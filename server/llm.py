"""Curator LLM 封装:OpenAI 兼容协议(默认 DeepSeek)+ MOCK 模式。

MOCK 模式(CURATOR_LLM_MOCK=1 或无 Key 时自动):返回结构合理的确定性结果,
让整条流水线在无 Key 环境下也可开发、演示、测试。
"""

from __future__ import annotations

import json
import os

_BASE = os.environ.get("CURATOR_LLM_BASE_URL", "https://api.deepseek.com")
_MODEL = os.environ.get("CURATOR_LLM_MODEL", "deepseek-chat")
_KEY_ENV = "CURATOR_LLM_API_KEY"


def _mock_mode() -> bool:
    if os.environ.get("CURATOR_LLM_MOCK") == "1":
        return True
    return not os.environ.get(_KEY_ENV)


def llm_status() -> dict:
    return {
        "mock": _mock_mode(),
        "model": "mock" if _mock_mode() else _MODEL,
        "provider_base": _BASE if not _mock_mode() else "builtin",
    }


def ask_llm(system: str, user: str, expect_json: bool = False) -> str:
    if _mock_mode():
        return _mock_answer(system, user, expect_json)

    from openai import OpenAI

    client = OpenAI(api_key=os.environ[_KEY_ENV], base_url=_BASE)
    resp = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# ---------------- MOCK ----------------

def _mock_answer(system: str, user: str, expect_json: bool) -> str:
    if "分类员" in system:
        # 按内容长度路由:短内容稍后读,长内容深加工(确定性,便于测试两条分支)
        depth = "read_later" if len(user) < 120 else "deep"
        return json.dumps({"depth": depth, "tags": ["AI", "待整理"]}, ensure_ascii=False)
    if "摘要员" in system:
        first = user.strip().split("\n")[0][:40]
        return json.dumps(
            {"summary": f"要点:{first}……(MOCK 摘要,接真实 LLM 后自动替换)", "tags": ["AI", "知识库"]},
            ensure_ascii=False,
        )
    if "链接员" in system:
        return json.dumps(
            {"connections": ["LangGraph-入门笔记.md"], "reasons": ["主题同为 agent 编排"]},
            ensure_ascii=False,
        )
    if "质疑员" in system:
        return json.dumps(
            {"verdict": "pass", "comment": "摘要与原文关键词覆盖充分(MOCK 判定)"},
            ensure_ascii=False,
        )
    return json.dumps({"ok": True}, ensure_ascii=False) if expect_json else "MOCK 回复"
