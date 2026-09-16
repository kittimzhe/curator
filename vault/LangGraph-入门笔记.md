---
title: LangGraph 入门笔记
date: 2026-09-15
tags: [agent, 编排]
---

# LangGraph 入门

StateGraph 把 agent 编排建模为状态图:节点是函数,边是控制流,
conditional_edges 做路由。fan-out/fan-in 天然支持并行。
