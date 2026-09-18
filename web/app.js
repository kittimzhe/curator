const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const TAB_BASE = 'px-3 py-1 rounded-full font-medium transition duration-200';
const THEME_KEY = 'insightloom_theme';
const LEGACY_THEME_KEY = 'zhice_theme';
const DRAFT_KEY = 'insightloom_inbox_draft';
const THEME_ORDER = ['light', 'dark', 'auto'];
const THEME_COPY = {
  light: '☀️ 浅色',
  dark: '🌙 深色',
  auto: '🖥 跟随系统',
};
let currentThemeMode = 'light';
let themeMediaQuery = null;
const COPY = {
  submitReady: '投递到洞察织机',
  submitSending: '投递中…',
  proposalApprove: '✅ 批准入库',
  proposalReject: '🚫 退回重审',
  proposalPendingSuffix: '条待审批',
  toastRejected: '🚫 已退回重审',
  toastIngested: file => `✅ 已纳入知库 vault/${file}`,
  toastLinkUpdated: file => `🌻 双链已追加到 ${file}`,
  toastInboxQueued: '📥 已投递到洞察织机,治理流水线启动',
  toastInboxFailed: '投递失败,请稍后重试',
  toastDraftRestored: '已恢复上次未提交草稿',
};

function readThemePreference() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'dark' || saved === 'light' || saved === 'auto') return saved;
    const legacy = localStorage.getItem(LEGACY_THEME_KEY);
    if (legacy === 'dark' || legacy === 'light' || legacy === 'auto') return legacy;
  } catch (_) {}
  return 'light';
}

function getSystemTheme() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light';
  if (!themeMediaQuery) themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  return themeMediaQuery.matches ? 'dark' : 'light';
}

function resolveThemeMode(mode) {
  return mode === 'auto' ? getSystemTheme() : mode;
}

function applyTheme(mode) {
  currentThemeMode = mode;
  const effectiveTheme = resolveThemeMode(mode);
  const isDark = effectiveTheme === 'dark';
  document.body.classList.toggle('dark-theme', isDark);
  const btn = $('theme-toggle');
  if (btn) {
    btn.textContent = THEME_COPY[mode] || THEME_COPY.light;
    btn.setAttribute('aria-label', `当前主题模式: ${btn.textContent}`);
  }
}

function setTheme(theme, persist = true) {
  applyTheme(theme);
  if (!persist) return;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch (_) {}
}

function toggleTheme() {
  const currentIdx = THEME_ORDER.indexOf(currentThemeMode);
  const next = THEME_ORDER[(currentIdx + 1) % THEME_ORDER.length];
  setTheme(next, true);
}

function bindSystemThemeListener() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
  if (!themeMediaQuery) themeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  const onChange = () => {
    if (currentThemeMode === 'auto') applyTheme('auto');
  };
  if (typeof themeMediaQuery.addEventListener === 'function') {
    themeMediaQuery.addEventListener('change', onChange);
  } else if (typeof themeMediaQuery.addListener === 'function') {
    themeMediaQuery.addListener(onChange);
  }
}

function setInboxSubmitting(isSubmitting) {
  const submitBtn = $('inbox-submit');
  if (!submitBtn) return;
  submitBtn.disabled = isSubmitting;
  submitBtn.textContent = isSubmitting ? COPY.submitSending : COPY.submitReady;
  submitBtn.classList.toggle('opacity-70', isSubmitting);
  submitBtn.classList.toggle('cursor-not-allowed', isSubmitting);
}

function readInboxDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const draft = JSON.parse(raw);
    if (!draft || typeof draft !== 'object') return null;
    return {
      title: String(draft.title || ''),
      url: String(draft.url || ''),
      content: String(draft.content || ''),
    };
  } catch (_) {
    return null;
  }
}

function saveInboxDraft() {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({
      title: $('f-title')?.value || '',
      url: $('f-url')?.value || '',
      content: $('f-content')?.value || '',
    }));
  } catch (_) {}
}

function clearInboxDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch (_) {}
}

function bindInboxEnhancements() {
  const draft = readInboxDraft();
  if (draft && (draft.title || draft.url || draft.content)) {
    $('f-title').value = draft.title;
    $('f-url').value = draft.url;
    $('f-content').value = draft.content;
    toast(COPY.toastDraftRestored);
  }

  ['f-title', 'f-url', 'f-content'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('input', saveInboxDraft);
  });

  const contentInput = $('f-content');
  const form = $('inbox-form');
  if (contentInput && form) {
    contentInput.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        form.requestSubmit();
      }
    });
  }
}

