"""洞察织机（InsightLoom）API 服务(FastAPI)。

端点:
- POST /api/inbox               投递内容,触发 Agent 流水线
- GET  /api/state               聚合状态(条目/事件/提案/vault/LLM 信息),供 UI 轮询
- POST /api/proposals/{id}/approve   批准提案 → 写入 vault Markdown
- POST /api/proposals/{id}/reject    拒绝提案
- GET  /                        Web UI(静态页)

运行:
    CURATOR_LLM_MOCK=1 .venv/bin/uvicorn server.app:app --port 8300
    真实模式:CURATOR_LLM_API_KEY=sk-xxx .venv/bin/uvicorn server.app:app
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 启动时加载项目根 .env(如存在),自动注入 CURATOR_LLM_API_KEY 等
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

from . import gardener
from . import llm
from . import pipeline
from . import retrieval
from . import store

app = FastAPI(title="InsightLoom API", version="0.1.0")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
VAULT_DIR = Path(__file__).resolve().parent.parent / "vault"


class InboxItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    url: str = ""


@app.post("/api/inbox")
def add_item(item: InboxItem):
    item_id = store.create_item(item.title, item.content, item.url)
    row = store.get_item(item_id)
    threading.Thread(target=pipeline.run_pipeline, args=(row,), daemon=True).start()
    return {"id": item_id, "status": "processing"}


@app.get("/api/state")
def state():
    return {
        "items": store.list_items(),
        "events": store.list_events(),
        "proposals": store.list_proposals(),
        "vault": store.list_vault_notes(),
        "llm": llm.llm_status(),
    }


@app.post("/api/proposals/{pid}/approve")
def approve(pid: int):
    p = store.get_proposal(pid)
    if not p:
        raise HTTPException(404, "proposal not found")
    if p["status"] != "pending":
        raise HTTPException(409, f"proposal already {p['status']}")
    kind = p.get("kind", "new_note")
    if kind == "link_suggestion":
        # 园丁提案:把双链追加进既有笔记
        try:
            store.append_to_vault_note(p["filepath"], p["markdown"])
            name = p["filepath"]
        except FileNotFoundError:
            raise HTTPException(410, f"目标笔记已不存在: {p['filepath']}")
    else:
        name = store.write_vault_note(p["filepath"].removesuffix(".md"), p["markdown"])
    store.set_proposal_status(pid, "approved")
    if p["item_id"]:
        store.set_item_status(p["item_id"], "done")
    # 审批落盘后,自动把该笔记重建进语义索引(失败不影响主流程)
    try:
        target = VAULT_DIR / name
        if target.exists():
            retrieval.index_note(target.name, target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    if kind == "link_suggestion":
        store.log_event(p["item_id"], "✅ 审批", f"提案 #{pid} 已批准:双链追加到 {name}")
    else:
        store.log_event(p["item_id"], "✅ 审批", f"提案 #{pid} 已批准 → vault/{name}")
    return {"file": name, "kind": kind}


@app.post("/api/proposals/{pid}/reject")
def reject(pid: int):
    p = store.get_proposal(pid)
    if not p:
        raise HTTPException(404, "proposal not found")
    if p["status"] != "pending":
        raise HTTPException(409, f"proposal already {p['status']}")
    store.set_proposal_status(pid, "rejected")
    store.set_item_status(p["item_id"], "rejected")
    store.log_event(p["item_id"], "🚫 审批", f"提案 #{pid} 被拒绝")
    return {"status": "rejected"}


@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.llm_status(), "retrieval": retrieval.status()}


@app.get("/api/search")
def search(q: str = "", k: int = 5):
    """语义检索 vault:本地嵌入,无需任何云 API。"""
    if not q.strip():
        return {"ok": False, "results": [], "reason": "empty query"}
    return {"ok": True, "query": q, "results": retrieval.search(q, k=k)}


@app.post("/api/reindex")
def reindex():
    """全量重建语义索引(手动兜底入口)。"""
    return {"ok": True, **retrieval.reindex_vault()}


@app.get("/api/graph")
def graph():
    """知识图谱:vault 全量笔记为节点,[[wiki-link]] 为边;未命中的链接单独返回。

    供前端图谱视图(力导向图)消费;纯本地解析,无任何外部依赖。
    """
    import re

    files = sorted(VAULT_DIR.glob("*.md"))
    nodes = []
    for f in files:
        first = ""
        try:
            first = next(
                (ln.lstrip("# ").strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("# ")),
                f.stem,
            )
        except OSError:
            first = f.stem
        nodes.append({"id": f.stem, "file": f.name, "title": first or f.stem})

    known = {n["id"] for n in nodes}
    links: list[dict] = []
    unresolved: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for target in dict.fromkeys(re.findall(r"\[\[([^\]|#]+)", text)):
            target = target.strip()
            if not target:
                continue
            if target == f.stem:
                continue
            if target in known:
                links.append({"source": f.stem, "target": target})
            else:
                unresolved.append({"from": f.stem, "to": target})

    degree = {n["id"]: 0 for n in nodes}
    for l in links:
        degree[l["source"]] += 1
        degree[l["target"]] += 1
    for n in nodes:
        n["degree"] = degree[n["id"]]

    return {"ok": True, "nodes": nodes, "links": links, "unresolved": unresolved}


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.post("/api/ask")
def ask(body: AskBody):
    """RAG 问答:本地语义检索 top-k 小节 → LLM 生成带引用的回答。"""
    hits = retrieval.search(body.question, k=5)
    if not hits:
        return {
            "ok": True,
            "answer": "知识库(或索引)里暂时找不到相关内容。可以先投递一些材料,或在简报页运行巡库后重建索引。",
            "citations": [],
        }
    context = "\n\n".join(
        f"[{i+1}] 《{h['title']}》小节「{h['section']}」:\n{h['snippet']}" for i, h in enumerate(hits)
    )
    answer = llm.ask_llm(
        "你是洞察织机的知识问答员。仅依据下面给出的知识库片段回答问题,"
        "并在回答末尾单独一行列出引用,格式:引用:[[笔记名]]。"
        "知识库里没有的内容要明说,不要编造。",
        f"知识库片段:\n{context}\n\n问题:{body.question}",
    )
    return {"ok": True, "answer": answer, "citations": list(dict.fromkeys(h["note"] for h in hits))}


@app.post("/api/garden/run")
def garden_run():
    """🌻 触发园丁巡库:发现 → 简报;双链建议 → 审批队列。"""
    return gardener.run_gardener()


@app.get("/api/digest")
def digest():
    """每日简报数据:24h 活动统计 + vault 健康度 + 巡库发现(实时计算)。"""
    import time as _time

    day_ago = _time.time() - 86400
    items_24h = [i for i in store.list_items(500) if i["created_at"] >= day_ago]
    proposals_24h = [p for p in store.list_proposals() if p["created_at"] >= day_ago]
    approved_24h = [p for p in proposals_24h if p["status"] == "approved"]

    notes = gardener.scan_vault()
    findings = gardener.find_issues(notes)
    tag_counter: dict[str, int] = {}
    for n in notes.values():
        for t in n["tags"]:
            tag_counter[t] = tag_counter.get(t, 0) + 1
    top_tags = sorted(tag_counter.items(), key=lambda kv: -kv[1])[:8]

    return {
        "stats_24h": {
            "items": len(items_24h),
            "approved": len(approved_24h),
            "pending": len([p for p in store.list_proposals("pending")]),
            "gardener_suggestions": len([p for p in proposals_24h if p.get("kind") == "link_suggestion"]),
        },
        "vault": {
            "total": len(notes),
            "orphan": sum(1 for f in findings if f["type"] == "orphan"),
            "stale": sum(1 for f in findings if f["type"] == "stale"),
            "thin": sum(1 for f in findings if f["type"] == "thin"),
        },
        "findings": findings,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "llm": llm.llm_status(),
    }


# 静态资源(UI + 本地 tailwind.js),挂在 API 路由之后,不遮蔽 /api/*
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
