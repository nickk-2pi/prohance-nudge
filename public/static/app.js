// Nudge front end: plain ES module, no build step. Regions re-render independently so typing never loses focus.

// ------------------------------------------------------------------ helpers
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hm = (m) => (m == null ? "—" : `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}`);
const parseHM = (s) => {
  const m = String(s).trim().match(/^(\d{1,2})(?::(\d{1,2}))?$/);
  return m ? +m[1] * 60 + +(m[2] || 0) : null;
};
const EMAIL_RE = /^[A-Za-z0-9._%+'\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$/;
const splitEmails = (s) => String(s || "").split(/[,;]/).map((x) => x.trim()).filter(Boolean);
const IRREGULAR = { person: "people" };
const plural = (n, w) => `${n} ${n === 1 ? w : IRREGULAR[w] || w + "s"}`;
const GRAPH_EXPLORER = "https://developer.microsoft.com/en-us/graph/graph-explorer";
const store = {
  get(k, d) { try { const v = localStorage.getItem("nudge." + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("nudge." + k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const ICONS = {
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  grid: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  skip: '<path d="m5 4 10 8-10 8V4zM19 5v14"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  rows: '<path d="M3 6h18M3 12h18M3 18h18"/>',
  key: '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  ext: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  sync: '<path d="M21 2v6h-6M3 22v-6h6"/><path d="M3.5 9a9 9 0 0 1 15-3.4L21 8M3 16l2.5 2.4A9 9 0 0 0 20.5 15"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
};
const ic = (n, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]}</svg>`;

const D = (iso) => new Date(iso + "T00:00:00");
const fmtLong = (iso) => D(iso).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const mailDate = (iso) => D(iso).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
const mailDateShort = (iso) => D(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
const clock = (ts) => new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const sameDay = (a, b) => a.toDateString() === b.toDateString();
function whenStr(ts) {
  if (!ts) return "";
  const d = new Date(ts), now = new Date(), y = new Date(now - 864e5);
  if (sameDay(d, now)) return clock(ts);
  if (sameDay(d, y)) return "yesterday " + clock(ts);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + ", " + clock(ts);
}
function ago(ts) {
  const s = (Date.now() - new Date(ts)) / 1000;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return whenStr(ts);
}
function left(expiresAt) {
  const m = Math.round((expiresAt * 1000 - Date.now()) / 60000);
  return m >= 90 ? `${Math.round(m / 60)} h left` : `${Math.max(m, 0)} min left`;
}

async function api(name, body = {}) {
  let r;
  try {
    r = await fetch("/api/" + name, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw Object.assign(new Error("Nudge isn't running. Start it again (Start Nudge shortcut) and reload."), { code: "offline" });
  }
  const j = await r.json().catch(() => ({ error: `Server returned ${r.status}` }));
  if (!r.ok) {
    const e = Object.assign(new Error(j.error || r.statusText), { code: j.code, status: r.status });
    if ((e.code === "token_expired" || e.code === "token_needed") && S.st) { S.st.token = null; renderTop(); renderBar(); renderPanel(); }
    throw e;
  }
  return j;
}

// ------------------------------------------------------------------ state
const S = {
  st: null, wb: null, ledger: [], latest: {}, edits: {}, byKey: {},
  view: store.get("view", "day"), day: store.get("day", null), filter: store.get("filter", "todo"), q: "",
  selByDay: {}, focus: null, anchor: null, tab: "preview",
  busy: {}, errors: {}, refreshing: false, modal: null,
  logFilter: "all", logQ: "", logOpen: null,
};
const thr = () => S.st.settings.threshold_min;
const tok = () => S.st?.token;
const canDraft = () => !!(S.st?.demo || S.st?.outlook?.installed);
const newOutlookOn = () => !S.st?.demo && !!S.st?.outlook?.new_outlook_on;
const NEW_OUTLOOK_HELP = "Emails open in classic Outlook. Turn off the “New Outlook” toggle (top right in Outlook) so classic Outlook opens them as new messages.";
const senderName = () => S.st.settings.sender_name || tok()?.name || "";
const curDay = () => S.wb?.days.find((d) => d.sheet === S.day);
const sel = () => (S.selByDay[S.day] ||= new Set());
const openDrafts = () => Object.values(S.latest).filter((e) => e.status === "drafted").length;

function indexLedger() {
  S.latest = {};
  for (const e of S.ledger) {
    if (e.status === "cleared" || e.status === "discarded") delete S.latest[e.key];
    else S.latest[e.key] = e;
  }
}
function addLedger(entries) { S.ledger.push(...entries); indexLedger(); }
function setWorkbook(wb) {
  S.wb = wb;
  S.byKey = {};
  for (const d of wb?.days || []) for (const c of d.candidates) S.byKey[c.key] = { c, d };
  if (!wb?.days.length) { S.day = null; return; }
  if (!curDay()) S.day = (wb.days.find((d) => dayCounts(d).todo) || wb.days[0]).sheet;
  if (S.focus && !S.byKey[S.focus]) S.focus = null;
}

// base status ignores the ledger; status includes it
function baseOf(c) {
  if (c.productive == null) return "unknown";
  if (c.productive >= thr()) return "ok";
  return c.productive === 0 && !c.logged ? "none" : "low";
}
const kindOf = (c) => (c.productive === 0 && !c.logged ? "none" : "low");
function statusOf(c) {
  const s = S.latest[c.key]?.status;
  return s === "sent" || s === "drafted" || s === "skipped" ? s : baseOf(c);
}
const isTodo = (st) => st === "low" || st === "none";
function dayCounts(d) {
  const n = { all: d.candidates.length, todo: 0, bLow: 0, bNone: 0, drafted: 0, sent: 0, skipped: 0 };
  for (const c of d.candidates) {
    const st = statusOf(c), b = baseOf(c);
    if (isTodo(st)) n.todo++;
    if (b === "low") n.bLow++;
    if (b === "none") n.bNone++;
    if (st in n) n[st]++;
  }
  return n;
}
const FILTERS = {
  todo: (c) => isTodo(statusOf(c)),
  low: (c) => baseOf(c) === "low",
  none: (c) => baseOf(c) === "none",
  drafted: (c) => statusOf(c) === "drafted",
  sent: (c) => statusOf(c) === "sent",
  all: () => true,
};
function dayWarnings(d) {
  return [...(d?.warnings || []).map((w) => ({ ...w, tab: d.sheet })), ...(S.wb?.warnings || [])];
}

// ------------------------------------------------------------------ the email
const topApps = (c, n = 3) => (c.apps || []).slice(0, n).map(([a, m]) => `${a} ${hm(m)}`).join(", ");
// durations for sentences: "4 hours", "1 hour 10 minutes", "29 minutes", "no time"
function hwords(m) {
  if (m == null) return "an unknown amount of time";
  const h = Math.floor(m / 60), mi = m % 60;
  const parts = [h && `${h} hour${h === 1 ? "" : "s"}`, mi && `${mi} minute${mi === 1 ? "" : "s"}`].filter(Boolean);
  return parts.join(" ") || "no time";
}
function vars(c, d) {
  const t = thr(), short = Math.max(0, t - (c.productive || 0));
  return {
    first_name: c.first_name, name: c.name, date: mailDate(d.date), date_short: mailDateShort(d.date),
    productive: hm(c.productive), threshold: hm(t), shortfall: hm(short),
    productive_words: hwords(c.productive), threshold_words: hwords(t), shortfall_words: hwords(short),
    logged: hm(c.logged), idle: hm(c.idle), top_apps: topApps(c) || "no apps recorded",
    sender_name: senderName(), sheet: d.sheet,
  };
}
const VAR_NAMES = ["first_name", "name", "date", "date_short", "productive_words", "threshold_words", "shortfall_words", "productive", "threshold", "shortfall", "logged", "idle", "top_apps", "stats", "apps", "sender_name"];
const BLOCKS = ["stats", "apps"];
const fill = (s, v) => s.replace(/\{(\w+)\}/g, (m, k) => (BLOCKS.includes(k) ? m : k in v ? v[k] : m));
function baseDraft(c, d, tpl) {
  tpl ||= S.st.settings.templates[kindOf(c)];
  const v = vars(c, d);
  return { to: joinAddrs([ownEmail(c)], S.st.settings.to_also || []), cc: joinAddrs(S.st.settings.cc || []),
    subject: fill(tpl.subject, v), body: fill(tpl.body, v) };
}
function draftFor(c, d = S.byKey[c.key].d) {
  const ov = S.edits[c.key];
  return { ...baseDraft(c, d), ...(ov || {}), edited: !!ov && Object.keys(ov).length > 0 };
}
const toValid = (dr) => { const t = splitEmails(dr.to); return t.length > 0 && t.every((e) => EMAIL_RE.test(e)); };
// the candidate's address: the email directory's (Settings) first, then a fix chosen for a typo in the sheet's
// address (saved with the person's edits), then the sheet's
const ownEmail = (c) => (c.email_source === "directory" ? c.email : S.edits[c.key]?.email || c.email);
// everyone in the tracker the directory doesn't list
function notInDirectory() {
  const names = new Map();
  for (const d of S.wb?.days || []) for (const c of d.candidates) if (c.email_source !== "directory") names.set(c.name.toLowerCase(), c.name);
  return [...names.values()].sort();
}
// the candidate's flagged address is still in To (the extra To recipients don't matter here)
const issueOpen = (c, dr) => !!c.email_issue && splitEmails(dr.to).some((e) => e.toLowerCase() === (c.email || "").toLowerCase());
function joinAddrs(...lists) {
  const seen = new Set(), out = [];
  for (const a of lists.flat()) { const k = String(a || "").trim(); if (k && !seen.has(k.toLowerCase())) { seen.add(k.toLowerCase()); out.push(k); } }
  return out.join(", ");
}
const canSelect = (c) => !["sent", "drafted"].includes(statusOf(c)) && toValid(draftFor(c));

function statsHtml(c) {
  const t = thr();
  const cells = [["Productive", hm(c.productive), (c.productive ?? 0) < t ? "#b42318" : "#1f2328"], ["Expected", hm(t)]];
  if (c.logged != null) cells.push(["Logged in", hm(c.logged)]);
  if (c.idle != null) cells.push(["Idle", hm(c.idle)]);
  return `<table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:separate;border:1px solid #e3e5e8;border-radius:8px;margin:2px 0 14px">` +
    `<tr>${cells.map(([l, v, col], i) => `<td style="padding:10px 18px;${i ? "border-left:1px solid #e3e5e8;" : ""}">` +
      `<div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em">${l}</div>` +
      `<div style="font-size:18px;font-weight:600;color:${col || "#1f2328"};margin-top:2px">${v}</div></td>`).join("")}</tr></table>`;
}
function appsHtml(c) {
  const apps = (c.apps || []).slice(0, 5);
  if (!apps.length) return "";
  return `<div style="margin:2px 0 14px"><div style="font-size:12px;color:#6b7280;margin-bottom:6px">Where your tracked time went (top apps)</div>` +
    `<table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">` +
    apps.map(([a, m]) => `<tr><td style="padding:3px 18px 3px 0;color:#1f2328">${esc(a)}</td><td style="padding:3px 0;color:#4b505b;font-variant-numeric:tabular-nums">${hm(m)}</td></tr>`).join("") +
    `</table></div>`;
}
function toHtml(body, c) {
  const para = (p) => `<p style="margin:0 0 12px">${esc(p.trim()).replace(/\n/g, "<br>")}</p>`;
  const blocks = { stats: statsHtml(c), apps: appsHtml(c) };
  const parts = body.replace(/\r/g, "").split(/\n{2,}/).flatMap((p) =>
    p.split(/(\{stats\}|\{apps\})/).map((chunk) => {
      const b = chunk.match(/^\{(stats|apps)\}$/);
      return b ? blocks[b[1]] : chunk.trim() ? para(chunk) : "";
    }));
  return `<div style="font-family:'Segoe UI',Arial,sans-serif;font-size:14px;line-height:1.55;color:#1f2328">${parts.join("")}</div>`;
}
function toText(body, c) {
  const stats = [`Productive: ${hm(c.productive)}`, `Expected: ${hm(thr())}`, c.logged != null && `Logged in: ${hm(c.logged)}`, c.idle != null && `Idle: ${hm(c.idle)}`].filter(Boolean).join("  |  ");
  const apps = (c.apps || []).length ? "Top apps: " + topApps(c, 5) : "";
  return body.split("{stats}").join(stats).split("{apps}").join(apps).replace(/\n{3,}/g, "\n\n");
}
const mailPreview = (dr, c) => `<div class="subj">${esc(dr.subject)}</div>${toHtml(dr.body, c)}`;

let editTimer = {};
function saveEditField(key, field, value) {
  const { c, d } = S.byKey[key];
  const base = baseDraft(c, d);
  const ov = { ...(S.edits[key] || {}) };
  if (value === base[field]) delete ov[field]; else ov[field] = value;
  if (Object.keys(ov).length) S.edits[key] = ov; else delete S.edits[key];
  clearTimeout(editTimer[key]);
  editTimer[key] = setTimeout(() => api("edit", { key, edit: S.edits[key] || null }).catch((e) => toast(e.message, "err")), 400);
}

// Replace a mistyped candidate address with the suggested one. Saved as the person's own address, so the
// extra To/Cc recipients still apply; a To the person's email already sets by hand gets the swap too.
function useEmail(key, email) {
  const { c } = S.byKey[key];
  const ownTo = S.edits[key] && "to" in S.edits[key] ? S.edits[key].to : null;
  saveEditField(key, "email", email);
  if (ownTo !== null) {
    const bad = (c.email || "").toLowerCase();
    saveEditField(key, "to", joinAddrs(splitEmails(ownTo).map((e) => (e.toLowerCase() === bad ? email : e))));
  }
}

// ------------------------------------------------------------------ rendering
const app = $("#app");

function renderAll() {
  if (!S.st) return;
  if (!S.wb) return renderConnect();
  if (S.view === "log") {
    app.innerHTML = `<header id="top"></header><div class="body sent"><div class="sentlog">
      <div class="head"><h1>Log</h1><div class="seg" id="logseg"></div>
        <div class="search">${ic("search")}<input id="logq" placeholder="Search name, email, subject" value="${esc(S.logQ)}" autocomplete="off"></div>
      </div><div id="loglist"></div></div></div><div id="bar"></div>`;
    renderTop(); renderLog(); renderBar();
    return;
  }
  app.innerHTML = `<header id="top"></header><div class="body">
    <aside id="rail"></aside>
    <main id="main"><div id="dayhead"></div>
      <div id="tools">
        <div class="search">${ic("search")}<input id="q" placeholder="Search name or email" value="${esc(S.q)}" autocomplete="off"><kbd>/</kbd></div>
        <span class="thr">Threshold <b class="num">${hm(thr())}</b></span>
        <div class="spacer"></div>
        <button class="btn sm ghost" data-act="select-all">${ic("check")}Select everyone to do</button>
      </div>
      <div id="rows"></div>
    </main>
    <section id="panel"></section></div><div id="bar"></div>`;
  renderTop(); renderRail(); renderHead(); renderRows(); renderPanel(true); renderBar();
}

function tokenChip() {
  const t = tok();
  if (S.st.demo) return "";
  if (!t) return S.st.source === "sharepoint" || !S.wb
    ? `<button class="btn sm tokchip bad" data-act="token" title="Needed to read the tracker from SharePoint">${ic("key")}Add token</button>` : "";
  const mins = (t.expires_at * 1000 - Date.now()) / 60000;
  const cls = mins < 60 ? "warn" : "ok";
  const lacks = [!t.can_read && "can't read files"].filter(Boolean);
  return `<button class="btn sm tokchip ${lacks.length ? "warn" : cls}" data-act="token" title="${esc(`${t.name || t.user} · token from ${t.app || "Microsoft"}${lacks.length ? " · " + lacks.join(", ") : ""}`)}">
    <span class="dot"></span>${esc((t.name || t.user).split(" ")[0])} · ${esc(left(t.expires_at))}</button>`;
}

function renderTop() {
  const el = $("#top");
  if (!el) return;
  const f = S.wb?.file, src = S.st.source;
  const sub = S.refreshing ? "Checking SharePoint for changes…"
    : src === "local" ? `Downloaded copy · saved ${esc(whenStr(f?.modified))}`
    : src === "demo" ? "Demo data"
    : `Saved ${esc(whenStr(f?.modified))}${f?.modified_by ? " by " + esc(f.modified_by) : ""} · checked ${esc(ago(f?.fetched_at))}`;
  const nOpen = openDrafts();
  const nLog = S.ledger.filter((e) => e.status === "drafted" || e.status === "sent").length;
  el.innerHTML = `
    <div class="brand"><div class="logo">${ic("send")}</div>Nudge${S.st.demo ? ' <span class="demo-tag">DEMO</span>' : ""}</div>
    ${f ? `<div class="filechip">
      <div class="xl">${ic("grid")}</div>
      <div class="meta">${f.web_url ? `<a class="name" href="${esc(f.web_url)}" target="_blank" rel="noopener" title="Open in Excel">${esc(f.name)}</a>` : `<span class="name">${esc(f.name)}</span>`}
        <span class="sub">${sub}</span></div>
      ${src === "local" ? `<button class="btn icon ghost sm" data-act="pick-file" title="Open a newer copy">${ic("upload")}</button>`
        : `<button class="btn icon ghost sm refresh ${S.refreshing ? "spinning" : ""}" data-act="refresh" title="Check for changes (R)">${ic("refresh")}</button>`}
    </div>` : ""}
    <div class="spacer"></div>
    ${nOpen ? `<button class="btn sm ghost" data-act="mark-sent-list" title="Emails opened in Outlook that you haven't marked as sent yet">
      ${ic("check")}Mark sent <span class="cnt-badge num">${nOpen}</span></button>` : ""}
    <div class="nav">
      <button class="${S.view === "day" ? "on" : ""}" data-act="view" data-v="day">${ic("rows")}Days</button>
      <button class="${S.view === "log" ? "on" : ""}" data-act="view" data-v="log">${ic("history")}Log <span class="muted num">${nLog}</span></button>
    </div>
    <button class="btn ghost" data-act="templates">${ic("edit")}Templates</button>
    <button class="btn icon ghost" data-act="settings" title="Settings">${ic("sliders")}</button>
    ${newOutlookOn() ? `<button class="btn sm tokchip warn" data-act="outlook-help" title="${esc(NEW_OUTLOOK_HELP)}">${ic("alert")}New Outlook is on</button>` : ""}
    ${!S.st.demo && !S.st.outlook?.installed ? `<span class="btn sm tokchip bad" title="Drafts need classic Outlook on this PC">${ic("alert")}No classic Outlook</span>` : ""}
    ${tokenChip()}`;
}

function renderRail() {
  const el = $("#rail");
  if (!el) return;
  let todo = 0;
  const items = S.wb.days.map((d) => {
    const n = dayCounts(d);
    todo += n.todo;
    const dt = D(d.date);
    const sub = d.error ? "Couldn't read this tab"
      : n.bLow + n.bNone === 0 ? "Everyone on track"
      : n.todo ? `${n.todo} to do${n.drafted ? ` · ${n.drafted} drafted` : ""}${n.sent ? ` · ${n.sent} sent` : ""}`
      : [n.drafted && `${n.drafted} drafted`, n.sent && `${n.sent} sent`, n.skipped && `${n.skipped} skipped`].filter(Boolean).join(" · ") || "Done";
    return `<button class="day ${d.sheet === S.day ? "on" : ""} ${d.error ? "err" : ""}" data-act="day" data-sheet="${esc(d.sheet)}" title="Tab “${esc(d.sheet)}”">
      <div class="cal"><div class="m">${dt.toLocaleDateString("en-GB", { month: "short" })}</div><div class="d">${dt.getDate()}</div></div>
      <div class="dd"><div class="t">${dt.toLocaleDateString("en-GB", { weekday: "long" })}</div><div class="s">${esc(sub)}</div></div>
      ${n.todo ? `<span class="badge num">${n.todo}</span>` : n.sent || n.drafted ? `<span class="done">${ic("check")}</span>` : ""}
    </button>`;
  }).join("");
  const other = S.wb.other_tabs?.length ? `<div class="rail-foot">Other tabs: ${S.wb.other_tabs.map(esc).join(", ")}${S.wb.usage_tab ? " (app usage is used in emails)" : ""}</div>` : "";
  const nDays = S.wb.days.filter((d) => dayCounts(d).todo).length;
  el.innerHTML = `<div class="rail-sum"><div class="big num">${todo}</div><div class="lbl">${todo ? `${todo === 1 ? "person" : "people"} to email across ${plural(nDays, "day")}` : "All caught up"}</div></div>
    <div class="rail-h">Days</div>${items}${other}`;
}

function renderHead() {
  const el = $("#dayhead"), d = curDay();
  if (!el) return;
  if (!d) { el.innerHTML = `<div class="dh-title"><h1>No day tabs found</h1></div><p class="muted">Tabs are expected to be named like “10 Nov”.</p>`; return; }
  const n = dayCounts(d), t = hm(thr());
  const warns = dayWarnings(d), nWarn = warns.filter((w) => w.level === "warn").length;
  const tile = (f, v, l, sw) => `<button class="stat ${S.filter === f ? "on" : ""}" data-act="filter" data-f="${f}"><div class="v num"><span class="sw ${sw}"></span>${v}</div><div class="l">${l}</div></button>`;
  el.innerHTML = `<div class="dh-title"><h1>${esc(fmtLong(d.date))}</h1><span class="tab">Tab “${esc(d.sheet)}” · ${plural(n.all, "person")}</span>
      <span class="spacer"></span>
      <button class="btn sm ${nWarn ? "warnbtn" : "ghost"}" data-act="checks">${ic("shield")}${warns.length ? `Data checks · ${warns.length}` : "Data checks · all clear"}</button></div>
    <div class="stats six">
      ${tile("todo", n.todo, "To do", "low")}
      ${tile("low", n.bLow, `Under ${t}`, "low")}
      ${tile("none", n.bNone, "No activity", "none")}
      ${tile("drafted", n.drafted, "In Outlook", "all")}
      ${tile("sent", n.sent, "Sent", "sent")}
      ${tile("all", n.all, "Everyone", "skipped")}
    </div>`;
}

function visibleRows() {
  const d = curDay();
  if (!d) return [];
  const q = S.q.trim().toLowerCase();
  let list = d.candidates.filter(FILTERS[S.filter] || FILTERS.all);
  if (q) list = list.filter((c) => `${c.name} ${c.email} ${c.sheet_email || ""} ${c.emp_id}`.toLowerCase().includes(q));
  if (S.filter !== "all") list = [...list].sort((a, b) => (a.productive ?? 1e9) - (b.productive ?? 1e9) || a.row - b.row);
  return list;
}

function pill(c) {
  if (S.busy[c.key]) return `<span class="pill sending"><span class="spinner sm"></span>Opening</span>`;
  if (S.errors[c.key]) return `<span class="pill error" title="${esc(S.errors[c.key])}">${ic("alert")}Failed</span>`;
  const st = statusOf(c), l = S.latest[c.key];
  switch (st) {
    case "sent": return `<span class="pill sent" title="${esc(l.subject || "")}">${ic("check")}Sent ${esc(whenStr(l.sent_at || l.at))}</span>`;
    case "drafted": return `<span class="pill accent" title="Opened in Outlook; mark it sent once you've sent it">${ic("mail")}In Outlook ${esc(whenStr(l.at))}</span>`;
    case "skipped": return `<span class="pill skipped">Skipped</span>`;
    case "low": return `<span class="pill low"><span class="dot"></span>Under ${hm(thr())}</span>`;
    case "none": return `<span class="pill none"><span class="dot"></span>No activity</span>`;
    case "ok": return `<span class="pill ok">On track</span>`;
    default: return `<span class="pill" title="Productive hours couldn't be read; see Data checks">Hours unreadable</span>`;
  }
}

function barCell(c) {
  const max = Math.max(540, thr() + 60), b = baseOf(c), p = c.productive;
  const w = p == null ? 0 : Math.min(p, max) / max * 100;
  return `<div class="bar"><div class="track"><div class="fill ${b}" style="width:${w}%"></div><div class="mark" style="left:${thr() / max * 100}%"></div></div>
    <span class="v num ${b === "low" || b === "none" ? "low" : ""}">${hm(p)}</span></div>`;
}

function renderRows() {
  const el = $("#rows"), d = curDay();
  if (!el) return;
  if (!d) { el.innerHTML = ""; return; }
  if (d.error) { el.innerHTML = `<div class="sheet-err">${ic("alert")} ${esc(d.error)} in tab “${esc(d.sheet)}”.</div>`; return; }
  const list = visibleRows();
  S.visible = list.map((c) => c.key);
  if (!list.length) {
    const msg = S.q ? ["No matches", `Nobody on this day matches “${esc(S.q)}”.`]
      : S.filter === "todo" ? ["All caught up", "Everyone under the threshold on this day has a draft, was sent, or was skipped."]
      : ["Nobody here", "No one on this day fits this filter."];
    el.innerHTML = `<div class="empty"><div class="ico">${ic("check")}</div><div class="big">${msg[0]}</div>${msg[1]}</div>`;
    return;
  }
  const s = sel();
  const selectable = list.filter(canSelect);
  const nSel = selectable.filter((c) => s.has(c.key)).length;
  const headBox = nSel === 0 ? "" : nSel === selectable.length ? "on" : "mixed";
  el.innerHTML = `<table class="grid"><thead><tr>
      <th class="ck"><span class="cbox ${headBox} ${selectable.length ? "" : "off"}" data-act="toggle-all" title="Select all">${headBox === "on" ? ic("check") : ""}</span></th>
      <th>Candidate</th><th>Productive</th><th>Logged</th><th>Idle</th><th>Top app</th><th>Sheet reason</th><th>Status</th></tr></thead><tbody>
    ${list.map((c) => {
      const dr = draftFor(c, d), can = canSelect(c), on = s.has(c.key) && can;
      const st = statusOf(c), issue = issueOpen(c, dr), app0 = (c.apps || [])[0];
      return `<tr data-act="focus" data-key="${esc(c.key)}" class="${S.focus === c.key ? "focus" : ""} ${st === "ok" || st === "skipped" ? "dim" : ""}">
        <td class="ck"><span class="cbox ${on ? "on" : ""} ${can ? "" : "off"}" data-act="toggle" data-key="${esc(c.key)}">${ic("check")}</span></td>
        <td class="who"><div class="n">${esc(c.name)}${issue ? `<span class="warn" title="${esc(c.email_issue)}">${ic("alert")}</span>` : ""}${dr.edited ? '<span class="ed">EDITED</span>' : ""}</div>
          <div class="e">${esc(dr.to || "no email")}</div></td>
        <td>${barCell(c)}</td>
        <td class="cell-sm num">${hm(c.logged)}</td>
        <td class="cell-sm num">${hm(c.idle)}</td>
        <td class="cell-sm">${app0 ? `${esc(app0[0])} <span class="muted num">${hm(app0[1])}</span>` : '<span class="muted">—</span>'}</td>
        <td><div class="reason" title="${esc(c.reason)}">${esc(c.reason) || '<span class="muted">—</span>'}</div></td>
        <td>${pill(c)}</td></tr>`;
    }).join("")}</tbody></table>
    <div class="keys"><span><kbd>J</kbd><kbd>K</kbd> move</span><span><kbd>X</kbd> select</span><span><kbd>E</kbd> edit email</span><span><kbd>/</kbd> search</span><span><kbd>[</kbd><kbd>]</kbd> day</span><span><kbd>R</kbd> refresh</span><span><kbd>Ctrl</kbd><kbd>Enter</kbd> open selected in Outlook</span></div>`;
}

function panelBusy() {
  const a = document.activeElement;
  return a && $("#panel")?.contains(a) && /INPUT|TEXTAREA/.test(a.tagName);
}

function renderPanel(force = false) {
  const el = $("#panel");
  if (!el || (!force && panelBusy())) return;
  const hit = S.byKey[S.focus];
  if (!hit || hit.d.sheet !== S.day) {
    el.innerHTML = `<div class="p-empty"><div>${ic("mail")}<div style="margin-top:8px">Pick someone to see their email.</div><div class="muted" style="font-size:12.5px;margin-top:4px">A draft is ready for everyone under the threshold.</div></div></div>`;
    return;
  }
  const { c, d } = hit, st = statusOf(c), l = S.latest[c.key], dr = draftFor(c, d), b = baseOf(c);
  const facts = `<div class="facts">
      <span>Productive <b class="num ${b === "low" || b === "none" ? "low" : ""}">${hm(c.productive)}</b></span>
      <span>Logged <b class="num">${hm(c.logged)}</b></span><span>Idle <b class="num">${hm(c.idle)}</b></span>
      <span>Row <b class="num">${c.row}</b></span></div>
      ${(c.apps || []).length ? `<div class="apps">${c.apps.slice(0, 6).map(([a, m]) => `<span class="appchip">${esc(a)} <b class="num">${hm(m)}</b></span>`).join("")}</div>`
        : `<div class="apps muted" style="font-size:12px">${c.logged ? "No App Usage row for this day" : "No app usage (no activity)"}</div>`}`;
  const rowData = [["Name", c.name], ["Email", ownEmail(c)],
    ...(c.sheet_email && c.sheet_email.toLowerCase() !== ownEmail(c).toLowerCase() ? [["Email in the sheet", c.sheet_email]] : []), ["Emp ID", c.emp_id], ["Manager", c.manager], ["Productive", hm(c.productive)],
    ["Logged", hm(c.logged)], ["Idle", hm(c.idle)], ["Reason", c.reason], ...c.extra].filter(([, v]) => v && v !== "—");
  const details = `<details class="rowdata"><summary>${ic("grid")}Everything in the sheet row</summary>
    <dl class="kv">${rowData.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></details>`;
  let body, foot;
  if (st === "sent" || st === "drafted") {
    const box = st === "sent"
      ? `<div class="sentbox">${ic("check")}<div><div class="t">Sent ${esc(whenStr(l.sent_at || l.at))}</div><div class="s">To ${esc((l.to || []).join(", "))}${l.cc?.length ? ` · Cc ${esc(l.cc.join(", "))}` : ""}</div></div></div>`
      : `<div class="draftbox">${ic("mail")}<div style="flex:1"><div class="t">Opened in Outlook ${esc(whenStr(l.at))}</div><div class="s">Check it and press Send in Outlook, then mark it sent here.</div></div>
          <button class="btn sm" data-act="open-draft" data-key="${esc(c.key)}" title="Closed it by mistake? Open it again">${ic("ext")}Open again</button></div>`;
    body = `${box}${l.html ? `<div class="mail"><div class="subj">${esc(l.subject)}</div>${l.html}</div>` : ""}${details}`;
    foot = st === "sent"
      ? `<span class="grow">This person won't get another draft for this day unless you choose to.</span>
         <button class="btn sm ghost" data-act="again" data-key="${esc(c.key)}" ${canDraft() ? "" : "disabled"}>${ic("mail")}Email again</button>`
      : `<span class="grow">Decided not to send it? Put this person back on the to-do list.</span>
         <button class="btn sm ghost" data-act="forget" data-key="${esc(c.key)}">${ic("undo")}Not sent</button>
         <button class="btn sm primary" data-act="mark-sent" data-key="${esc(c.key)}">${ic("check")}Mark sent</button>`;
  } else {
    const fix = issueOpen(c, dr) ? `<div class="fixmail">${ic("alert")}<span class="grow">${esc(c.email_issue)}</span>
      ${c.email_suggestion ? `<button class="btn sm" data-act="use-email" data-key="${esc(c.key)}" data-email="${esc(c.email_suggestion)}">Use ${esc(c.email_suggestion)}</button>` : ""}</div>` : "";
    const skipped = st === "skipped" ? `<div class="skipbox">${ic("skip")}<span style="flex:1">Skipped ${esc(whenStr(l.at))}</span>
      <button class="btn sm" data-act="unskip" data-key="${esc(c.key)}">${ic("undo")}Undo</button></div>` : "";
    const noName = !senderName() ? `<div class="fixmail">${ic("edit")}<span class="grow">The sign-off has no name yet.</span><button class="btn sm" data-act="settings">Add your name</button></div>` : "";
    body = `${skipped}${noName}${fix}
      <label class="hdr-f"><span>To</span><input class="input" data-f="to" value="${esc(dr.to)}" spellcheck="false"></label>
      <label class="hdr-f"><span>Cc</span><input class="input" data-f="cc" value="${esc(dr.cc)}" placeholder="none" spellcheck="false"></label>
      <label class="hdr-f"><span>Subject</span><input class="input" data-f="subject" value="${esc(dr.subject)}"></label>
      <div class="tabs"><button class="${S.tab === "preview" ? "on" : ""}" data-act="tab" data-t="preview">Preview</button>
        <button class="${S.tab === "edit" ? "on" : ""}" data-act="tab" data-t="edit">Edit text</button>
        <span class="r">${dr.edited ? `<span class="pill accent">Edited</span><button class="btn sm ghost" data-act="reset-edit" data-key="${esc(c.key)}" title="Back to the template">${ic("undo")}Reset</button>` : `<span class="muted" style="font-size:12px">${kindOf(c) === "none" ? "“No activity” template" : "“Under threshold” template"}</span>`}</span></div>
      ${S.tab === "preview" ? `<div class="mail" id="pv">${mailPreview(dr, c)}</div>`
        : `<textarea class="textarea body-ta" data-f="body" spellcheck="true">${esc(dr.body)}</textarea>
           <div class="vars">${["first_name", "productive_words", "threshold_words", "date", "top_apps", "stats", "apps"].map((v) => `<button data-act="ins" data-v="${v}">{${v}}</button>`).join("")}</div>
           <div class="muted" style="font-size:12px">A line with just <code class="code">{stats}</code> becomes the hours table, and <code class="code">{apps}</code> the top-apps list.</div>`}
      ${details}`;
    const ok = toValid(dr);
    const note = !ok ? '<span style="color:var(--danger)">Fix the To address</span>' : canDraft() ? "Opens as a new message in Outlook; you press Send" : "Needs classic Outlook on this PC";
    foot = `<span class="grow">${note}</span>
      ${st !== "skipped" ? `<button class="btn sm ghost" data-act="skip-one" data-key="${esc(c.key)}">${ic("skip")}Skip</button>` : ""}
      <button class="btn sm ghost" data-act="copy-mail" data-key="${esc(c.key)}" title="Copy the formatted email">${ic("copy")}Copy</button>
      <button class="btn sm primary" data-act="draft-one" data-key="${esc(c.key)}" ${ok && canDraft() && !S.busy[c.key] ? "" : "disabled"}>${ic("mail")}Open in Outlook</button>`;
  }
  el.innerHTML = `<div class="p-head"><div class="row1"><div class="nm">${esc(c.name)}</div>${pill(c)}</div>${facts}</div>
    <div class="p-body">${body}</div><div class="p-foot">${foot}</div>`;
}

function selectedItems() {
  return [...sel()].map((k) => S.byKey[k]).filter((h) => h && h.d.sheet === S.day && canSelect(h.c));
}

function renderBar() {
  const el = $("#bar");
  if (!el) return;
  const items = S.view === "day" ? selectedItems() : [];
  el.className = items.length ? "show" : "";
  if (!items.length) { el.innerHTML = ""; return; }
  const nLow = items.filter((h) => kindOf(h.c) === "low").length, nNone = items.length - nLow;
  const busy = Object.keys(S.busy).length > 0;
  el.innerHTML = `<div class="abar"><span class="cnt num">${items.length} selected</span>
    <span class="sub">${[nLow && `${nLow} under ${hm(thr())}`, nNone && `${nNone} no activity`].filter(Boolean).join(" · ")}</span>
    <button class="btn sm ghost" data-act="clear-sel">Clear</button>
    <button class="btn sm ghost" data-act="skip-sel">${ic("skip")}Skip</button><div class="sep"></div>
    ${canDraft() ? `<button class="btn sm primary" data-act="draft-sel" ${busy ? "disabled" : ""}>${busy ? '<span class="spinner sm"></span>Opening…' : `${ic("mail")}Open ${items.length} in Outlook`}<span class="kb">Ctrl ↵</span></button>`
      : `<button class="btn sm primary" disabled title="Drafts need classic Outlook on this PC">${ic("alert")}Classic Outlook needed</button>`}</div>`;
}

function renderLog() {
  const seg = $("#logseg"), el = $("#loglist");
  if (!el) return;
  // one line per person and day: their latest state
  const all = Object.values(S.latest).filter((e) => ["drafted", "sent", "skipped"].includes(e.status));
  const counts = { all: all.length };
  for (const k of ["drafted", "sent", "skipped"]) counts[k] = all.filter((e) => e.status === k).length;
  seg.innerHTML = [["all", "All"], ["drafted", "In Outlook"], ["sent", "Sent"], ["skipped", "Skipped"]].map(([k, l]) =>
    `<button class="${S.logFilter === k ? "on" : ""}" data-act="logf" data-f="${k}">${l} <span class="muted num">${counts[k]}</span></button>`).join("");
  const q = S.logQ.trim().toLowerCase();
  const list = all.filter((e) => S.logFilter === "all" || e.status === S.logFilter)
    .filter((e) => !q || `${e.name} ${(e.to || []).join(" ")} ${e.subject || ""}`.toLowerCase().includes(q))
    .sort((a, b) => ((b.sent_at || b.at) > (a.sent_at || a.at) ? 1 : -1));
  if (!list.length) {
    el.innerHTML = `<div class="empty"><div class="ico" style="background:var(--accent-soft);color:var(--accent)">${ic("mail")}</div><div class="big">${all.length ? "No matches" : "Nothing yet"}</div>${all.length ? "Try a different search." : "Drafts you create and emails you send show up here."}</div>`;
    return;
  }
  let html = "", lastDay = "";
  for (const e of list) {
    const ts = e.sent_at || e.at, day = new Date(ts).toDateString();
    if (day !== lastDay) {
      if (html) html += "</tbody></table>";
      const label = sameDay(new Date(ts), new Date()) ? "Today" : sameDay(new Date(ts), new Date(Date.now() - 864e5)) ? "Yesterday"
        : new Date(ts).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
      html += `<div class="log-day">${label}</div><table class="grid"><thead><tr><th>Time</th><th>Tracker day</th><th>Candidate</th><th>To</th><th>Productive</th><th>Subject</th><th>Status</th></tr></thead><tbody>`;
      lastDay = day;
    }
    const id = `${e.key}@${e.at}`, open = S.logOpen === id;
    const status = e.status === "sent" ? `<span class="pill sent">${ic("check")}Sent${e.demo ? " (demo)" : ""}</span>`
      : e.status === "drafted" ? `<span class="pill accent">${ic("mail")}Draft</span>` : '<span class="pill skipped">Skipped</span>';
    html += `<tr data-act="logopen" data-id="${esc(id)}" class="${open ? "log-open" : ""}">
      <td class="cell-sm num">${esc(clock(ts))}</td>
      <td class="cell-sm">${e.date ? esc(D(e.date).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })) : ""}</td>
      <td><b>${esc(e.name)}</b></td><td class="cell-sm">${esc((e.to || []).join(", "))}</td>
      <td class="num" style="color:var(--danger);font-weight:600">${hm(e.productive)}</td>
      <td class="cell-sm" style="max-width:360px;overflow:hidden;text-overflow:ellipsis">${esc(e.subject || "")}</td>
      <td>${status}</td></tr>`;
    if (open && e.html) html += `<tr class="log-mail"><td colspan="7"><div class="mail"><div class="subj">${esc(e.subject)}</div>${e.html}</div></td></tr>`;
  }
  el.innerHTML = html + "</tbody></table>";
}

// ------------------------------------------------------------------ first screen: token + link, or a downloaded copy
function renderConnect() {
  const s = S.st.settings, t = tok();
  app.innerHTML = `<div class="onb"><div class="card">
    <div class="logo" style="width:44px;height:44px;border-radius:13px">${ic("send")}</div>
    <h1>Nudge</h1>
    <p class="lead">Drafts emails in your Outlook for interns under ${hm(s.threshold_min)} of productive time. Nothing is sent until you send it from Outlook.</p>
    <div class="cstep">
      <div class="cnum ${t ? "done" : ""}">${t ? ic("check") : "1"}</div>
      <div class="cbody">
        <div class="ctitle">Microsoft access token <span class="muted" style="font-weight:400">(to read the tracker from SharePoint)</span></div>
        ${t ? `<div class="muted" style="font-size:13px">${esc(t.name || t.user)} · ${esc(left(t.expires_at))}${t.can_read ? "" : " · <b style='color:var(--warn)'>can't read files</b>"}
            <button class="btn sm ghost" data-act="token">Change</button></div>`
          : `<div class="muted" style="font-size:13px;margin-bottom:8px">Open <a href="${GRAPH_EXPLORER}" target="_blank" rel="noopener">Graph Explorer</a>, sign in, open the <b>Access token</b> tab and copy it. It stays in memory only and lasts about a day.</div>
             <form id="tok-form" class="row-form"><input class="input" name="token" type="password" placeholder="Paste the access token" autocomplete="off" spellcheck="false" required><button class="btn primary">Use token</button></form>`}
      </div>
    </div>
    <div class="cstep">
      <div class="cnum">2</div>
      <div class="cbody">
        <div class="ctitle">Tracker link</div>
        <div class="muted" style="font-size:13px;margin-bottom:8px">The SharePoint link to the daily tracker (Share → Copy link). Saved until you change it.</div>
        <form id="link-form" class="row-form"><input class="input" name="link" value="${esc(s.link)}" placeholder="https://…sharepoint.com/:x:/…" spellcheck="false" required>
          <button class="btn primary" id="lbtn" ${t ? "" : "disabled title='Add the token first'"}>${ic("link")}Load</button></form>
      </div>
    </div>
    <div class="form-err" id="ferr"></div>
    <div class="or"><span>or, without a token</span></div>
    <button class="btn lg" data-act="pick-file" style="width:100%;justify-content:center">${ic("upload")}Open a downloaded copy (.xlsx)</button>
    <p class="muted" style="font-size:12.5px;margin:10px 0 0;text-align:center">Everything works the same, drafts included; you just open a newer copy yourself when the tracker changes.</p>
    ${newOutlookOn() ? `<div class="fixmail" style="margin-top:14px">${ic("alert")}<span>${esc(NEW_OUTLOOK_HELP)}</span></div>` : ""}
  </div></div>`;
  $("#tok-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try { await useToken(new FormData(e.target).get("token")); renderConnect(); }
    catch (err) { $("#ferr").textContent = err.message; }
  });
  $("#link-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#lbtn");
    btn.disabled = true; btn.innerHTML = `<span class="spinner sm"></span>Loading…`; $("#ferr").textContent = "";
    try {
      const r = await api("settings", { link: new FormData(e.target).get("link").trim() });
      applyState(r);
      if (!S.wb) { const rr = await api("refresh", { force: true }); applyState(rr); }
      renderAll();
    } catch (err) {
      $("#ferr").textContent = err.message;
      btn.disabled = false; btn.innerHTML = `${ic("link")}Load`;
    }
  });
}

