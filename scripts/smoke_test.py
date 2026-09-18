"""洞察织机(InsightLoom)端到端冒烟测试(MOCK 模式)。

覆盖:健康检查 → 投递 → 五 Agent 流水线 → 审批落盘 → 简报 → 园丁巡库 + 旧前缀兼容自检。
检索层为可选检查:嵌入模型不可用时自动跳过(检索模块本身设计为优雅降级)。
用法:INSIGHTLOOM_LLM_MOCK=1 .venv/bin/python scripts/smoke_test.py
退出码 0 = 全部通过。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ["INSIGHTLOOM_LLM_MOCK"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 兼容性自检:旧前缀 CURATOR_ 仍可读取(存量部署不中断)
os.environ["CURATOR_SMOKE_COMPAT"] = "1"
from server.config import env  # noqa: E402

assert env("SMOKE_COMPAT") == "1", "CURATOR_ 旧前缀兼容失效"
os.environ.pop("CURATOR_SMOKE_COMPAT")

from fastapi.testclient import TestClient  # noqa: E402

from server.app import app  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    (PASSED if ok else FAILED).append(name)
    mark = "✓" if ok else "✗"
    print(f"{mark} {name}" + (f" — {detail}" if detail else ""))


client = TestClient(app)

# 1) 健康
r = client.get("/api/health")
check("健康检查", r.status_code == 200 and r.json()["ok"], r.text[:80])

# 2) 投递 → 流水线
r = client.post(
    "/api/inbox",
    json={
        "title": "冒烟测试条目",
        "content": (
            "端到端冒烟测试:该内容刻意写得足够长,确保 MOCK 分类员判定为 deep 深加工分支"
            "(提示词长度需超过 120 字符)。分类员路由后,摘要员与链接员并行执行,"
            "链接员会调用本地嵌入检索(冷环境会下载约 79MB 的 ONNX 模型),"
            "随后质疑员做对抗式审查,最终由组装员产出提案。"
            "内含强断言与数字以命中 deep 判据:处理效率提升 300%,断言覆盖率 95%,召回率 82%。"
        ),
    },
)
check("投递返回", r.status_code == 200 and r.json()["status"] == "processing", r.text[:80])

# 3) 等待提案出现(流水线在后台线程)
pid = None
for _ in range(60):
    st = client.get("/api/state").json()
    pending = [p for p in st["proposals"] if p["status"] == "pending"]
    if pending:
        pid = pending[0]["id"]
        break
    time.sleep(0.5)
check("流水线产出提案", pid is not None, f"proposal #{pid}")

# 3b) 事件异步落库:等到事件流稳定且角色数达标(全新环境里
#     link() 首次触发嵌入模型下载,可能让事件间隔长达数十秒)
agents: set[str] = set()
for _ in range(180):  # 最多 90 秒
    agents = {e["agent"] for e in st["events"]}
    if len(agents) >= 4:
        break
    time.sleep(0.5)
    st = client.get("/api/state").json()
check("多 Agent 事件", len(agents) >= 4, f"{len(agents)} 个角色: {sorted(agents)[:5]}")

# 5) 审批落盘
if pid:
    r = client.post(f"/api/proposals/{pid}/approve")
    ok = r.status_code == 200
    if ok:
        f = Path(__file__).resolve().parent.parent / "vault" / r.json()["file"]
        ok = f.exists()
        check("批准并落盘 Markdown", ok, str(f.name) if ok else "文件未出现")
    else:
        check("批准并落盘 Markdown", False, r.text[:80])

# 6) 简报
r = client.get("/api/digest")
check("每日简报", r.status_code == 200 and "stats_24h" in r.json())

# 7) 园丁巡库(不强制有发现,只要不炸)
r = client.post("/api/garden/run")
check("园丁巡库", r.status_code == 200 and "findings" in r.json())

# 8) 检索(可选:嵌入模型可用才断言命中)
try:
    r = client.post("/api/reindex")
    hits = client.get("/api/search", params={"q": "冒烟测试"}).json()["results"]
    check("语义检索(可选)", r.status_code == 200 and len(hits) >= 1, f"{len(hits)} 命中")
except Exception as e:  # noqa: BLE001
    print(f"- 语义检索跳过(嵌入模型不可用):{type(e).__name__}")

print(f"\n通过 {len(PASSED)} 项" + (f",失败 {len(FAILED)} 项:{FAILED}" if FAILED else ""))
sys.exit(1 if FAILED else 0)
