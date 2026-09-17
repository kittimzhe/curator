# 洞察织机（InsightLoom）最小发布清单

适用目标：先低成本上线 `insightloomapp.com`，保证可访问、可检索、可迭代。

## 1) 上线前（30 分钟）

- [ ] 品牌文案统一：页面标题、Logo、README、favicon 一致
- [ ] 访问入口确认：`insightloomapp.com` 可作为唯一主入口
- [ ] 基础页面可用：首页可打开、核心按钮可点击、无明显报错
- [ ] HTTPS 生效：浏览器地址栏显示安全连接

## 2) 域名与 DNS

- [ ] 在域名服务商完成 `insightloomapp.com` 购买
- [ ] 按托管平台要求添加 DNS 记录（常见为 `A` 或 `CNAME`）
- [ ] 配置 `www` 到主域名跳转（`www.insightloomapp.com` → `insightloomapp.com`）
- [ ] 等待 DNS 生效后复测（可用手机网络再测一次）

## 3) 部署（零预算优先）

- [ ] 先用免费托管跑通（如 `*.vercel.app` / `*.pages.dev`）
- [ ] 再绑定自定义域名 `insightloomapp.com`
- [ ] 打开自动部署（推送代码后自动更新站点）
- [ ] 保留一个回退版本（上次稳定构建）

## 4) 基础 SEO（最小可用）

- [ ] 页面 `<title>` 含品牌词与价值主张
- [ ] `meta description` 描述产品用途（80~160 字）
- [ ] favicon 正常显示（桌面/移动端都检查）
- [ ] 准备 `og:title`、`og:description`、`og:image`（用于社交分享）

## 5) 发布后 24 小时内

- [ ] 自测三轮：桌面 Chrome、手机浏览器、隐私模式
- [ ] 接入 51.la 统计（国内节点友好，替换原 Plausible/Umami 设想；一行 script + 统计 ID）
- [ ] 监控 404/500（平台日志）并修复首批问题
- [ ] 收集首批反馈（3~5 人）并记录到待办
- [ ] 只做高优先修复，不做大重构

## 6) 下一步建议（MVP 之后）

- 增加独立的 `about` 与 `privacy` 页面
- 增加使用示例（1 分钟上手）
- 准备一个对外演示链接（产品介绍 + 截图 + 核心流程）