async function useToken(token) {
  const r = await api("token", { token: String(token || "").trim() });
  S.st.token = r.token;
  const t = r.token;
  toast(t.can_read ? `Token ready: ${t.name || t.user}, ${left(t.expires_at)}` : "Token works, but it can't read SharePoint files.", t.can_read ? "ok" : "err");
  return t;
}

// ------------------------------------------------------------------ modals & toasts
function toast(msg, kind = "ok", action) {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.innerHTML = `${ic(kind === "err" ? "alert" : "check")}<div style="flex:1">${esc(msg)}</div>${action ? `<button class="btn sm">${esc(action.label)}</button>` : ""}`;
  if (action) t.querySelector("button").onclick = () => { action.run(); t.remove(); };
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "err" ? 9000 : action ? 8000 : 3500);
}
function openModal({ title, body, foot, wide, onEnter, mount }) {
  closeModal();
  const root = $("#modal-root");
  root.innerHTML = `<div class="overlay"><div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true">
    <div class="m-head"><h2>${title}</h2><button class="btn icon ghost sm" data-act="close-modal">${ic("x")}</button></div>
    <div class="m-body">${body}</div>${foot ? `<div class="m-foot">${foot}</div>` : ""}</div></div>`;
  root.firstElementChild.addEventListener("mousedown", (e) => { if (e.target === e.currentTarget) closeModal(); });
  S.modal = { onEnter };
  mount?.(root);
}
function closeModal() { $("#modal-root").innerHTML = ""; S.modal = null; }

