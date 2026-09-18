"""集中读取环境变量:新前缀 INSIGHTLOOM_ 优先,兼容旧前缀 CURATOR_(存量部署不中断)。

用法:env("LLM_API_KEY")  →  依次查 INSIGHTLOOM_LLM_API_KEY、CURATOR_LLM_API_KEY。
"""

from __future__ import annotations

import os

_NEW = "INSIGHTLOOM_"
_OLD = "CURATOR_"  # 旧品牌前缀,保留兼容


def env(name: str, default: str = "") -> str:
    """读取环境变量:新前缀优先,回退旧前缀,再回退默认值。空字符串视为未设置。"""
    val = os.environ.get(f"{_NEW}{name}")
    if val:
        return val
    val = os.environ.get(f"{_OLD}{name}")
    if val:
        return val
    return default


def env_flag(name: str) -> bool:
    """开关型变量:任一前缀下为 "1" 即为真。"""
    return os.environ.get(f"{_NEW}{name}") == "1" or os.environ.get(f"{_OLD}{name}") == "1"
