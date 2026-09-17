"""洞察织机(InsightLoom)Agent 流水线(LangGraph)。

结构:

              ┌──────────┐
              │ 分类员    │ depth = read_later
              │ (classify)│──────────────────────┐
              └────┬─────┘                       ▼
                   │ depth = deep          ┌───────────┐
          ┌────────┴────────┐              │ 组装员     │
          ▼ (fan-out 并行)  │              │ (assemble)│
   ┌──────────┐   ┌──────────┐             └─────┬─────┘
   │ 摘要员    │   │ 链接员   │  (fan-in)         │
   │ (summarize)│   │ (link)   │───────────────────┤
   └────┬─────┘   └────┬─────┘                   │
        └──────┬────────┘                        │
               ▼                                 │
        ┌──────────┐                             │
        │ 质疑员    │─────────────────────────────┘
        │ (skeptic)│
        └──────────┘

- 分类员决定加工深度(短内容稍后读、长内容深加工)——按需消耗 token
- 摘要员/链接员并行(fan-out),质疑员等两者都完成(fan-in)再审查
- 所有产出进入"提案"队列等待人工审批,不直接写 vault
"""

from __future__ import annotations

import datetime as _dt
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import llm
from . import store

AGENTS = {
    "classify": ("分类员", "🏷️"),
    "summarize": ("摘要员", "📝"),
    "link": ("链接员", "🔗"),
    "skeptic": ("质疑员", "⚔️"),
    "assemble": ("组装员", "📦"),
}


class State(TypedDict, total=False):
    item_id: int
    title: str
    url: str
    content: str
    depth: str
    tags: list
    summary: str
    connections: list
    reasons: list
    verdict: str
    comment: str
    markdown: str
    filename: str


def _log(state: State, agent_key: str, message: str, level: str = "info") -> None:
    name, emoji = AGENTS[agent_key]
    store.log_event(state["item_id"], f"{emoji} {name}", message, level)


# ---------------- 节点实现 ----------------

def classify(state: State) -> dict:
    data = llm.parse_json(
        llm.ask_llm(
            "你是分类员(输出 JSON)。判断内容值得深加工(deep)还是稍后读(read_later),"
            "并给 1-3 个标签。注意:包含强断言、对比结论、数字/百分比的内容必须 deep"
            "(需要质疑员审查);纯链接、简短通知类才 read_later。"
            '输出 {"depth": "deep|read_later", "tags": [...]}',
            f"标题:{state['title']}\n内容:\n{state['content'][:600]}",
            expect_json=True,
        )
    )
    depth = data.get("depth", "read_later")
    tags = data.get("tags", [])
    _log(state, "classify", f"判定深度={depth},标签={tags}")
    return {"depth": depth, "tags": tags}


def summarize(state: State) -> dict:
    data = llm.parse_json(
        llm.ask_llm(
            "你是摘要员(输出 JSON)。为内容写 3 句话摘要,提炼标签。"
            '输出 {"summary": "...", "tags": [...]}',
            f"标题:{state['title']}\n内容:\n{state['content'][:2000]}",
            expect_json=True,
        )
    )
    summary = data.get("summary", "")
    _log(state, "summarize", f"生成摘要({len(summary)} 字)")
    tags = sorted(set(state.get("tags", []) + data.get("tags", [])))
    return {"summary": summary, "tags": tags}


def link(state: State) -> dict:
    vault_notes = store.list_vault_notes()
    # 语义候选优先:用本地向量检索找出最相关的既有笔记小节,给 LLM 一个
    # 高质量短名单;检索不可用时回退全量笔记列表(原行为)。
    try:
        from . import retrieval

        hits = retrieval.search(state["content"][:500], k=8)
    except Exception:  # noqa: BLE001 —— 检索层故障不影响流水线
        hits = []
    if hits:
        seen, candidates = set(), []
        for h in hits:
            if h["note"] not in seen:
                seen.add(h["note"])
                candidates.append(f"{h['note']}(相关小节:{h['section']})")
        candidate_desc = "语义相关候选:\n" + "\n".join(candidates)
        _log(state, "link", f"语义检索给出 {len(candidates)} 个候选(本地嵌入)")
    else:
        candidate_desc = f"既有笔记:{vault_notes}"
    data = llm.parse_json(
        llm.ask_llm(
            "你是链接员(输出 JSON)。从既有笔记列表中找出与该内容相关的笔记(最多 3 条),"
            '没有则给空数组。输出 {"connections": ["文件名.md"], "reasons": ["原因"]}',
            f"新内容标题:{state['title']}\n内容摘要片段:{state['content'][:300]}\n\n{candidate_desc}",
            expect_json=True,
        )
    )
    conns = []
    for c in data.get("connections", []):
        base = c.split("(")[0].strip()  # 兼容候选带"(相关小节:…)"后缀的引用
        if base in vault_notes:
            conns.append(base)
        elif c in vault_notes:  # 幻觉防护:只保留真实存在的笔记
            conns.append(c)
    if data.get("connections") and not conns:
        _log(state, "link", "LLM 提到的笔记不存在,已过滤(幻觉防护)", level="warn")
    _log(state, "link", f"连接到 {len(conns)} 条既有笔记: {conns}")
    return {"connections": conns, "reasons": data.get("reasons", [])}