function openToken() {
  const t = tok();
  openModal({
    title: "Microsoft access token",
    body: `${t ? `<div class="tokinfo"><div><b>${esc(t.name || t.user)}</b> <span class="muted">${esc(t.user)}</span></div>
        <div class="muted" style="font-size:12.5px">From ${esc(t.app || "Microsoft")} · expires ${esc(new Date(t.expires_at * 1000).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }))} (${esc(left(t.expires_at))})</div>
        <div style="display:flex;gap:6px;margin-top:8px">${t.can_read ? '<span class="pill sent">Reads SharePoint</span>' : '<span class="pill low">Can\'t read files</span>'}</div></div>` : ""}
      <div class="field"><label>${t ? "Replace with a new token" : "Paste a token"}</label>
        <textarea class="textarea" id="tok-in" style="min-height:90px;font-family:var(--mono);font-size:12px" placeholder="eyJ0eXAiOi…" spellcheck="false"></textarea>
        <span class="hint">Used only to read the tracker from SharePoint (emails open in Outlook on this PC). Get it from <a href="${GRAPH_EXPLORER}" target="_blank" rel="noopener">Graph Explorer</a>: sign in → <b>Access token</b> tab → copy. Nudge keeps it in memory only, never on disk; restarting Nudge forgets it.</span></div>
      <div class="form-err" id="tok-err"></div>`,
    foot: `${t ? `<button class="btn ghost" id="tok-forget">${ic("trash")}Forget token</button>` : ""}<span class="grow"></span><button class="btn" data-act="close-modal">Cancel</button><button class="btn primary" id="tok-go">Use token</button>`,
    onEnter: () => $("#tok-go").click(),
    mount: () => {
      $("#tok-in").focus();
      $("#tok-go").onclick = async () => {
        const v = $("#tok-in").value.trim();
        if (!v) { $("#tok-err").textContent = "Paste a token first"; return; }
        try { await useToken(v); closeModal(); renderAll(); if (S.st.source === "sharepoint") refresh(); }
        catch (e) { $("#tok-err").textContent = e.message; }
      };
      $("#tok-forget")?.addEventListener("click", async () => {
        const r = await api("token_clear"); S.st.token = r.token; closeModal(); renderAll(); toast("Token forgotten");
      });
    },
  });
}

