# 项目初始化调整清单（InsightLoom）

> 目标：把项目从早期代号状态统一到当前品牌与上线准备状态。
> 更新时间：2026-09-17

## 已完成

- [x] 前端品牌统一为"洞察织机 / InsightLoom"
- [x] 域名方案确定为 `insightloomapp.com`
- [x] 图标文件重命名为 `icon-insightloom-*`、`favicon-insightloom.svg`
- [x] SEO 基础项:`title`、`description`、`og:*`、`twitter:*`、`robots.txt`、`sitemap.xml`
- [x] OG 分享图:已接入极简版 `og-image-insightloom-minimal.png`
- [x] API 标题改为 `InsightLoom API`
- [x] 产品愿景文档主标题同步到 InsightLoom
- [x] 竞赛记录已落地:`docs/COMPETITION__CUP_2026.md`
- [x] `docs/PRODUCT_VISION.md` 历史 `Curator` 字样已清理
- [x] BP 模板已落地:`docs/BP_OUTLINE.md`
- [x] 代码层品牌残留清理:落盘脚注与 docstring(pipeline/store/llm),存量 vault 笔记脚注批量迁移
- [x] README 首屏截图更新为浅色新版 UI

- [x] **GitHub 仓库名 `curator` → `insightloom`**(已完成,旧链接 301 重定向,本地 remote 已同步)

## 待完成(下一轮)

- [ ] 评估是否把环境变量前缀 `CURATOR_` 迁移到 `INSIGHTLOOM_`(建议做兼容映射,避免中断)
- [ ] 在部署平台完成正式域名绑定并验证 OG 抓取
- [ ] 增加基础访问统计(如 Plausible/Umami)用于后续增长验证

## 命名规范（当前约定）

- 对外品牌：`洞察织机` / `InsightLoom`
- 官网域名：`insightloomapp.com`
- 资产文件：`insightloom` 前缀
- 历史兼容命名（暂不动）：仓库目录名 `curator`、环境变量 `CURATOR_*`
