import fs from 'node:fs';
import path from 'node:path';
import { marked } from 'marked';

const here = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(here, '..');
const bookDir = path.join(root, 'book');
const chapterDir = path.join(bookDir, 'chapters');
const outDir = path.join(here, 'chapters');
const assetsDir = path.join(here, 'assets');
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(assetsDir, { recursive: true });

marked.setOptions({ gfm: true, breaks: false });

const summary = fs.readFileSync(path.join(bookDir, 'SUMMARY.md'), 'utf8');
const chapterMatches = [...summary.matchAll(/^\d+\. \[([^\]]+)\]\(chapters\/([^)]+)\)/gm)];
const appendixMatches = [...summary.matchAll(/^- \[([^\]]+)\]\(chapters\/([^)]+)\)/gm)];
const items = [...chapterMatches, ...appendixMatches].map((m, i) => ({
  title: m[1],
  file: m[2],
  slug: m[2].replace(/\.md$/, ''),
  label: i < chapterMatches.length ? String(i).padStart(2, '0') : String.fromCharCode(65 + i - chapterMatches.length),
  appendix: i >= chapterMatches.length,
}));
if (items.length !== 20) throw new Error(`Expected 20 chapters, found ${items.length}`);

const escapeHtml = (s) => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const plain = (md) => md
  .replace(/<figure[\s\S]*?<\/figure>/g, ' ')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/`([^`]+)`/g, '$1')
  .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  .replace(/^#{1,6}\s+/gm, '')
  .replace(/[>*_|]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();
const slugify = (s) => s.replace(/<[^>]+>/g, '').trim().toLowerCase()
  .replace(/[^\p{Letter}\p{Number}]+/gu, '-').replace(/^-|-$/g, '') || 'section';

function renderMarkdown(md) {
  let html = marked.parse(md);
  const ids = new Map();
  html = html.replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (_, level, inside) => {
    const base = slugify(inside); const n = ids.get(base) || 0; ids.set(base, n + 1);
    const id = n ? `${base}-${n + 1}` : base;
    return `<h${level} id="${id}">${inside}<a class="anchor" href="#${id}" aria-label="链接到本节">#</a></h${level}>`;
  });
  html = html.replace(/<table>/g, '<div class="table-wrap"><table>').replace(/<\/table>/g, '</table></div>');
  return html;
}

const records = items.map((item) => {
  const md = fs.readFileSync(path.join(chapterDir, item.file), 'utf8');
  const bodyMd = md.replace(/^# .+\n/, '');
  const text = plain(bodyMd);
  const description = text.slice(0, 120);
  const html = renderMarkdown(bodyMd);
  const headings = [...html.matchAll(/<h2 id="([^"]+)">([\s\S]*?)<a class="anchor"/g)].map(m => ({
    id: m[1], title: m[2].replace(/<[^>]+>/g, ''),
  }));
  return {...item, md, html, text, description, headings, href: `chapters/${item.slug}.html`};
});

function topbar(prefix = '') {
  return `<div class="progress" aria-hidden="true"></div>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar">
  <a class="brand" href="${prefix}index.html"><span class="brand-mark">LC×LG</span><span>LangChain × LangGraph</span></a>
  <nav class="tools" aria-label="阅读工具">
    <a class="tool-button" href="${prefix}search.html" aria-label="搜索">搜索</a>
    <button class="tool-button" data-font-down aria-label="减小字号">A−</button>
    <button class="tool-button" data-font-up aria-label="增大字号">A+</button>
    <button class="tool-button" data-theme><span class="theme-label">深色</span></button>
    <button class="tool-button" data-menu-open aria-label="打开目录">目录</button>
  </nav>
</header>`;
}

function menu(prefix = '') {
  return `<dialog class="menu-panel" data-menu-panel>
  <div class="menu-head"><span>全书目录</span><button class="tool-button" data-menu-close>关闭</button></div>
  <nav class="menu-list">${records.map(r => `<a href="${prefix}${r.href}"><span>${r.label}</span>${escapeHtml(r.title)}</a>`).join('')}</nav>
</dialog>`;
}

function shell({title, body, prefix = '', chapter = false, extraScripts = ''}) {
  return `<!doctype html>
<html lang="zh-CN" data-theme="auto"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="description" content="LangChain 与 LangGraph 源码驱动中文电子书">
<title>${escapeHtml(title)} · LangChain × LangGraph</title>
<link rel="stylesheet" href="${prefix}assets/reader.css">
</head><body data-chapter="${chapter}">
${topbar(prefix)}${body}${menu(prefix)}
<footer class="site-footer">基于官方源码快照独立撰写 · LangChain 1.4.2 · LangGraph 1.2.12</footer>
<script src="${prefix}assets/reader.js"></script>${extraScripts}
</body></html>`;
}

const descriptions = {
  '00-preface':'范围、版本与阅读路线', '01-two-layers':'框架分层与职责边界',
  '02-loop-from-scratch':'用标准库看清模型工具循环', '03-messages':'工具、多模态与流式背后的协议',
  '04-tools':'Schema、权限、副作用与 ToolNode', '05-runnables':'统一调用、组合、重试和配置传播',
  '06-create-agent':'拆解 Agent 工厂生成的图', '07-stategraph':'State、Node、Edge 与 reducer',
  '08-control-flow':'条件边、Command、Send 与循环', '09-pregel':'Plan、Execution、Update 三阶段',
  '10-persistence':'Checkpoint 与 Store 的生命周期', '11-interrupts':'暂停、恢复、重放与人工审批',
  '12-streaming':'消息、更新、状态与事件流', '13-subgraphs':'上下文隔离与多 Agent 模式',
  '14-project':'观测申请的研究、修订与审批', '15-production':'测试、升级与故障定位',
  'appendix-glossary':'术语、模板与故障速查', 'appendix-sources':'官方材料、快照与原创说明'
};