function openChecks() {
  const d = curDay(), warns = dayWarnings(d);
  const order = { warn: 0, info: 1 };
  const rows = [...warns].sort((a, b) => order[a.level] - order[b.level] || (a.row || 0) - (b.row || 0));
  openModal({
    title: `Data checks · ${esc(d?.sheet || "")}`,
    body: rows.length ? `<p class="muted" style="margin:0">Rows that look odd are listed here instead of stopping anything. Everything else on the day works as normal.</p>
      <div class="checks">${rows.map((w) => `<div class="chk ${w.level}"><span class="lvl">${w.level === "warn" ? "Check" : "Note"}</span>
        <div><div>${w.who ? `<b>${esc(w.who)}</b>: ` : ""}${esc(w.msg)}</div><div class="muted" style="font-size:12px">${esc(w.tab || "")}${w.row ? ` · row ${w.row}` : ""}</div></div></div>`).join("")}</div>`
      : `<div class="empty" style="padding:30px"><div class="ico">${ic("check")}</div><div class="big">All clear</div>Every row on this tab was read, the Date column matches the tab, and nothing looks odd.</div>`,
    foot: `<span class="grow">Checks: missing or unreadable hours, productive above logged, duplicates, Date column vs tab name, email addresses, App Usage.</span><button class="btn" data-act="close-modal">Close</button>`,
  });
}