/* ---------- Agent 名录(配色统一来源) ---------- */
const AGENTS = {
  '分类员': { emoji:'🏷️', color:'sky' },
  '摘要员': { emoji:'📝', color:'violet' },
  '链接员': { emoji:'🔗', color:'amber' },
  '质疑员': { emoji:'⚔️', color:'rose' },
  '组装员': { emoji:'📦', color:'emerald' },
  '园丁':   { emoji:'🌻', color:'lime' },
};
const AGENT_COLORS = {
  sky:   { dot:'bg-sky-500',    text:'text-sky-700',    chip:'bg-sky-50 text-sky-700 border-sky-200' },
  violet:{ dot:'bg-violet-500', text:'text-violet-700', chip:'bg-violet-50 text-violet-700 border-violet-200' },
  amber: { dot:'bg-amber-500',  text:'text-amber-700',  chip:'bg-amber-50 text-amber-700 border-amber-200' },
  rose:  { dot:'bg-rose-500',   text:'text-rose-700',   chip:'bg-rose-50 text-rose-700 border-rose-200' },
  emerald:{dot:'bg-emerald-500',text:'text-emerald-700',chip:'bg-emerald-50 text-emerald-700 border-emerald-200' },
  lime:  { dot:'bg-lime-500',   text:'text-lime-700',   chip:'bg-lime-50 text-lime-700 border-lime-200' },
};
function agentStyle(name) {
  for (const [key, cfg] of Object.entries(AGENTS)) if (name.includes(key)) return cfg;
  return { emoji:'⚡', color:'slate' };
}
const SLATE = { dot:'bg-slate-400', text:'text-slate-600', chip:'bg-slate-100 text-slate-600 border-slate-300' };

const ITEM_STATUS = {
  pending:          ['等待治理','bg-slate-100 text-slate-600'],
  processing:       ['洞察织机治理中','bg-sky-100 text-sky-700'],
  awaiting_approval:['等待馆长审批','bg-amber-100 text-amber-700'],
  done:             ['已纳入知库','bg-emerald-100 text-emerald-700'],
  rejected:         ['未通过本次入库','bg-rose-100 text-rose-700'],
  error:            ['治理出错','bg-rose-100 text-rose-700'],
};
const LEVEL_BORDER = { info:'border-l-slate-300', warn:'border-l-amber-400', debate:'border-l-violet-400' };
const VERDICT_THEME = {
  pass: ['✅ 审查通过', 'text-emerald-600'],
  questioned: ['⚔️ 质疑员存疑', 'text-violet-600'],
  default: ['🌻 园丁建议', 'text-lime-600'],
};
const PROPOSAL_STATUS_THEME = {
  approved: ['已纳入知库', 'text-emerald-600'],
  rejected: ['未通过本次入库', 'text-rose-600'],
};