def skeptic(state: State) -> dict:
    # 摘要员与链接员都完成后执行(fan-in):对照原文审查摘要
    data = llm.parse_json(
        llm.ask_llm(
            "你是质疑员,负责对抗式审查(输出 JSON)。检查摘要是否过度概括、无中生有、"
            '遗漏关键限定。输出 {"verdict": "pass|questioned", "comment": "..."}',
            f"原文片段:\n{state['content'][:800]}\n\n摘要员的摘要:\n{state.get('summary', '(无)')}",
            expect_json=True,
        )
    )
    verdict = data.get("verdict", "pass")
    comment = data.get("comment", "")
    level = "info" if verdict == "pass" else "debate"
    _log(state, "skeptic", f"审查结论={verdict}:{comment}", level=level)
    return {"verdict": verdict, "comment": comment}


def assemble(state: State) -> dict:
    today = _dt.date.today().isoformat()
    tags = ", ".join(state.get("tags", []))
    lines = [
        "---",
        f"title: {state['title']}",
        f"source: {state.get('url') or '手动录入'}",
        f"date: {today}",
        f"tags: [{tags}]",
        f"depth: {state.get('depth')}",
        "---",
        "",
        f"# {state['title']}",
        "",
    ]
    if state.get("summary"):
        lines += ["## 摘要", state["summary"], ""]
    else:
        lines += [f"> 稍后读。原文片段:{state['content'][:200]}", ""]
    if state.get("connections"):
        lines += ["## 关联笔记"]
        lines += [f"- [[{c.replace('.md', '')}]] — {r}" for c, r in zip(state["connections"], state.get("reasons", []))]
        lines.append("")
    verdict_text = {
        "pass": "✅ 质疑员审查通过",
        "questioned": f"⚠️ 质疑员存疑:{state.get('comment', '')}",
    }.get(state.get("verdict", ""), "—(稍后读快车道,未触发对抗审查)")
    lines += ["## Agent 审查", verdict_text, "", "---", "*由 洞察织机(InsightLoom)Agent 流水线生成,经人工审批入库*"]
    markdown = "\n".join(lines)

    filename = store.slugify(state["title"])
    pid = store.create_proposal(
        item_id=state["item_id"],
        filepath=f"{filename}.md",
        markdown=markdown,
        verdict=state.get("verdict", ""),
        links=state.get("connections", []),
    )
    _log(state, "assemble", f"提案 #{pid} 已生成 → {filename}.md,等待人工审批")
    return {"markdown": markdown, "filename": filename}


def route_after_classify(state: State):
    """深加工:fan-out 到摘要员+链接员(返回列表触发并行);稍后读:直达组装员。"""
    if state.get("depth") == "read_later":
        return "assemble"
    return ["summarize", "link"]


def build_graph():
    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("summarize", summarize)
    g.add_node("link", link)
    g.add_node("skeptic", skeptic)
    g.add_node("assemble", assemble)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify",
        route_after_classify,
        {"summarize": "summarize", "link": "link", "assemble": "assemble"},
    )
    # fan-out: 摘要员与链接员并行
    g.add_edge("summarize", "skeptic")
    g.add_edge("link", "skeptic")
    g.add_edge("skeptic", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_GRAPH = None


def run_pipeline(item: dict) -> None:
    """处理一条收件箱内容:跑 graph → 生成提案(不直接写盘)。"""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    item_id = item["id"]
    store.set_item_status(item_id, "processing")
    store.log_event(item_id, "⚡ 调度器", f"开始处理「{item['title']}」")
    try:
        _GRAPH.invoke(
            {
                "item_id": item_id,
                "title": item["title"],
                "url": item.get("url") or "",
                "content": item.get("content") or "",
            }
        )
        store.set_item_status(item_id, "awaiting_approval")
    except Exception as e:  # noqa: BLE001
        store.log_event(item_id, "❌ 调度器", f"流水线失败: {e}", level="warn")
        store.set_item_status(item_id, "error")