function confirmDrafts(items, { again = false } = {}) {
  if (!items.length) return;
  if (!canDraft()) { toast("This needs classic Outlook on this PC, and it isn't installed.", "err"); return; }
  // the email must be complete before it reaches Outlook: a sign-off name, and no unfilled {fields}
  const usesName = items.some(({ c }) => /\{sender_name\}/.test(S.st.settings.templates[kindOf(c)].body) && !S.edits[c.key]?.body);
  if (usesName && !senderName()) { toast("Add your name for the sign-off first (Settings).", "err"); openSettings(); return; }
  const unfilled = items.map(({ c }) => { const dr = draftFor(c); return [c, (dr.subject + " " + dr.body).match(/\{(?!stats\}|apps\})[a-z_]{2,30}\}/g)]; }).filter(([, m]) => m);
  if (unfilled.length) { toast(`${unfilled[0][0].name}'s email has an unfilled field ${unfilled[0][1][0]}. Fix the template or that email.`, "err"); return; }
  const ccOptions = S.st.settings.cc_list || [];
  const ownCc = items.filter(({ c }) => S.edits[c.key] && ("cc" in S.edits[c.key] || "to" in S.edits[c.key]));
  const flagged = items.filter(({ c }) => issueOpen(c, draftFor(c)));
  const chips = (field) => ccOptions.map((c, i) => [c, i]).filter(([c]) => (c.field || "cc") === field)
    .map(([c, i]) => `<label class="ccchip"><input type="checkbox" class="go-cc" data-i="${i}" ${c.default ? "checked" : ""}> ${esc(c.email)}</label>`).join("");
  openModal({
    title: again ? "Email this person again?" : `Open ${plural(items.length, "email")} in Outlook?`,
    body: `<div>Each email opens as a <b>new message window in classic Outlook</b>, already filled in and formatted. <b>Nothing is sent</b> until you press Send in Outlook. Afterwards, mark them sent here.${S.st.demo ? ' <span class="demo-tag">DEMO: nothing opens</span>' : ""}</div>
      ${newOutlookOn() ? `<div class="fixmail">${ic("alert")}<span>${esc(NEW_OUTLOOK_HELP)}</span></div>` : ""}
      ${ccOptions.length ? `<div class="field"><label>Also on these emails</label>
        ${chips("to") ? `<div class="ccpick"><span class="muted" style="font-size:12.5px;align-self:center;width:28px">To</span>${chips("to")}</div>` : ""}
        ${chips("cc") ? `<div class="ccpick"><span class="muted" style="font-size:12.5px;align-self:center;width:28px">Cc</span>${chips("cc")}</div>` : ""}
        ${ownCc.length ? `<span class="hint">${esc(ownCc.map(({ c }) => c.name).join(", "))} keep${ownCc.length === 1 ? "s" : ""} the To/Cc set in their own email.</span>` : ""}</div>`
        : `<div class="muted" style="font-size:12.5px">Only the candidate. Add others under Settings → Extra recipients.</div>`}
      <div class="rcpt">${items.map(({ c }) => { const dr = draftFor(c); return `<div class="r"><div><b>${esc(c.name)}</b><div class="e">${esc(dr.to)}</div></div>
        <span class="num" style="color:var(--danger);font-weight:650">${hm(c.productive)}</span>${pill({ ...c, key: "_" })}</div>`; }).join("")}</div>
      ${flagged.map(({ c }) => `<div class="fixmail">${ic("alert")}<span class="grow">${esc(c.name)}: ${esc(c.email_issue)}</span>
        ${c.email_suggestion ? `<button class="btn sm fix-go" data-key="${esc(c.key)}" data-email="${esc(c.email_suggestion)}">Use ${esc(c.email_suggestion)}</button>` : ""}</div>`).join("")}`,
    foot: `<span class="grow"><kbd>Enter</kbd> to open · <kbd>Esc</kbd> to cancel</span><button class="btn" data-act="close-modal">Cancel</button>
      <button class="btn primary" id="go">${ic("mail")}Open ${items.length} in Outlook</button>`,
    onEnter: () => $("#go")?.click(),
    mount: () => {
      $("#go").onclick = () => {
        const picked = [...document.querySelectorAll(".go-cc:checked")].map((x) => ccOptions[+x.dataset.i]);
        const choice = { to: picked.filter((c) => c.field === "to").map((c) => c.email), cc: picked.filter((c) => c.field !== "to").map((c) => c.email) };
        closeModal(); runDrafts(items, again, choice);
      };
      document.querySelectorAll(".fix-go").forEach((b) => (b.onclick = () => {
        useEmail(b.dataset.key, b.dataset.email);
        renderRows(); renderPanel(true);
        confirmDrafts(items, { again }); // redraw with the fixed address
      }));
      $("#go").focus();
    },
  });
}