/* ---------- Markdown-lite 渲染(提案预览用) ---------- */
function mdLite(src) {
  let h = esc(src);
  h = h.replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">[[$1]]</span>');
  h = h.replace(/^### (.*)$/gm, '<div class="font-semibold text-slate-700 mt-2">$1</div>');
  h = h.replace(/^## (.*)$/gm, '<div class="font-bold text-sky-700 mt-2">$1</div>');
  h = h.replace(/^# (.*)$/gm, '<div class="font-bold text-base text-slate-800 mt-1">$1</div>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-slate-800">$1</strong>');
  h = h.replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-amber-700 rounded px-1 text-[11px] border border-slate-200">$1</code>');
  h = h.replace(/^- (.*)$/gm, '<div class="pl-3 border-l border-slate-300 ml-1 my-0.5">$1</div>');
  h = h.replace(/^&gt; (.*)$/gm, '<div class="pl-2 border-l-2 border-slate-300 text-slate-600 italic my-1">$1</div>');
  h = h.replace(/^---+$/gm, '<hr class="border-slate-200 my-2">');
  return h.replace(/\n/g, '<br>');
}

/* ---------- Toast ---------- */
function toast(msg, type='ok') {
  const style = type === 'ok'
    ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
    : 'bg-rose-50 border-rose-300 text-rose-700';
  const el = document.createElement('div');
  el.className = `toast border rounded-xl px-4 py-2.5 text-sm shadow-xl backdrop-blur ${style}`;
  el.textContent = msg;
  $('toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; setTimeout(() => el.remove(), 400); }, 3200);
}

/* ---------- 流水线舞台条 ---------- */
const STAGES = [
  { key:'分类员', label:'分类' }, { key:'摘要员', label:'摘要·互链' },
  { key:'质疑员', label:'对抗审查' }, { key:'组装员', label:'组装提案' }, { key:'审批', label:'人工审批' },
];
function renderStagebar(s) {
  const processing = s.items.find(i => i.status === 'processing');
  const latest = processing ? s.items.find(i => i.id === processing.id) : null;
  const fired = new Set();
  if (latest) {
    for (const e of s.events) if (e.item_id === latest.id) {
      for (const st of STAGES) if (e.agent.includes(st.key)) fired.add(st.key);
    }
  }
  const anyPendingApproval = s.proposals.some(p => p.status === 'pending');
  $('stagebar').innerHTML =
    `<span class="text-[10px] text-slate-600 mr-2 whitespace-nowrap rounded-full border border-slate-300 bg-white/80 px-2 py-1">${processing ? '⚡ 洞察织机治理中「' + esc(processing.title) + '」' : '洞察织机流水线待命'}</span>` +
    STAGES.map((st, i) => {
      const active = processing && fired.has(st.key);
      const isApproval = st.key === '审批';
      const lit = active || (isApproval && !processing && anyPendingApproval);
      const cfg = AGENTS[st.key] ? AGENT_COLORS[AGENTS[st.key].color] : {text:'text-amber-700'};
      const emoji = AGENTS[st.key] ? AGENTS[st.key].emoji : '✋';
      return `<div class="flex items-center gap-1 whitespace-nowrap">
        <div class="px-2.5 py-1 rounded-full border text-[11px] border-slate-300 text-slate-600 bg-white/80 ${lit ? 'stage-active border-sky-400 bg-sky-100 text-sky-700 stage-glow' : ''}">${emoji} ${st.label}</div>
        ${i < STAGES.length - 1 ? '<div class="w-4 h-px bg-slate-300"></div>' : ''}
      </div>`;
    }).join('');
}

/* ---------- 主渲染 ---------- */
function render(s) {
  $('llm-badge').textContent = s.llm.mock ? 'LLM: MOCK 模式' : `LLM: ${s.llm.model}`;
  $('llm-badge').className = 'px-2.5 py-1 rounded-full border ' + (s.llm.mock ? 'bg-amber-50 text-amber-700 border-amber-300' : 'bg-emerald-50 text-emerald-700 border-emerald-300');
  renderStagebar(s);

  // Agent 图例
  $('agent-legend').innerHTML = Object.entries(AGENTS).map(([name, cfg]) => {
    const c = AGENT_COLORS[cfg.color];
    return `<span class="text-[10px] px-2 py-0.5 rounded-full border ${c.chip} shadow-sm shadow-slate-950/40">${cfg.emoji} ${name}</span>`;
  }).join('');

  // 队列
  $('item-count').textContent = `(${s.items.length})`;
  $('items').innerHTML = s.items.map(i => {
    const [label, cls] = ITEM_STATUS[i.status] || [i.status,'bg-slate-100 text-slate-600'];
    return `<div class="flex items-center gap-2 text-sm bg-white/88 border border-slate-200 rounded-xl px-3 py-2.5 fade-in hover:border-slate-300 hover:bg-white transition">
      <span class="truncate flex-1">${esc(i.title)}</span>
      <span class="text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${cls}">${label}</span></div>`;
  }).join('') || `<div class="text-xs text-slate-500 border border-dashed border-slate-300 rounded-lg px-3 py-6 text-center">📭 还没有待治理内容<br>把想收藏的文章粘贴到左边开始</div>`;

  // 事件流:Agent 配色头像 + 时间线
  $('events').innerHTML = s.events.map(e => {
    const cfg = agentStyle(e.agent);
    const c = AGENT_COLORS[cfg.color] || SLATE;
    const time = new Date(e.created_at * 1000).toLocaleTimeString('zh-CN',{hour12:false});
    const level = LEVEL_BORDER[e.level] || LEVEL_BORDER.info;
    return `<div class="flex gap-2.5 fade-in rounded-xl border border-slate-200 bg-white/90 px-2 py-2 ${level} border-l-2 hover:border-slate-300 transition">
      <div class="flex flex-col items-center pt-0.5">
        <div class="w-7 h-7 rounded-full grid place-items-center text-sm bg-slate-50 border border-slate-300 ${c.text}">${cfg.emoji}</div>
        <div class="w-px flex-1 bg-slate-300 mt-1"></div>
      </div>
      <div class="flex-1 pb-2 min-w-0">
        <div class="flex justify-between items-baseline gap-2">
          <span class="text-xs font-medium ${c.text}">${esc(e.agent.replace(cfg.emoji,'').trim())}</span>
          <span class="text-[10px] text-slate-600">${time}</span>
        </div>
        <div class="text-xs text-slate-500 leading-relaxed break-words">「<span class="text-slate-700">${esc(e.item_title || '')}</span>」${esc(e.message)}</div>
      </div></div>`;
  }).join('') || `<div class="text-xs text-slate-500 border border-dashed border-slate-300 rounded-lg px-3 py-6 text-center">🤖 洞察织机馆员待命中…<br>投递内容后可以看到治理实况</div>`;

  // 审批台
  const pending = s.proposals.filter(p => p.status==='pending');
  $('approval-count').textContent = pending.length ? `${pending.length} ${COPY.proposalPendingSuffix}` : '';
  $('proposals').innerHTML = s.proposals.map(p => {
    if (p.status==='pending') {
      const verdict = VERDICT_THEME[p.verdict] || VERDICT_THEME.default;
      return `<div class="border border-amber-300 bg-amber-50/55 rounded-xl p-3 fade-in hover:border-amber-400 transition shadow-sm shadow-amber-100/70">
        <div class="flex justify-between items-center mb-2 text-xs">
          <span class="text-amber-700 font-mono">#${p.id} → vault/${esc(p.filepath)}</span>
          <span class="${verdict[1]}">${verdict[0]}</span>
        </div>
        <div class="text-[11px] leading-relaxed text-slate-600 max-h-48 overflow-y-auto bg-white/90 rounded-lg p-2.5 border border-slate-200">${p.kind==='link_suggestion' ? mdLite(p.markdown) : mdLite(p.markdown)}</div>
        <div class="flex gap-2 mt-2.5">
          <button onclick="act(${p.id},'approve')" class="flex-1 bg-emerald-700 hover:bg-emerald-600 border border-emerald-500/30 text-white rounded-lg py-1.5 text-xs font-medium transition shadow-sm shadow-emerald-950/40">${COPY.proposalApprove}</button>
          <button onclick="act(${p.id},'reject')" class="flex-1 bg-white hover:bg-rose-50 border border-slate-300 hover:border-rose-300 text-slate-700 rounded-lg py-1.5 text-xs transition">${COPY.proposalReject}</button>
        </div></div>`;
    }
    const [label, cls] = PROPOSAL_STATUS_THEME[p.status] || PROPOSAL_STATUS_THEME.rejected;
    return `<div class="border border-slate-200 bg-white/70 rounded-lg px-3 py-2 text-xs flex justify-between fade-in opacity-80">
      <span class="font-mono text-slate-500">#${p.id} ${esc(p.filepath)}</span><span class="${cls}">${label}</span></div>`;
  }).join('') || `<div class="text-xs text-slate-500 border border-dashed border-slate-300 rounded-lg px-3 py-6 text-center">🕘 暂无待审批提案<br>洞察织机的每笔修改都会先到这里等你确认</div>`;

  // vault
  $('vault').innerHTML = s.vault.map(f =>
    `<span class="text-xs bg-white/90 border border-slate-200 hover:border-sky-300 rounded-full px-3 py-1 font-mono transition">📄 ${esc(f)}</span>`
  ).join('') || '<span class="text-xs text-slate-600">空</span>';
}

/* ---------- 轮询与动作 ---------- */
async function poll(){
  try {
    const r = await fetch('/api/state');
    render(await r.json());
  } catch(e) { /* server restarting */ }
}

async function act(pid, action){
  try {
    const r = await fetch(`/api/proposals/${pid}/${action}`, {method:'POST'});
    const d = await r.json();
    if (action === 'approve') toast(d.kind === 'link_suggestion' ? COPY.toastLinkUpdated(d.file) : COPY.toastIngested(d.file));
    else toast(COPY.toastRejected, 'warn');
  } catch(e) { toast('操作失败,请重试', 'warn'); }
  poll();
}

/* ---------- 简报 ---------- */
function switchTab(tab){
  $('view-workbench').classList.toggle('hidden', tab !== 'workbench');
  $('view-digest').classList.toggle('hidden', tab !== 'digest');
  $('view-graph').classList.toggle('hidden', tab !== 'graph');
  $('tab-workbench').className = TAB_BASE + (tab==='workbench' ? ' bg-sky-600 text-white shadow-sm shadow-sky-400/40' : ' text-slate-500 hover:text-slate-700 hover:bg-slate-100');
  $('tab-graph').className = TAB_BASE + (tab==='graph' ? ' bg-sky-600 text-white shadow-sm shadow-sky-400/40' : ' text-slate-500 hover:text-slate-700 hover:bg-slate-100');
  $('tab-digest').className = TAB_BASE + (tab==='digest' ? ' bg-sky-600 text-white shadow-sm shadow-sky-400/40' : ' text-slate-500 hover:text-slate-700 hover:bg-slate-100');
  if (tab === 'digest') fetchDigest();
  if (tab === 'graph') { if (!G.inited) initGraph(); else if (!G.raf) loopGraph(); }
}

/* ============ 知识图谱:canvas 力导向 ============ */
const G = { nodes: [], links: [], byId: {}, unresolved: [], inited: false, sel: null, hover: null, drag: null, raf: 0, alpha: 0.4, dpr: 1, bound: false };

async function initGraph(){
  const cv = $('graph-canvas');
  try {
    const r = await fetch('/api/graph').then(x => x.json());
    if (!r.ok || !r.nodes.length) throw new Error(r.reason || 'empty');
    G.nodes = r.nodes.map((n, i) => {
      const a = (i / Math.max(1, r.nodes.length)) * Math.PI * 2;
      return { ...n, x: 0.5 + Math.cos(a) * (0.2 + 0.012 * n.degree), y: 0.5 + Math.sin(a) * (0.28 + 0.015 * n.degree), vx: 0, vy: 0, r: 7 + Math.min(14, n.degree * 2.4) };
    });
    G.byId = {}; G.nodes.forEach(n => G.byId[n.id] = n);
    G.links = r.links.map(l => ({ s: G.byId[l.source], t: G.byId[l.target] })).filter(l => l.s && l.t);
    G.unresolved = r.unresolved || [];
    G.sel = null; G.alpha = 0.5; G.inited = true;
    renderGraphInfo();
    $('graph-meta').textContent = `${G.nodes.length} 篇笔记 · ${G.links.length} 条双链`;
    const ul = $('graph-unresolved-list');
    ul.innerHTML = G.unresolved.slice(0, 12).map(u => `<div>「${esc(u.from)}」→ <span class="text-amber-600">${esc(u.to)}</span></div>`).join('');
    $('graph-unresolved').classList.toggle('hidden', !G.unresolved.length);
    if (!G.bound) { bindGraphEvents(cv); G.bound = true; }
    if (!G.raf) loopGraph();
  } catch (e) {
    $('graph-meta').textContent = '图谱加载失败:' + (e.message || e);
  }
}

function bindGraphEvents(cv){
  const pos = ev => { const b = cv.getBoundingClientRect(); return { x: (ev.clientX - b.left) / b.width, y: (ev.clientY - b.top) / b.height }; };
  const hit = p => {
    const W = cv.clientWidth, H = cv.clientHeight;
    let best = null, bd = 1e9;
    for (const n of G.nodes) {
      const dx = n.x * W - p.x * W, dy = n.y * H - p.y * H, d = dx * dx + dy * dy;
      if (d < (n.r + 6) ** 2 && d < bd) { bd = d; best = n; }
    }
    return best;
  };
  cv.addEventListener('pointerdown', ev => {
    const p = pos(ev); const n = hit(p);
    if (n) { G.drag = { n, moved: 0 }; cv.setPointerCapture(ev.pointerId); }
    else { G.sel = null; renderGraphInfo(); }
    G.alpha = Math.max(G.alpha, 0.25);
  });
  cv.addEventListener('pointermove', ev => {
    const p = pos(ev);
    if (G.drag) { G.drag.n.x = Math.max(0.02, Math.min(0.98, p.x)); G.drag.n.y = Math.max(0.03, Math.min(0.97, p.y)); G.drag.n.vx = G.drag.n.vy = 0; G.drag.moved++; }
    else { G.hover = hit(p); cv.style.cursor = G.hover ? 'pointer' : 'grab'; }
  });
  cv.addEventListener('pointerup', () => {
    if (G.drag && G.drag.moved < 4) { G.sel = G.drag.n; renderGraphInfo(); }
    G.drag = null;
  });
  window.addEventListener('resize', () => { if (G.inited && G.raf) fitGraphCanvas(); });
}

function fitGraphCanvas(){ const cv = $('graph-canvas'); G.dpr = window.devicePixelRatio || 1; cv.width = cv.clientWidth * G.dpr; cv.height = cv.clientHeight * G.dpr; }

function loopGraph(){
  const cv = $('graph-canvas');
  const step = () => {
    if ($('view-graph').classList.contains('hidden')) { G.raf = 0; return; }
    fitGraphCanvas();
    tickGraph(cv.clientWidth, cv.clientHeight);
    drawGraph(cv);
    G.raf = requestAnimationFrame(step);
  };
  G.raf = requestAnimationFrame(step);
}

function tickGraph(W, H){
  G.alpha = Math.max(0.015, G.alpha * 0.995);
  const a = G.alpha;
  for (let i = 0; i < G.nodes.length; i++) for (let j = i + 1; j < G.nodes.length; j++) {
    const n1 = G.nodes[i], n2 = G.nodes[j];
    let dx = n2.x - n1.x, dy = n2.y - n1.y;
    let d2 = dx * dx + dy * dy || 1e-6;
    if (d2 > 0.25) continue;
    const f = Math.min(0.05, 0.0024 / d2) * a, d = Math.sqrt(d2);
    dx /= d; dy /= d;
    n1.vx -= dx * f; n1.vy -= dy * f; n2.vx += dx * f; n2.vy += dy * f;
  }
  for (const l of G.links) {
    const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.hypot(dx, dy) || 1e-6;
    const f = (d - 0.17) * 0.07 * a;
    const ux = dx / d, uy = dy / d;
    l.s.vx += ux * f; l.s.vy += uy * f; l.t.vx -= ux * f; l.t.vy -= uy * f;
  }
  for (const n of G.nodes) {
    n.vx += (0.5 - n.x) * 0.004 * a; n.vy += (0.5 - n.y) * 0.006 * a;
    n.vx *= 0.86; n.vy *= 0.86;
    if (G.drag && G.drag.n === n) continue;
    n.x = Math.min(0.98, Math.max(0.02, n.x + n.vx)); n.y = Math.min(0.97, Math.max(0.03, n.y + n.vy));
  }
}

function drawGraph(cv){
  const ctx = cv.getContext('2d'); const W = cv.clientWidth, H = cv.clientHeight;
  const dark = document.body.classList.contains('dark-theme');
  ctx.setTransform(G.dpr, 0, 0, G.dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const neigh = new Set();
  if (G.sel) { neigh.add(G.sel.id); for (const l of G.links) { if (l.s === G.sel) neigh.add(l.t.id); if (l.t === G.sel) neigh.add(l.s.id); } }
  for (const l of G.links) {
    const on = !G.sel || (l.s === G.sel || l.t === G.sel);
    ctx.strokeStyle = on ? (dark ? 'rgba(56,189,248,.75)' : 'rgba(14,165,233,.6)') : (dark ? 'rgba(148,163,184,.12)' : 'rgba(100,116,139,.16)');
    ctx.lineWidth = on ? 1.7 : 1;
    ctx.beginPath(); ctx.moveTo(l.s.x * W, l.s.y * H); ctx.lineTo(l.t.x * W, l.t.y * H); ctx.stroke();
  }
  for (const n of G.nodes) {
    const dim = G.sel && !neigh.has(n.id);
    const R = n.r * (G.hover === n || G.sel === n ? 1.22 : 1);
    const g = ctx.createRadialGradient(n.x * W - R * 0.3, n.y * H - R * 0.3, 1, n.x * W, n.y * H, R);
    if (dim) { g.addColorStop(0, dark ? '#475569' : '#94a3b8'); g.addColorStop(1, dark ? '#1e293b' : '#cbd5e1'); }
    else if (n.degree >= 4) { g.addColorStop(0, '#7dd3fc'); g.addColorStop(1, '#0284c7'); }
    else { g.addColorStop(0, '#a5b4fc'); g.addColorStop(1, '#4f46e5'); }
    ctx.globalAlpha = dim ? 0.35 : 1;
    ctx.beginPath(); ctx.arc(n.x * W, n.y * H, R, 0, 7); ctx.fillStyle = g; ctx.fill();
    if (G.sel === n) { ctx.beginPath(); ctx.arc(n.x * W, n.y * H, R + 3.5, 0, 7); ctx.strokeStyle = dark ? '#38bdf8' : '#0ea5e9'; ctx.lineWidth = 2; ctx.stroke(); }
    ctx.font = `${G.sel === n ? '600 ' : ''}${11 + Math.min(4, n.degree)}px system-ui, -apple-system, "PingFang SC", sans-serif`;
    ctx.fillStyle = dim ? (dark ? 'rgba(148,163,184,.4)' : 'rgba(100,116,139,.4)') : (dark ? '#e2e8f0' : '#334155');
    const label = n.title.length > 12 ? n.title.slice(0, 11) + '…' : n.title;
    ctx.fillText(label, n.x * W - ctx.measureText(label).width / 2, n.y * H + R + 14);
    ctx.globalAlpha = 1;
  }
}

function renderGraphInfo(){
  const box = $('graph-info'), title = $('graph-info-title');
  if (!G.sel) {
    title.textContent = '选中一个节点';
    box.innerHTML = '<p class="text-xs text-slate-500 leading-relaxed">节点 = 已入库笔记;连线 = [[双链]]。点大小随连接数增长,亮蓝 = 枢纽节点。未入库的链接目标会列在下方。</p>';
    return;
  }
  const n = G.sel;
  const neighbors = G.links.filter(l => l.s === n || l.t === n).map(l => (l.s === n ? l.t : l.s)).sort((a, b) => b.degree - a.degree);
  title.textContent = n.title;
  box.innerHTML = `
    <p class="text-xs text-slate-500">${esc(n.file)} · ${n.degree} 条连接</p>
    <div class="flex flex-wrap gap-1.5 pt-1">
      ${neighbors.map(m => `<button onclick="focusNode(this.dataset.id)" data-id="${esc(m.id)}" class="text-xs px-2 py-1 rounded-lg border border-sky-200 bg-sky-50 hover:bg-sky-100 text-sky-700 dark:border-sky-800 dark:bg-sky-900/30 dark:text-sky-300 transition">${esc(m.title)}</button>`).join('') || '<span class="text-xs text-slate-400">暂无邻居(孤岛笔记)</span>'}
    </div>`;
}

function focusNode(id){ const n = G.byId[id]; if (n) { G.sel = n; renderGraphInfo(); G.alpha = Math.max(G.alpha, 0.2); } }

/* ============ 书签采集(bookmarklet,弹窗导航方案) ============ */
/* 说明:现代 Chrome 的私有网络管控(PNA)会拦截公网页面向 127.0.0.1 的 fetch,
   因此用 window.open 顶级导航到 /collect 收件页——不受 CORS/PNA 限制,全浏览器可靠。 */
function bookmarkletCode(){
  const origin = location.origin;
  return `(function(){try{var s=String(window.getSelection()||'');var m=document.querySelector('meta[name="description"]');var c=s||(m&&m.content?m.content:document.body.innerText.slice(0,1500));var q='title='+encodeURIComponent(document.title.slice(0,200))+'&content='+encodeURIComponent(c.slice(0,1500))+'&url='+encodeURIComponent(location.href);var w=window.open('${origin}/collect?'+q,'insightloom_collect','width=380,height=260');if(!w)alert('弹窗被拦截:请允许本站弹窗后重试')}catch(e){alert('脚本异常: '+e)}})()`;
}
function initBookmarklet(){
  const a = document.getElementById('bookmarklet-link');
  if (a) a.href = 'javascript:' + encodeURIComponent(bookmarkletCode());
}
function copyBookmarklet(){
  const code = 'javascript:' + bookmarkletCode();
  navigator.clipboard.writeText(decodeURIComponent(code)).then(() => {
    const b = event?.target; const old = b?.textContent;
    if (b) { b.textContent = '已复制 ✓ 去书签管理器粘贴'; setTimeout(() => b.textContent = old, 2600); }
  }).catch(() => alert('复制失败,请手动拖拽按钮到书签栏'));
}

async function fetchDigest(){
  try {
    const d = await (await fetch('/api/digest')).json();
    const cards = [
      ['📥 24h 投递', d.stats_24h.items, 'text-sky-600'],
      ['✅ 24h 纳入知库', d.stats_24h.approved, 'text-emerald-600'],
      ['🕘 待审批', d.stats_24h.pending, 'text-amber-600'],
      ['📚 库存笔记', d.vault.total, 'text-violet-600'],
    ];
    $('digest-cards').innerHTML = cards.map(([label, val, cls]) => `
      <div class="glass-panel rounded-2xl p-4 hover:border-slate-600/80 transition panel-hover">
        <div class="text-2xl font-bold ${cls}">${val}</div>
        <div class="text-xs text-slate-500 mt-1">${label}</div></div>`).join('');
    const ISSUE = {
      orphan: ['🏝️ 孤立','border-amber-300 text-amber-700'],
      stale: ['⏳ 疑似过时','border-slate-300 text-slate-600'],
      thin: ['🪶 薄弱','border-slate-300 text-slate-600'],
    };
    $('digest-findings').innerHTML = d.findings.length
      ? d.findings.map(f => {
          const [label, cls] = ISSUE[f.type] || [f.type,'border-slate-300 text-slate-600'];
          return `<div class="text-xs border rounded-lg px-3 py-2 bg-white/90 ${cls} hover:border-slate-400 transition">
            <span class="font-medium">${label}</span>
            <span class="font-mono text-slate-400">${esc(f.note)}</span>
            <div class="text-slate-500 mt-0.5">${esc(f.detail)}</div></div>`;
        }).join('')
      : '<p class="text-xs text-emerald-600">🌻 巡库无异常,知识库健康</p>';
    $('digest-tags').innerHTML = d.top_tags.length
      ? d.top_tags.map(t => `<span class="text-xs bg-white/90 border border-slate-200 rounded-full px-3 py-1 hover:border-sky-300 transition">${esc(t.tag)} <span class="text-slate-500">×${t.count}</span></span>`).join('')
      : '<p class="text-xs text-slate-600">暂无标签</p>';
  } catch(e) {}
}

async function runGardener(){
  try {
    const r = await (await fetch('/api/garden/run', {method:'POST'})).json();
    toast(`🌻 巡库完成:${r.total_notes} 篇 · ${r.findings.length} 个发现 · ${r.proposals_created} 条双链提案`);
    fetchDigest();
  } catch(e) { toast('巡库失败', 'warn'); }
}

$('inbox-form').addEventListener('submit', async e => {
  e.preventDefault();
  const body = { title: $('f-title').value.trim(), url: $('f-url').value.trim(), content: $('f-content').value };
  if (!body.title) return;
  setInboxSubmitting(true);
  try {
    const r = await fetch('/api/inbox', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    if (!r.ok) throw new Error(`submit_failed_${r.status}`);
    toast(COPY.toastInboxQueued);
    e.target.reset();
    clearInboxDraft();
    poll();
  } catch (_) {
    toast(COPY.toastInboxFailed, 'warn');
  } finally {
    setInboxSubmitting(false);
  }
});

const themeToggleBtn = $('theme-toggle');
if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', toggleTheme);
}

applyTheme(readThemePreference());
bindSystemThemeListener();
bindInboxEnhancements();
setInboxSubmitting(false);

/* ---------- 知识库检索 / 问答 ---------- */
async function doSearch(){
  const q = $('search-q').value.trim();
  if (!q) return;
  const box = $('search-results');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="feature-tile fade-in">🔍 语义检索中…(本地嵌入)</div>';
  try {
    const d = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
    if (!d.results?.length) {
      box.innerHTML = '<div class="feature-tile">📭 没有命中。试试换个说法,或先投递一些材料、运行一次索引重建。</div>';
      return;
    }
    box.innerHTML = d.results.map(r => `
      <div class="feature-tile fade-in">
        <div class="flex justify-between gap-2">
          <span class="font-medium text-slate-700">📘 ${esc(r.title)} <span class="text-slate-400">§ ${esc(r.section)}</span></span>
          <span class="text-[10px] text-slate-400 whitespace-nowrap">${r.score}</span>
        </div>
        <div class="text-slate-500 mt-1 text-[11px] leading-relaxed">${esc(r.snippet)}…</div>
      </div>`).join('');
  } catch(e) {
    box.innerHTML = '<div class="feature-tile">检索失败,请确认服务正常。</div>';
  }
}

async function doAsk(){
  const q = $('search-q').value.trim();
  if (!q) return;
  const box = $('search-results');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="feature-tile fade-in">✨ 正在从知识库检索相关小节并组织回答…</div>';
  try {
    const d = await (await fetch('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question: q})})).json();
    const cites = (d.citations || []).map(c => `<span class="wikilink">${esc(c)}</span>`).join(' ');
    box.innerHTML = `
      <div class="feature-tile fade-in">
        <div class="text-slate-700 leading-relaxed">${esc(d.answer)}</div>
        ${cites ? `<div class="mt-2 flex flex-wrap gap-1.5">${cites}</div>` : ''}
      </div>`;
  } catch(e) {
    box.innerHTML = '<div class="feature-tile">回答生成失败,请重试。</div>';
  }
}

$('search-q').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); doSearch(); } });

initBookmarklet();
poll();
setInterval(poll, 2000);
