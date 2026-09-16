"""真实 LLM 模式质量抽查(步骤①)。

用法:
    # 先确保 curator/.env 里已配置 CURATOR_LLM_API_KEY,并以真实模式启动服务:
    #   .venv/bin/uvicorn server.app:app --port 8300
    # 然后:
    .venv/bin/python scripts/quality_check.py [--base http://127.0.0.1:8300]

投递 3 篇不同类型的内容(观点型/事实型/故意有坑的内容),等流水线跑完,
打印每个提案的完整 Markdown 与质疑员结论,人工评估 Agent 产出质量。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

ARTICLES = [
    {
        "title": "RAG 检索质量的三个瓶颈",
        "content": (
            "RAG 系统的检索质量瓶颈通常有三处。第一是分块策略:固定长度切块会切断语义,"
            "按标题/段落的结构化分块配合 10-20% 重叠能显著降低上下文丢失;第二是嵌入模型与"
            "语料的领域错配,通用嵌入在垂直领域(法律/医疗)召回率明显下降,值得用小规模标注集"
            "做召回@K 评测再选型;第三是重排缺失,向量召回的 top-k 顺序不等于相关性顺序,"
            "加一层 cross-encoder 重排常见提升 10% 以上的端到端准确率。实践中建议先把评测集"
            "建起来,否则三个瓶颈的优化都是盲人摸象。"
        ),
    },
    {
        "title": "LangGraph 与 CrewAI 的取舍",
        "content": (
            "选型观点:CrewAI 适合快速原型,角色隐喻降低认知负担,一两天就能跑通;"
            "LangGraph 适合生产,显式状态图、条件边、checkpointer 与 human-in-the-loop "
            "是它真正的护城河。一个常见误区是把两者对立——其实很多团队用 CrewAI 验证想法,"
            "确认编排逻辑后再用 LangGraph 重写关键链路。成本上,LangGraph 的学习曲线约一周,"
            "但换来的是可回放、可测试、可观测的 agent 系统。如果你的场景需要人审批中间步骤,"
            "直接上 LangGraph,别绕路。"
        ),
    },
    {
        "title": "某调研断言(供质疑员挑刺)",
        "content": (
            "这篇文章断言:所有 multi-agent 系统都比单 agent 系统效果更好,准确率普遍提升"
            " 40% 以上,且成本更低。理由是多个 agent 可以互相纠错。文章没有给出任何实验数据、"
            "对比基线或适用范围,也没有讨论多 agent 通信开销与失败模式。"
        ),
    },
]


def req(base: str, path: str, data: dict | None = None) -> dict:
    url = f"{base}{path}"
    if data is None:
        r = urllib.request.urlopen(url, timeout=30)
        return json.loads(r.read())
    body = json.dumps(data).encode()
    r = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8300")
    ap.add_argument("--wait", type=float, default=90.0, help="等流水线的最长秒数")
    args = ap.parse_args()

    health = req(args.base, "/api/health")
    if health["llm"]["mock"]:
        print("⚠️ 服务当前是 MOCK 模式!请用真实模式启动:\n"
              "  .venv/bin/uvicorn server.app:app --port 8300  (需 curator/.env 配好 CURATOR_LLM_API_KEY)")
        sys.exit(2)
    print(f"✅ 真实模式:model={health['llm']['model']}\n")

    before = {p["id"] for p in req(args.base, "/api/state")["proposals"]}
    for a in ARTICLES:
        r = req(args.base, "/api/inbox", a)
        print(f"投递 #{r['id']}: {a['title']}")

    print(f"\n等待流水线(最长 {args.wait:.0f}s)…")
    deadline = time.time() + args.wait
    while time.time() < deadline:
        state = req(args.base, "/api/state")
        new = [p for p in state["proposals"] if p["id"] not in before]
        if len(new) >= len(ARTICLES) and all(
            i["status"] in ("awaiting_approval", "done") for i in state["items"][: len(ARTICLES)]
        ):
            break
        time.sleep(3)

    state = req(args.base, "/api/state")
    new = [p for p in state["proposals"] if p["id"] not in before]
    print(f"\n{'='*70}\n生成 {len(new)} 份提案,逐份评估:\n{'='*70}")
    for p in sorted(new, key=lambda x: x["id"]):
        print(f"\n───── 提案 #{p['id']} → {p['filepath']} | 质疑员:{p['verdict']} ─────")
        print(p["markdown"])
    print("\n评估要点:① 摘要是否忠实原文(第 3 篇故意有过度概括,看质疑员是否标 questioned)"
          "② 链接员引用是否真实存在 ③ frontmatter/标签是否合理")


if __name__ == "__main__":
    main()