async function runDrafts(items, again = false, choice = null) {
  // one request: Nudge writes each email as a file and Windows opens them in Outlook one after another
  for (const { c } of items) { S.busy[c.key] = true; delete S.errors[c.key]; }
  renderRows(); renderBar(); renderPanel();
  const payload = items.map(({ c, d }) => {
    const dr = draftFor(c, d);
    const ownTo = S.edits[c.key] && "to" in S.edits[c.key], ownCc = S.edits[c.key] && "cc" in S.edits[c.key];
    const to = ownTo || !choice ? splitEmails(dr.to) : splitEmails(joinAddrs([ownEmail(c)], choice.to));
    const cc = ownCc || !choice ? splitEmails(dr.cc) : choice.cc;
    return { key: c.key, to, cc, subject: dr.subject, html: toHtml(dr.body, c),
      date: d.date, sheet: d.sheet, name: c.name, productive: c.productive, kind: kindOf(c) };
  });
  try {
    const r = await api("drafts_create", { items: payload, again });
    addLedger(r.entries);
    for (const e of [...r.entries, ...r.duplicates]) sel().delete(e.key);
    for (const f of r.failed) S.errors[f.key] = f.message;
    const parts = [r.entries.length && `Opening ${plural(r.entries.length, "email")} in Outlook`,
      r.duplicates.length && `${plural(r.duplicates.length, "person")} already emailed`,
      r.failed.length && `${r.failed.length} failed: ${r.failed[0].message}`].filter(Boolean);
    toast(parts.join(" · ") + (r.entries.length ? ". Check each one and press Send, then mark them sent here." : ""),
      r.failed.length ? "err" : "ok", r.entries.length ? { label: "Mark sent", run: () => openMarkSent() } : undefined);
  } catch (e) {
    for (const { c } of items) S.errors[c.key] = e.message;
    toast(e.message, "err");
  } finally {
    for (const { c } of items) delete S.busy[c.key];
    renderRows(); renderRail(); renderHead(); renderBar(); renderTop(); renderPanel(true);
  }
}

async function mark(items, status) {
  const r = await api("mark", {
    status,
    items: items.map(({ c, d }) => ({ key: c.key, date: d.date, sheet: d.sheet, name: c.name, email: ownEmail(c), productive: c.productive })),
  });
  addLedger(r.entries);
  if (status === "skipped") items.forEach(({ c }) => sel().delete(c.key));
  renderRail(); renderHead(); renderRows(); renderPanel(true); renderBar(); renderTop();
  return r.entries.length;
}

