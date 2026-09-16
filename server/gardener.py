"""🌻 园丁 Agent:定期巡库,维护知识库健康。

职责(对应 P1 路线图):
1. 扫描 vault:解析 [[双链]] 构建链接图
2. 发现问题:孤立笔记(无入链/出链)、疑似过时(日期久远)、薄弱笔记(正文过短)
3. 产出:
   - 巡库报告(findings)→ 进入每日简报
   - 双链建议(link_suggestion 提案)→ 走统一审批队列,批准后追加到既有笔记

与主流水线的关系:园丁是独立触发的维护 Agent(POST /api/garden/run,
未来可挂 cron),但复用同一套提案-审批机制。
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path

from . import llm
from . import store

LINK_RE = re.compile(r"\[\[([^\]\|#]+)")


def parse_frontmatter(text: str) -> dict:
    """解析 YAML frontmatter 的 key: value 行(轻量实现,足够 P1)。"""
    fm: dict[str, str] = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def scan_vault() -> dict:
    """构建链接图与笔记档案。"""
    notes: dict[str, dict] = {}
    for name in store.list_vault_notes():
        text = store.VAULT_DIR.joinpath(name).read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        body = re.sub(r"^---.*?---", "", text, flags=re.S).strip()
        notes[name] = {
            "links_out": set(LINK_RE.findall(text)),
            "fm": fm,
            "date": fm.get("date", ""),
            "tags": [t.strip() for t in fm.get("tags", "").strip("[]").split(",") if t.strip()],
            "body_len": len(body),
        }
    # 归一化出链:[[X]] → X.md,只保留真实存在的笔记
    valid = set(notes)
    for n in notes.values():
        n["links_out"] = {
            (l if l.endswith(".md") else l + ".md") for l in n["links_out"]
        }
        n["links_out"] = {l for l in n["links_out"] if l in valid}
    for name, n in notes.items():
        n["links_in"] = {other for other, o in notes.items() if name in o["links_out"]}
    return notes


def find_issues(notes: dict) -> list[dict]:
    """规则层检测:孤立 / 过时 / 薄弱。"""
    today = _dt.date.today()
    findings: list[dict] = []
    for name, n in notes.items():
        if not n["links_out"] and not n["links_in"]:
            findings.append({"type": "orphan", "note": name, "detail": "无入链也无出链,可能是知识孤岛"})
        if n["date"]:
            try:
                age = (today - _dt.date.fromisoformat(n["date"])).days
                if age > 180:
                    findings.append({"type": "stale", "note": name, "detail": f"已 {age} 天未更新,建议复核是否过时"})
            except ValueError:
                pass
        if n["body_len"] < 120:
            findings.append({"type": "thin", "note": name, "detail": f"正文仅 {n['body_len']} 字,建议补全"})
    return findings


def suggest_links(notes: dict) -> list[dict]:
    """LLM 层建议:为孤立笔记找同标签的伙伴,生成双链提案(走审批)。"""
    orphans = [name for name, n in notes.items() if not n["links_out"] and not n["links_in"]]
    suggestions: list[dict] = []
    for orphan in orphans:
        orphan_tags = set(notes[orphan]["tags"])
        if not orphan_tags:
            continue
        candidates = [
            name
            for name, n in notes.items()
            if name != orphan and orphan_tags & set(n["tags"]) and name not in notes[orphan]["links_out"]
        ]
        if not candidates:
            continue
        if llm.llm_status()["mock"]:
            picked, reason = candidates[0], f"共享标签 {sorted(orphan_tags & set(notes[candidates[0]]['tags']))}"
        else:
            data = llm.parse_json(
                llm.ask_llm(
                    "你是链接员(输出 JSON)。为孤立笔记从候选中挑最相关的 1 条,"
                    '输出 {"note": "xxx.md", "reason": "..."}',
                    f"孤立笔记:{orphan}(标签 {sorted(orphan_tags)})\n候选:{candidates}",
                    expect_json=True,
                )
            )
            picked = data.get("note", "")
            reason = data.get("reason", "")
            if picked not in candidates:  # 幻觉防护
                continue
        suggestions.append({"orphan": orphan, "target": picked, "reason": reason})
    return suggestions


def run_gardener() -> dict:
    """巡库主流程:扫描 → 规则检测 → LLM 建议双链 → 生成提案(等待审批)。"""
    notes = scan_vault()
    findings = find_issues(notes)
    suggestions = suggest_links(notes)

    system_item_id = 0  # 园丁是系统级 Agent,不挂具体条目
    store.log_event(system_item_id, "🌻 园丁", f"巡库完成:{len(notes)} 篇笔记,{len(findings)} 个发现,{len(suggestions)} 条双链建议")

    created = 0
    existing_pending = {p["filepath"] for p in store.list_proposals("pending")}
    for s in suggestions:
        key = f"{s['orphan']}->{s['target']}"
        if key in existing_pending:  # 防重复提案
            continue
        line = f"- [[{s['target'].removesuffix('.md')}]] — 🌻 园丁建议:{s['reason']}"
        pid = store.create_proposal(
            item_id=system_item_id,
            filepath=s["orphan"],
            markdown=line,
            verdict="gardener",
            links=[s["target"]],
            kind="link_suggestion",
        )
        created += 1
        store.log_event(system_item_id, "🌻 园丁", f"提案 #{pid}:建议在「{s['orphan']}」中补充双链 → {s['target']}")

    return {
        "total_notes": len(notes),
        "findings": findings,
        "suggestions": suggestions,
        "proposals_created": created,
        "ran_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