for (let i = 0; i < records.length; i++) {
  const r = records[i], prev = records[i - 1], next = records[i + 1];
  const rail = `<aside class="chapter-rail"><div class="rail-label">${r.appendix ? 'Appendix' : `Chapter ${r.label}`}</div><div class="rail-title">${escapeHtml(r.title)}</div><ol>${r.headings.map(h => `<li><a href="#${h.id}">${escapeHtml(h.title)}</a></li>`).join('')}</ol></aside>`;
  const nav = `<nav class="chapter-nav" aria-label="章节导航">${prev ? `<a href="${prev.slug}.html"><small>上一章</small><strong>${escapeHtml(prev.title)}</strong></a>` : ''}${next ? `<a class="next" href="${next.slug}.html"><small>下一章</small><strong>${escapeHtml(next.title)}</strong></a>` : ''}</nav>`;
  const body = `<main id="main" class="reader-layout">${rail}<article class="chapter"><header class="chapter-head"><div class="chapter-number">${r.appendix ? `附录 ${r.label}` : `第 ${r.label} 章`}</div><h1>${escapeHtml(r.title)}</h1><div class="chapter-meta">源码快照 2026-09-22 · 约 ${Math.ceil(r.text.length / 500) * 2} 分钟</div></header><div class="prose">${r.html}</div>${nav}</article></main>`;
  fs.writeFileSync(path.join(outDir, `${r.slug}.html`), shell({title:r.title, body, prefix:'../', chapter:true}));
}

const chapterRows = records.map(r => `<a class="chapter-row" href="${r.href}"><span class="chapter-no">${r.label}</span><span><h3>${escapeHtml(r.title)}</h3><p>${escapeHtml(descriptions[r.slug] || r.description)}</p></span><span class="arrow">→</span></a>`).join('');
const home = `<main id="main">
<section class="hero"><div><p class="kicker">Source guided field book</p><h1>从工具调用到<br><em>可恢复 Agent</em></h1><p class="dek">跟踪一份天文台申请如何读取资料、计算观测预算、等待审核并完成修订。沿状态与消息核对组件协议、图执行和恢复边界。</p></div>
<aside class="hero-aside"><strong>用执行结果核验理解</strong>章节顺序保持不变，正文、图表和两个示例程序重新编写。离线轨迹演示控制流，不冒充真实模型或望远镜测试。<dl class="snapshot"><dt>LC</dt><dd>877ad8c7bfa3</dd><dt>LG</dt><dd>1afaca35a0d4</dd><dt>DATE</dt><dd>2026-09-22</dd></dl></aside></section>
<section class="home-grid"><aside class="home-intro"><h2>全书 18 章 + 2 附录</h2><p>先从无框架循环建立直觉，再下沉到运行时，最后用工程检查表收束。</p><a href="chapters/00-preface.html">开始阅读 →</a><br><a href="search.html">全文搜索 →</a></aside><div class="contents">${chapterRows}</div></section></main>`;
fs.writeFileSync(path.join(here, 'index.html'), shell({title:'目录', body:home}));

const searchBody = `<main id="main" class="search-page"><p class="kicker">Full text index</p><h1>查一个概念，<br>回到执行路径。</h1><label for="search" class="skip">搜索全书</label><input id="search" class="search-input" type="search" autocomplete="off" placeholder="reducer / interrupt / 工具权限"><section id="results" aria-live="polite"><p class="search-hint">输入 API、概念或错误现象，例如 reducer、interrupt、重复副作用。</p></section></main>`;
const searchIndex = records.map(r => ({number:r.label,title:r.title,href:r.href,text:r.text}));
fs.writeFileSync(path.join(assetsDir, 'search-index.json'), JSON.stringify(searchIndex, null, 2));
fs.writeFileSync(path.join(assetsDir, 'search-index.js'), `window.BOOK_SEARCH=${JSON.stringify(searchIndex)};\n`);
fs.writeFileSync(path.join(here, 'search.html'), shell({title:'搜索', body:searchBody, extraScripts:'<script src="assets/search-index.js"></script><script src="assets/search.js"></script>'}));

// A chapter fragment needs its own ID namespace in the combined volume.
function volumeHtml(record) {
  const prefix = record.slug + '--';
  return record.html.replace(/\bid="([^"]+)"/g, (_, id) => `id="${prefix}${id}"`)
    .replace(/href="#([^"]+)"/g, (_, id) => `href="#${prefix}${id}"`)
    .replace(/aria-labelledby="([^"]+)"/g, (_, ids) =>
      `aria-labelledby="${ids.split(/\s+/).map(id => prefix + id).join(' ')}"`);
}
const combined = records.map(r => `<section class="book-section"><header class="chapter-head"><div class="chapter-number">${r.label}</div><h1>${escapeHtml(r.title)}</h1></header><div class="prose">${volumeHtml(r)}</div></section>`).join('');
fs.writeFileSync(path.join(here, 'book.html'), shell({title:'离线合订本', body:`<main id="main" class="reader-layout"><div></div><article class="chapter">${combined}</article></main>`, chapter:true}));

console.log(`Built ${records.length} chapters, index, search, and book.html`);