// Everyone opened in Outlook but not yet marked sent, across all days: tick the ones you sent.
function openMarkSent() {
  const waiting = Object.values(S.latest).filter((e) => e.status === "drafted").sort((a, b) => (a.at < b.at ? 1 : -1));
  if (!waiting.length) { toast("Nobody is waiting to be marked sent"); return; }
  const day = (iso) => (iso ? D(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : "");
  openModal({
    title: `Which of these did you send?`,
    body: `<p class="muted" style="margin:0">Opened in Outlook and not marked yet. Untick anyone you didn't send; they stay on the list.</p>
      <div class="rcpt">${waiting.map((e) => `<label class="r" style="grid-template-columns:auto 1fr auto auto;cursor:pointer">
        <input type="checkbox" class="ms-ck" data-key="${esc(e.key)}" checked style="width:16px;height:16px">
        <div><b>${esc(e.name)}</b><div class="e">${esc((e.to || []).join(", "))}</div></div>
        <span class="muted" style="font-size:12.5px">${esc(day(e.date))}</span>
        <span class="muted num" style="font-size:12.5px">opened ${esc(whenStr(e.at))}</span></label>`).join("")}</div>`,
    foot: `<span class="grow"></span><button class="btn" data-act="close-modal">Cancel</button><button class="btn primary" id="ms-go">${ic("check")}Mark as sent</button>`,
    onEnter: () => $("#ms-go").click(),
    mount: () => {
      const count = () => { const n = document.querySelectorAll(".ms-ck:checked").length; $("#ms-go").innerHTML = `${ic("check")}Mark ${n} as sent`; $("#ms-go").disabled = !n; };
      document.querySelectorAll(".ms-ck").forEach((x) => (x.onchange = count));
      count();
      $("#ms-go").onclick = async () => {
        const keys = [...document.querySelectorAll(".ms-ck:checked")].map((x) => x.dataset.key);
        try {
          const r = await api("mark", { status: "sent", items: keys.map((key) => ({ key })) });
          addLedger(r.entries);
          closeModal();
          renderRail(); renderHead(); renderRows(); renderPanel(true); renderBar(); renderTop(); if (S.view === "log") renderLog();
          toast(`Marked ${plural(r.entries.length, "email")} as sent`);
        } catch (e) { toast(e.message, "err"); }
      };
    },
  });
}

function openTemplates() {
  const tpls = JSON.parse(JSON.stringify(S.st.settings.templates));
  let kind = "low", lastField = null;
  const d = curDay();
  const sample = () => {
    const pick = d?.candidates.find((c) => S.focus === c.key && kindOf(c) === kind) || d?.candidates.find((c) => kindOf(c) === kind && baseOf(c) !== "ok" && (kind === "none" || c.apps?.length));
    return { c: pick || { name: "Alex Sample", first_name: "Alex", email: "alex@example.com", productive: kind === "none" ? 0 : 149, logged: kind === "none" ? 0 : 412, idle: kind === "none" ? 0 : 201, apps: kind === "none" ? [] : [["MS Teams", 84], ["ChatGPT", 40], ["MS Excel", 25]], key: "_" }, d: d || { date: new Date().toISOString().slice(0, 10), sheet: "" } };
  };
  const draw = () => {
    const { c, d: dd } = sample();
    $("#tpl-pv").innerHTML = mailPreview(baseDraft(c, dd, tpls[kind]), c);
    $("#tpl-who").textContent = `Preview for ${c.name}`;
  };
  const fields = () => {
    $("#tpl-kind").innerHTML = [["low", "Under threshold"], ["none", "No activity"]].map(([k, l]) => `<button class="${k === kind ? "on" : ""}" data-k="${k}">${l}</button>`).join("");
    $("#tpl-subject").value = tpls[kind].subject;
    $("#tpl-body").value = tpls[kind].body;
    draw();
  };
  openModal({
    title: "Email templates", wide: true,
    body: `<div style="display:flex;align-items:center;gap:12px"><div class="seg" id="tpl-kind"></div><span class="muted" style="font-size:12.5px">“No activity” is used when productive and logged are both 0:00.</span></div>
      <div class="tpl-grid">
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="field"><label>Subject</label><input class="input" id="tpl-subject"></div>
          <div class="field"><label>Body</label><textarea class="textarea" id="tpl-body" style="min-height:330px"></textarea></div>
          <div class="field"><label>Insert a field</label><div class="vars">${VAR_NAMES.map((v) => `<button data-v="${v}">{${v}}</button>`).join("")}</div>
            <span class="hint"><code class="code">{stats}</code> and <code class="code">{apps}</code> on their own line become the hours table and the top-apps list (left out when there's no app usage). Edits you made to one person's email are kept.</span></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px"><div class="section-t" id="tpl-who"></div><div class="mail" id="tpl-pv"></div></div>
      </div>`,
    foot: `<span class="grow"></span><button class="btn" data-act="close-modal">Cancel</button><button class="btn primary" id="tpl-save">Save templates</button>`,
    mount: (root) => {
      fields();
      $("#tpl-kind").onclick = (e) => { const b = e.target.closest("button"); if (b) { kind = b.dataset.k; fields(); } };
      for (const [id, f] of [["#tpl-subject", "subject"], ["#tpl-body", "body"]]) {
        const el = $(id);
        el.oninput = () => { tpls[kind][f] = el.value; draw(); };
        el.onfocus = () => { lastField = el; };
      }
      root.querySelector(".vars").onclick = (e) => {
        const b = e.target.closest("button[data-v]");
        if (!b) return;
        const el = lastField || $("#tpl-body");
        el.setRangeText(`{${b.dataset.v}}`, el.selectionStart, el.selectionEnd, "end");
        el.focus(); el.dispatchEvent(new Event("input"));
      };
      $("#tpl-save").onclick = async () => {
        try { applyState(await api("settings", { templates: tpls })); closeModal(); renderAll(); toast("Templates saved"); }
        catch (e) { toast(e.message, "err"); }
      };
    },
  });
}

function openSettings() {
  const s = S.st.settings;
  openModal({
    title: "Settings",
    body: `<div class="field"><label>Tracker link (SharePoint)</label>
        <div style="display:flex;gap:8px"><input class="input" id="s-link" value="${esc(s.link)}" placeholder="https://…sharepoint.com/:x:/…" ${S.st.demo ? "disabled" : ""} spellcheck="false">
        ${s.link && !S.st.demo ? `<button class="btn" id="s-unlink" title="Remove the saved link">${ic("trash")}Remove</button>` : ""}</div>
        <span class="hint">Paste next month's link here when the new tracker starts. The log is kept.</span></div>
      <div class="grid2">
        <div class="field"><label>Your name in the sign-off</label><input class="input" id="s-name" value="${esc(s.sender_name || "")}" placeholder="${esc(tok()?.name || "e.g. Nikhil Sharma")}">
          <span class="hint">Fills {sender_name}, the name after “Thanks,”.</span></div>
        <div class="field"><label>Threshold (h:mm)</label><input class="input num" id="s-thr" value="${hm(s.threshold_min)}"><span class="hint">People below this get an email.</span></div>
      </div>
      <div class="field"><label>Extra recipients</label>
        <div class="cclist" id="s-cc"></div>
        <div class="row-form"><input class="input" id="s-cc-new" placeholder="name@company.com" spellcheck="false" autocomplete="off">
          <select class="input" id="s-cc-field" style="width:auto"><option value="cc">Cc</option><option value="to">To</option></select>
          <button class="btn" id="s-cc-add">Add</button></div>
        <span class="hint">Added to every email: <b>To</b> goes next to the candidate's address, <b>Cc</b> in Cc. “On by default” ones are pre-ticked when you open emails; you can untick them per batch, or change one person's email.</span></div>
      <div class="field"><label>Company email domain</label><input class="input" id="s-domain" value="${esc(s.email_domain || "")}" placeholder="e.g. ccsglobaltech.com" spellcheck="false">
        <span class="hint">Addresses in the tracker on any other domain are flagged, with a one-click fix to this one.</span></div>
      <div class="field"><label>Email directory</label>
        <textarea class="input" id="s-dir" rows="6" spellcheck="false" placeholder="Sam Lee    slee@company.com&#10;Ana Ruiz    aruiz" style="font-family:var(--mono,monospace);font-size:12.5px">${esc((s.directory || []).map((e) => `${e.name}\t${e.email}`).join("\n"))}</textarea>
        <span class="hint">One person per line: name, then address. A username alone gets the company domain. These addresses replace the tracker's, matched by name.${S.wb && (s.directory || []).length ? ` ${notInDirectory().length ? `Not listed: ${esc(notInDirectory().join(", "))}.` : "Everyone in the tracker is listed."}` : ""}</span></div>
      <div class="form-err" id="s-err"></div>`,
    foot: `<span class="grow"></span><button class="btn" data-act="close-modal">Cancel</button><button class="btn primary" id="s-save">Save</button>`,
    onEnter: () => { if (document.activeElement?.id === "s-cc-new") $("#s-cc-add").click(); else $("#s-save").click(); },
    mount: () => {
      const ccList = JSON.parse(JSON.stringify(s.cc_list || []));
      const drawCc = () => {
        $("#s-cc").innerHTML = ccList.length ? ccList.map((c, i) => `<div class="ccrow">
            <span class="grow">${esc(c.email)}</span>
            <select class="input cc-field" data-i="${i}" style="width:auto;padding:3px 6px"><option value="to" ${c.field === "to" ? "selected" : ""}>To</option><option value="cc" ${c.field !== "to" ? "selected" : ""}>Cc</option></select>
            <label class="sw-l"><input type="checkbox" data-i="${i}" class="cc-def" ${c.default ? "checked" : ""}> On by default</label>
            <button class="btn icon ghost sm" data-i="${i}" title="Remove">${ic("x")}</button></div>`).join("")
          : `<div class="muted" style="font-size:12.5px;padding:6px 2px">No one yet. Add your manager or a team mailbox below.</div>`;
        $("#s-cc").querySelectorAll(".cc-def").forEach((x) => (x.onchange = () => { ccList[+x.dataset.i].default = x.checked; }));
        $("#s-cc").querySelectorAll(".cc-field").forEach((x) => (x.onchange = () => { ccList[+x.dataset.i].field = x.value; }));
        $("#s-cc").querySelectorAll("button[data-i]").forEach((b) => (b.onclick = () => { ccList.splice(+b.dataset.i, 1); drawCc(); }));
      };
      drawCc();
      $("#s-cc-add").onclick = () => {
        const v = $("#s-cc-new").value.trim(), err = $("#s-err");
        err.textContent = "";
        if (!EMAIL_RE.test(v)) { err.textContent = `“${v}” isn't a valid email address`; return; }
        if (ccList.some((c) => c.email.toLowerCase() === v.toLowerCase())) { err.textContent = `${v} is already on the list`; return; }
        ccList.push({ email: v, field: $("#s-cc-field").value, default: true });
        $("#s-cc-new").value = ""; drawCc(); $("#s-cc-new").focus();
      };
      openSettings.ccList = ccList;
      $("#s-unlink")?.addEventListener("click", async () => {
        try { applyState(await api("settings", { link: "" })); closeModal(); if (S.st.source !== "local") S.wb = null; renderAll(); toast("Link removed"); }
        catch (e) { $("#s-err").textContent = e.message; }
      });
      $("#s-save").onclick = async () => {
        const btn = $("#s-save"), err = $("#s-err");
        err.textContent = "";
        try {
          const t = parseHM($("#s-thr").value);
          if (t == null || t <= 0) throw new Error("Threshold must look like 4:00");
          btn.disabled = true; btn.innerHTML = `<span class="spinner sm"></span>Saving…`;
          const pending = $("#s-cc-new").value.trim();
          if (pending) throw new Error(`Click Add for ${pending}, or clear that box`);
          const body = { threshold_min: t, cc_list: openSettings.ccList, sender_name: $("#s-name").value.trim(),
            email_domain: $("#s-domain").value.trim(), directory_text: $("#s-dir").value };
          const link = $("#s-link").value.trim();
          if (!S.st.demo && link && link !== s.link) body.link = link;
          const r = await api("settings", body);
          applyState(r);
          if (body.link && !r.workbook) S.wb = null;
          closeModal(); renderAll();
          const missing = S.wb && S.st.settings.directory?.length ? notInDirectory() : [];
          toast(missing.length ? `Settings saved. Not in the email directory: ${missing.slice(0, 4).join(", ")}${missing.length > 4 ? ` and ${missing.length - 4} more` : ""}` : "Settings saved");
        } catch (e) {
          err.textContent = e.message;
          btn.disabled = false; btn.textContent = "Save";
        }
      };
    },
  });
}

// ------------------------------------------------------------------ actions
function setDay(sheet) {
  if (sheet === S.day) return;
  S.day = sheet; S.focus = null; S.anchor = null; store.set("day", sheet);
  ensureDefaults();
  renderRail(); renderHead(); renderRows(); renderPanel(true); renderBar();
  $("#rows").scrollTop = 0;
}
function ensureDefaults() {
  const d = curDay();
  if (!d || S.selByDay[d.sheet]) return;
  S.selByDay[d.sheet] = new Set(d.candidates.filter((c) => statusOf(c) === "low" && canSelect(c) && !issueOpen(c, draftFor(c, d))).map((c) => c.key));
}
function focusRow(key, scroll = false) {
  S.focus = key; S.tab = "preview";
  for (const tr of document.querySelectorAll("#rows tr.focus")) tr.classList.remove("focus");
  const tr = document.querySelector(`#rows tr[data-key="${CSS.escape(key)}"]`);
  tr?.classList.add("focus");
  if (scroll) tr?.scrollIntoView({ block: "nearest" });
  renderPanel(true);
}
function toggle(key, shift) {
  const s = sel(), vis = S.visible || [];
  const hit = S.byKey[key];
  if (!hit || !canSelect(hit.c)) return;
  const on = !s.has(key);
  if (shift && S.anchor && vis.includes(S.anchor)) {
    const [a, b] = [vis.indexOf(S.anchor), vis.indexOf(key)].sort((x, y) => x - y);
    for (const k of vis.slice(a, b + 1)) if (canSelect(S.byKey[k].c)) on ? s.add(k) : s.delete(k);
  } else on ? s.add(key) : s.delete(key);
  S.anchor = key;
  renderRows(); renderBar();
}
function moveFocus(step) {
  const vis = S.visible || [];
  if (!vis.length) return;
  const i = vis.indexOf(S.focus);
  focusRow(vis[i < 0 ? 0 : Math.max(0, Math.min(vis.length - 1, i + step))], true);
}

let lastRefresh = 0;
async function refresh(force = false, loud = false) {
  if (S.refreshing || S.st.source !== "sharepoint" && S.st.source !== "demo") return;
  if (!tok()) { if (loud) openToken(); return; }
  S.refreshing = true; lastRefresh = Date.now(); renderTop();
  try {
    const r = await api("refresh", { force });
    const first = !S.wb;
    setWorkbook(r.workbook);
    ensureDefaults();
    if (r.changed || first) {
      if (S.view === "log" || first) renderAll();
      else { renderRail(); renderHead(); renderRows(); renderPanel(); renderBar(); }
      if (!first && r.changed) toast("The tracker changed, so the list is updated");
    } else if (loud) toast("Already up to date");
  } catch (e) {
    if (loud || !["token_needed", "token_expired"].includes(e.code)) toast(e.message, "err");
  } finally {
    S.refreshing = false; renderTop();
  }
}

function pickFile() {
  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = ".xlsx,.xlsm";
  inp.onchange = () => inp.files[0] && openLocal(inp.files[0]);
  inp.click();
}
async function openLocal(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  try {
    const r = await api("upload", { name: file.name, data: btoa(bin), modified: new Date(file.lastModified).toISOString() });
    S.selByDay = {}; S.focus = null;
    applyState(r);
    ensureDefaults();
    S.view = "day"; store.set("view", "day");
    renderAll();
    toast(`Opened ${file.name}: ${plural(r.workbook.days.length, "day")}`);
  } catch (e) { toast(e.message, "err"); }
}

function applyState(r) {
  const { workbook, ledger, edits, ...rest } = r;
  S.st = { ...(S.st || {}), ...rest };
  if (ledger) { S.ledger = ledger; indexLedger(); }
  if (edits) S.edits = edits;
  if (workbook !== undefined) setWorkbook(workbook);
}

const ACT = {
  refresh: () => refresh(false, true),
  "mark-sent-list": () => openMarkSent(),
  "mark-sent": async (t) => {
    const h = S.byKey[t.dataset.key];
    try {
      const r = await api("mark", { status: "sent", items: [{ key: h.c.key }] });
      addLedger(r.entries);
      renderRail(); renderHead(); renderRows(); renderPanel(true); renderBar(); renderTop();
      toast(`Marked ${h.c.name} as sent`);
    } catch (e) { toast(e.message, "err"); }
  },
  token: () => openToken(),
  checks: () => openChecks(),
  view: (t) => { S.view = t.dataset.v; store.set("view", S.view); renderAll(); },
  day: (t) => setDay(t.dataset.sheet),
  filter: (t) => { S.filter = t.dataset.f; store.set("filter", S.filter); renderHead(); renderRows(); },
  focus: (t) => focusRow(t.dataset.key),
  toggle: (t, e) => { e.stopPropagation(); toggle(t.dataset.key, e.shiftKey); },
  "toggle-all": () => {
    const s = sel(), items = (S.visible || []).map((k) => S.byKey[k].c).filter(canSelect);
    const all = items.every((c) => s.has(c.key));
    items.forEach((c) => (all ? s.delete(c.key) : s.add(c.key)));
    renderRows(); renderBar();
  },
  "select-all": () => {
    const d = curDay(), s = sel();
    d?.candidates.filter((c) => isTodo(statusOf(c)) && canSelect(c)).forEach((c) => s.add(c.key));
    renderRows(); renderBar();
  },
  "clear-sel": () => { sel().clear(); renderRows(); renderBar(); },
  "draft-sel": () => confirmDrafts(selectedItems()),
  "draft-one": (t) => confirmDrafts([S.byKey[t.dataset.key]]),
  again: (t) => confirmDrafts([S.byKey[t.dataset.key]], { again: true }),
  forget: async (t) => {
    const h = S.byKey[t.dataset.key];
    await mark([h], "cleared").catch((e) => toast(e.message, "err"));
    toast(`${h.c.name} is back on the to-do list. Delete the draft in Outlook if it's still there.`);
  },
  "skip-sel": async () => {
    const items = selectedItems();
    const n = await mark(items, "skipped").catch((e) => toast(e.message, "err"));
    if (n) toast(`Skipped ${plural(n, "person")}`, "ok", { label: "Undo", run: () => mark(items, "cleared") });
  },
  "skip-one": async (t) => {
    const h = S.byKey[t.dataset.key];
    const n = await mark([h], "skipped").catch((e) => toast(e.message, "err"));
    if (n) { toast(`Skipped ${h.c.name}`, "ok", { label: "Undo", run: () => mark([h], "cleared") }); moveFocus(1); }
  },
  unskip: (t) => mark([S.byKey[t.dataset.key]], "cleared").catch((e) => toast(e.message, "err")),
  tab: (t) => { S.tab = t.dataset.t; renderPanel(true); if (S.tab === "edit") $("#panel textarea")?.focus(); },
  "reset-edit": (t) => {
    delete S.edits[t.dataset.key];
    api("edit", { key: t.dataset.key, edit: null }).catch((e) => toast(e.message, "err"));
    renderPanel(true); renderRows();
  },
  "use-email": (t) => {
    useEmail(t.dataset.key, t.dataset.email);
    renderPanel(true); renderRows(); renderBar();
  },
  ins: (t) => {
    const ta = $("#panel textarea");
    if (!ta) return;
    ta.setRangeText(`{${t.dataset.v}}`, ta.selectionStart, ta.selectionEnd, "end");
    ta.focus(); ta.dispatchEvent(new Event("input", { bubbles: true }));
  },
  "copy-mail": async (t) => {
    const { c, d } = S.byKey[t.dataset.key], dr = draftFor(c, d);
    try {
      await navigator.clipboard.write([new ClipboardItem({
        "text/html": new Blob([toHtml(dr.body, c)], { type: "text/html" }),
        "text/plain": new Blob([toText(dr.body, c)], { type: "text/plain" }),
      })]);
    } catch { await navigator.clipboard.writeText(toText(dr.body, c)); }
    toast(`Copied the email to ${dr.to}`);
  },
  "pick-file": () => pickFile(),
  "open-draft": async (t) => {
    try { await api("open_draft", { key: t.dataset.key }); toast("Opened the draft in Outlook"); }
    catch (e) { toast(e.message, "err"); }
  },
  "outlook-help": () => openModal({
    title: "Switch to classic Outlook",
    body: `<p style="margin:0">${esc(NEW_OUTLOOK_HELP)}</p>
      <ol class="howto" style="margin:0"><li><div>In new Outlook, turn off the <b>New Outlook</b> toggle at the top right.</div></li>
      <li><div>Classic Outlook opens. If it asks, sign in to your mailbox once.</div></li>
      <li><div>Come back here and open the emails; each appears as a new message in classic Outlook.</div></li></ol>`,
    foot: `<button class="btn" data-act="close-modal">Got it</button>`,
  }),
  templates: () => openTemplates(),
  settings: () => openSettings(),
  "close-modal": () => closeModal(),
  logf: (t) => { S.logFilter = t.dataset.f; renderLog(); },
  logopen: (t) => { S.logOpen = S.logOpen === t.dataset.id ? null : t.dataset.id; renderLog(); },
};

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-act]");
  if (t && ACT[t.dataset.act]) ACT[t.dataset.act](t, e);
});

