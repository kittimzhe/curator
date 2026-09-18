// 洞察织机(InsightLoom)浏览器采集插件 · MV3 service worker
// 右键「织入」→ POST {server}/api/inbox → 通知结果。
// 扩展的 host_permissions 使其 fetch 不受页面 CORS / 私有网络管控限制。

const DEFAULT_SERVER = "http://127.0.0.1:8300";

async function getServer() {
  const { server } = await chrome.storage.local.get("server");
  return (server || DEFAULT_SERVER).replace(/\/+$/, "");
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "loom-selection",
      title: "🌾 织入洞察织机(选中文字)",
      contexts: ["selection"],
    });
    chrome.contextMenus.create({
      id: "loom-page",
      title: "🌾 织入整页(标题+正文摘要)",
      contexts: ["page"],
    });
  });
});

async function grabPageContent(tabId) {
  const [res] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const meta = document.querySelector('meta[name="description"]');
      const sel = String(window.getSelection() || "");
      return {
        content: sel || (meta && meta.content ? meta.content : document.body.innerText.slice(0, 4000)),
      };
    },
  });
  return res?.result?.content || "";
}

function notify(ok, detail) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: chrome.runtime.getURL("icons/icon128.png"),
    title: ok ? "已织入洞察织机 🌾" : "织入失败",
    message: detail,
  });
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const server = await getServer();
  let title = tab?.title || "未命名页面";
  let content = info.selectionText || "";

  if (info.menuItemId === "loom-page" && tab?.id != null) {
    try {
      content = await grabPageContent(tab.id);
    } catch (e) {
      content = "";
    }
  }
  if (!content) content = `(无正文,仅链接)${info.pageUrl || tab?.url || ""}`;

  try {
    const r = await fetch(`${server}/api/inbox`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title.slice(0, 200),
        content: content.slice(0, 8000),
        url: info.pageUrl || tab?.url || "",
      }),
    });
    const j = await r.json();
    if (r.ok && j.status === "processing") notify(true, `「${title.slice(0, 40)}」已进入流水线`);
    else notify(false, `服务响应异常: ${r.status} ${JSON.stringify(j).slice(0, 80)}`);
  } catch (e) {
    notify(false, `无法连接 ${server} — 服务在跑吗?(${e.message?.slice(0, 60) || e})`);
  }
});
