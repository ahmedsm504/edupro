// ================= core: API, auth, UI helpers, router, websocket =================
import { icon } from "./icons.js";
export const API = "/api/v1/";
export const state = { user: null, config: null, unread: 0, ws: null, wsOn: false, listeners: new Set() };

// ---------- tokens ----------
const store = {
  get access() { return localStorage.getItem("ep_access"); },
  get refresh() { return localStorage.getItem("ep_refresh"); },
  set(a, r) { localStorage.setItem("ep_access", a); if (r) localStorage.setItem("ep_refresh", r); },
  clear() { localStorage.removeItem("ep_access"); localStorage.removeItem("ep_refresh"); },
};
export const tokens = store;

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.error?.message || `خطأ ${status}`);
    this.status = status; this.code = body?.error?.code; this.details = body?.error?.details; this.body = body;
  }
}

let refreshing = null;
async function refreshToken() {
  if (!store.refresh) throw new ApiError(401, null);
  refreshing ??= fetch(API + "auth/token/refresh/", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: store.refresh }),
  }).then(async r => {
    const b = await r.json().catch(() => null);
    if (!r.ok) throw new ApiError(r.status, b);
    store.set(b.access, b.refresh);
  }).finally(() => { refreshing = null; });
  return refreshing;
}

export async function api(path, { method = "GET", body, form, query, auth = true, retry = true } = {}) {
  let url = path.startsWith("http") || path.startsWith("/") ? path : API + path;
  if (query) {
    const q = new URLSearchParams(Object.entries(query).filter(([, v]) => v !== "" && v != null));
    if ([...q].length) url += (url.includes("?") ? "&" : "?") + q;
  }
  const headers = { "Accept-Language": "ar" };
  if (auth && store.access) headers.Authorization = `Bearer ${store.access}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch(url, { method, headers, body: payload });
  if (r.status === 204) return null;
  const data = await r.json().catch(() => null);
  if (r.status === 401 && auth && retry && store.refresh && data?.error?.code === "token_not_valid") {
    try { await refreshToken(); } catch { logout(); throw new ApiError(401, data); }
    return api(path, { method, body, form, query, auth, retry: false });
  }
  if (!r.ok) throw new ApiError(r.status, data);
  return data;
}
// رفع ملفات كبيرة (فيديو) مع نسبة التقدم — fetch مبيدّيش progress فبنستخدم XHR
export function upload(path, form, { method = "POST", onProgress } = {}) {
  const send = () => new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open(method, path.startsWith("/") ? path : API + path);
    if (store.access) x.setRequestHeader("Authorization", `Bearer ${store.access}`);
    x.setRequestHeader("Accept-Language", "ar");
    x.upload.onprogress = e => e.lengthComputable && onProgress?.(Math.round(e.loaded * 100 / e.total), e);
    x.onload = () => {
      let data = null; try { data = JSON.parse(x.responseText); } catch {}
      if (x.status >= 200 && x.status < 300) resolve(data); else reject(new ApiError(x.status, data));
    };
    x.onerror = () => reject(new ApiError(0, { error: { message: "النت فصل أثناء الرفع — جرّب تاني" } }));
    x.send(form);
  });
  return send().catch(async e => {
    if (e.status === 401 && store.refresh) { await refreshToken(); return send(); }
    throw e;
  });
}
// helper: لما الرد paginated يرجع results، غير كده يرجع الـ array
export const list = d => Array.isArray(d) ? d : (d?.results ?? []);

export async function login(identifier, password) {
  const d = await api("auth/login/", { method: "POST", body: { identifier, password }, auth: false });
  store.set(d.access, d.refresh);
  state.user = d.user;
  return d.user;
}
export async function logout() {
  try { if (store.refresh) await api("auth/logout/", { method: "POST", body: { refresh: store.refresh }, retry: false }); } catch {}
  store.clear(); state.user = null;
  state.ws?.close();
  location.href = "/login/";
}

// ---------- tiny template helpers ----------
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ESC[c]);
// html`...` — القيم بتتعمل لها escape تلقائياً إلا لو اتلفت بـ raw()
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = s => new Raw(s);
export function html(strings, ...vals) {
  let out = "";
  strings.forEach((s, i) => {
    out += s;
    if (i < vals.length) {
      const v = vals[i];
      if (v instanceof Raw) out += v.s;
      else if (Array.isArray(v)) out += v.map(x => (x instanceof Raw ? x.s : esc(x))).join("");
      else if (v === false || v == null) out += "";
      else out += esc(v);
    }
  });
  return raw(out);
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---------- formatting ----------
const fDate = new Intl.DateTimeFormat("ar-EG", { weekday: "long", day: "numeric", month: "long" });
const fShort = new Intl.DateTimeFormat("ar-EG", { day: "numeric", month: "short" });
const fTime = new Intl.DateTimeFormat("ar-EG", { hour: "numeric", minute: "2-digit" });
const fFull = new Intl.DateTimeFormat("ar-EG", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
export const fmt = {
  date: d => d ? fDate.format(new Date(d)) : "—",
  short: d => d ? fShort.format(new Date(d)) : "—",
  time: d => d ? fTime.format(new Date(d)) : "—",
  full: d => d ? fFull.format(new Date(d)) : "—",
  money: (v, c = "EGP") => `${Number(v || 0).toLocaleString("ar-EG", { maximumFractionDigits: 2 })} ${c === "EGP" ? "ج.م" : c}`,
  ago(d) {
    const s = (Date.now() - new Date(d)) / 1000;
    if (s < 60) return "الآن";
    if (s < 3600) return `من ${Math.floor(s / 60)} دقيقة`;
    if (s < 86400) return `من ${Math.floor(s / 3600)} ساعة`;
    return fShort.format(new Date(d));
  },
  num: v => Number(v || 0).toLocaleString("ar-EG"),
};
// درجة/من: بتتعرض شمال لليمين عشان متتقلبش في العربي
export const score = (a, b) => html`<span dir="ltr" style="unicode-bidi:isolate">${+Number(a).toFixed(2)} / ${+Number(b).toFixed(2)}</span>`;
export const WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"];
export const ROLE_AR = { admin: "مدير", supervisor: "مشرف", teacher: "مدرس", student: "طالب" };

const STATUS = {
  // sessions
  scheduled: ["مجدولة", "b-blue"], live: ["جارية الآن", "b-live"], completed: ["تمت", "b-green"], cancelled: ["ملغاة", ""],
  student_absent: ["غياب الطالب", "b-red"], teacher_absent: ["غياب المدرس", "b-red"],
  // subscriptions
  pending_payment: ["في انتظار الدفع", "b-yellow"], pending_assignment: ["جاري تحديد المدرس", "b-yellow"],
  active: ["نشط", "b-green"], paused: ["متوقف مؤقتاً", ""], expired: ["منتهي", "b-red"],
  // orders / misc
  pending: ["قيد الانتظار", "b-yellow"], paid: ["مدفوع", "b-green"], failed: ["فشل", "b-red"], refunded: ["مسترد", ""],
  approved: ["معتمد", "b-green"], rejected: ["مرفوض", "b-red"], suspended: ["موقوف", "b-red"],
  draft: ["مسودة", ""], pending_review: ["قيد المراجعة", "b-yellow"], published: ["منشور", "b-green"],
  in_progress: ["جاري الحل", "b-blue"], submitted: ["مستني التصحيح", "b-yellow"], graded: ["اتصحح", "b-green"],
  done: ["تمت", "b-green"],
  // lesson access
  free: ["مجاني للكل", "b-green"], members: ["للمسجلين", "b-blue"],
};
export const badge = s => { const [t, c] = STATUS[s] || [s, ""]; return html`<span class="badge ${c}">${t}</span>`; };
export const avatar = (u, cls = "") => u?.avatar
  ? html`<img class="avatar ${cls}" src="${u.avatar}" alt="">`
  : html`<span class="avatar ${cls}">${(u?.full_name || "؟").replace(/^(أ\.|د\.|م\.|الشيخ)\s*/, "").slice(0, 1)}</span>`;

// ---------- UI feedback ----------
export function toast(msg, kind = "") {
  let box = $(".toasts");
  if (!box) { box = document.createElement("div"); box.className = "toasts"; box.setAttribute("role", "status"); document.body.append(box); }
  const t = document.createElement("div");
  t.className = `toast ${kind}`; t.textContent = msg;
  box.append(t);
  setTimeout(() => t.remove(), 4200);
}
export const fail = e => toast(e?.message || "حصل خطأ غير متوقع", "bad");

export function modal(title, body, { wide = false, onMount } = {}) {
  const o = document.createElement("div");
  o.className = "overlay";
  o.innerHTML = html`<div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-label="${title}">
    <div class="modal-head"><h2>${title}</h2><button class="x" aria-label="إغلاق">×</button></div>
    <div class="modal-body">${body}</div></div>`;
  const close = () => { o.remove(); document.removeEventListener("keydown", onKey); };
  const onKey = e => { if (e.key === "Escape") close(); };
  o.addEventListener("click", e => { if (e.target === o || e.target.closest(".x")) close(); });
  document.addEventListener("keydown", onKey);
  document.body.append(o);
  o.querySelector("input,select,textarea,button:not(.x)")?.focus();
  onMount?.(o.querySelector(".modal-body"), close);
  return close;
}
export function confirmBox(text, okLabel = "تأكيد") {
  return new Promise(res => {
    const close = modal("تأكيد", html`<p>${text}</p><div class="row" style="justify-content:flex-end;margin-top:18px">
      <button class="btn ghost" data-a="no">رجوع</button><button class="btn" data-a="ok">${okLabel}</button></div>`, {
      onMount: (b, c) => b.addEventListener("click", e => {
        const a = e.target.closest("[data-a]")?.dataset.a; if (!a) return; c(); res(a === "ok");
      }),
    });
    void close;
  });
}
// يحوّل form لـ object، ويعرض أخطاء الـ validation جنب الحقول
export const formData = f => Object.fromEntries(new FormData(f).entries());
export function showErrors(f, e) {
  $$(".err", f).forEach(x => x.remove());
  if (e?.details && typeof e.details === "object") {
    for (const [k, v] of Object.entries(e.details)) {
      const inp = f.querySelector(`[name="${k}"]`);
      const msg = Array.isArray(v) ? v.join(" ") : (typeof v === "object" ? JSON.stringify(v) : v);
      const el = document.createElement("div"); el.className = "err"; el.textContent = msg;
      (inp?.closest(".field") || f).append(el);
    }
  }
  fail(e);
}
// زرار بيعمل حاجة async: يقفل نفسه لحد ما تخلص
export async function busy(btn, fn) {
  if (btn) btn.disabled = true;
  try { return await fn(); } catch (e) { fail(e); } finally { if (btn) btn.disabled = false; }
}
export const loading = () => html`<div class="spinner" aria-label="جاري التحميل"></div>`;
export const empty = (title, hint = "", ic = "") => html`<div class="empty">${ic ? raw(`<div class="ei">${icon(ic, 26)}</div>`) : ""}<b>${title}</b>${hint}</div>`;
export { icon };
export const ico = (name, size = 18) => raw(icon(name, size));
// مدة بالثواني → "12 د" أو "1:05:20"
export const dur = (sec, long = false) => {
  sec = Math.round(sec || 0);
  if (!long) return sec >= 3600 ? `${Math.floor(sec / 3600)} س ${Math.round((sec % 3600) / 60)} د` : `${Math.max(1, Math.round(sec / 60))} د`;
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (h ? `${h}:${String(m).padStart(2, "0")}` : `${m}`) + `:${String(s).padStart(2, "0")}`;
};

// ---------- router ----------
const routes = [];
export function route(pattern, view, opts = {}) {
  const keys = [];
  const re = new RegExp("^" + pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return "([^/]+)"; }) + "$");
  routes.push({ re, keys, view, ...opts });
}
export function go(path) { location.hash = "#" + path; }
export function currentPath() { return location.hash.slice(1) || "/home"; }
export function match(path) {
  const [p, qs] = path.split("?");
  for (const r of routes) {
    const m = p.match(r.re);
    if (m) {
      const params = Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])]));
      return { ...r, params, query: Object.fromEntries(new URLSearchParams(qs || "")) };
    }
  }
  return null;
}

// ---------- websocket ----------
export function onEvent(fn) { state.listeners.add(fn); return () => state.listeners.delete(fn); }
let wsTimer, pingTimer, backoff = 1000;
export function connectWS() {
  if (!store.access) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/?token=${encodeURIComponent(store.access)}`);
  state.ws = ws;
  ws.onopen = () => { state.wsOn = true; backoff = 1000; emitLocal("ws.state", { on: true });
    clearInterval(pingTimer); pingTimer = setInterval(() => ws.readyState === 1 && ws.send('{"action":"ping"}'), 25000); };
  ws.onmessage = e => { try { const m = JSON.parse(e.data); emitLocal(m.event, m.data); } catch {} };
  ws.onclose = async () => {
    state.wsOn = false; emitLocal("ws.state", { on: false }); clearInterval(pingTimer);
    if (!state.user) return;
    try { await refreshToken(); } catch {}
    clearTimeout(wsTimer); wsTimer = setTimeout(connectWS, backoff); backoff = Math.min(backoff * 2, 15000);
  };
}
function emitLocal(event, data) { state.listeners.forEach(fn => { try { fn(event, data); } catch (err) { console.error(err); } }); }
export function wsSend(obj) { if (state.ws?.readyState === 1) { state.ws.send(JSON.stringify(obj)); return true; } return false; }