document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.id === "q") { S.q = t.value; renderRows(); return; }
  if (t.id === "logq") { S.logQ = t.value; renderLog(); return; }
  if (t.dataset.f && $("#panel")?.contains(t) && S.focus) {
    saveEditField(S.focus, t.dataset.f, t.value);
    const { c } = S.byKey[S.focus];
    const pv = $("#pv");
    if (pv) pv.innerHTML = mailPreview(draftFor(c), c);
    if (t.dataset.f === "to") {
      const btn = $('#panel [data-act="draft-one"]');
      if (btn) btn.disabled = !(toValid(draftFor(c)) && canDraft());
    }
    clearTimeout(document._rowsT);
    document._rowsT = setTimeout(() => { renderRows(); renderBar(); }, 250);
  }
});

document.addEventListener("keydown", (e) => {
  if (S.modal) {
    if (e.key === "Escape") closeModal();
    else if (e.key === "Enter" && S.modal.onEnter && document.activeElement?.tagName !== "TEXTAREA") { e.preventDefault(); S.modal.onEnter(); }
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    if (S.view === "day" && selectedItems().length) { e.preventDefault(); ACT["draft-sel"](); }
    return;
  }
  const a = document.activeElement;
  if (a && /INPUT|TEXTAREA|SELECT/.test(a.tagName)) { if (e.key === "Escape") a.blur(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey || S.view !== "day" || !S.wb) return;
  const days = S.wb.days.map((d) => d.sheet), di = days.indexOf(S.day);
  const keys = {
    j: () => moveFocus(1), ArrowDown: () => moveFocus(1), k: () => moveFocus(-1), ArrowUp: () => moveFocus(-1),
    x: () => S.focus && toggle(S.focus, e.shiftKey), " ": () => S.focus && toggle(S.focus, e.shiftKey),
    "/": () => $("#q")?.focus(), r: () => refresh(false, true),
    e: () => { if (S.focus) { S.tab = "edit"; renderPanel(true); $("#panel textarea")?.focus(); } },
    "]": () => di < days.length - 1 && setDay(days[di + 1]), "[": () => di > 0 && setDay(days[di - 1]),
    1: () => ACT.filter({ dataset: { f: "todo" } }), 2: () => ACT.filter({ dataset: { f: "low" } }),
    3: () => ACT.filter({ dataset: { f: "none" } }), 4: () => ACT.filter({ dataset: { f: "drafted" } }),
    5: () => ACT.filter({ dataset: { f: "sent" } }), 6: () => ACT.filter({ dataset: { f: "all" } }),
  };
  if (keys[e.key]) { e.preventDefault(); keys[e.key](); }
});

// drop a downloaded copy anywhere
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  const f = [...(e.dataTransfer?.files || [])].find((x) => /\.xls[xm]$/i.test(x.name));
  if (f) openLocal(f); else toast("Drop an .xlsx workbook", "err");
});

// keep the time labels fresh; look for workbook changes when you come back to the tab (never touches Outlook)
setInterval(() => { if (!S.refreshing && S.wb) renderTop(); }, 30000);
setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 5 * 60000);
window.addEventListener("focus", () => {
  if (!S.st) return;
  if (Date.now() - lastRefresh > 60000) refresh();
});

// ------------------------------------------------------------------ boot
(async function boot() {
  try {
    applyState(await api("state"));
    if (!S.wb && S.st.demo) applyState(await api("refresh", { force: true }));
    ensureDefaults();
    renderAll();
    if (S.wb && tok()) refresh();
  } catch (e) {
    app.innerHTML = `<div class="onb"><div class="card narrow"><h1>Nudge couldn't start</h1><p class="lead">${esc(e.message)}</p><button class="btn primary" onclick="location.reload()">Try again</button></div></div>`;
  }
})();
