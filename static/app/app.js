import { $, $$, api, avatar, connectWS, currentPath, esc, fail, go, html, login, logout, match, onEvent, raw, ROLE_AR, state,
  toast, tokens } from "./core.js";
import "./views-common.js";
import "./views-student.js";
import "./views-teacher.js";
import "./views-admin.js";
import "./views-qa.js";
import "./views-courses.js";
import "./views-room.js";
import { icon } from "./icons.js";

// [المسار، الاسم، الأيقونة]
const NAV = {
  student: [
    ["", [["/home", "الرئيسية", "home"], ["/sessions", "حصصي", "calendar"], ["/subscriptions", "اشتراكاتي", "wallet"], ["/teachers", "المدرسين", "users"]]],
    ["التعلّم", [["/courses", "الكورسات", "play"], ["/quizzes", "الواجبات والامتحانات", "clipboard"], ["/results", "نتايجي", "chart"],
      ["/certificates", "شهاداتي", "award"], ["/qa", "الأسئلة والأجوبة", "help"]]],
    ["التواصل", [["/chat", "الشات", "chat"], ["/notifications", "الإشعارات", "bell"]]],
  ],
  teacher: [
    ["", [["/home", "الرئيسية", "home"], ["/sessions", "جدولي", "calendar"], ["/students", "طلابي", "users"], ["/availability", "مواعيدي المتاحة", "clock"]]],
    ["المحتوى", [["/t-courses", "كورساتي وفيديوهاتي", "play"], ["/t-quizzes", "الواجبات والامتحانات", "clipboard"], ["/grading", "التصحيح", "grading"],
      ["/qa", "أسئلة الطلاب", "help"], ["/articles", "مقالاتي", "pen"]]],
    ["التواصل", [["/chat", "الشات", "chat"], ["/notifications", "الإشعارات", "bell"]]],
  ],
  supervisor: [
    ["", [["/home", "الرئيسية", "home"], ["/sessions", "الحصص", "calendar"], ["/subscriptions", "الاشتراكات", "wallet"]]],
    ["المهام", [["/assign", "تعيين مدرسين", "swap"], ["/trials", "الحصص التجريبية", "gift"], ["/reschedules", "تغيير المواعيد", "clock"]]],
    ["المحتوى", [["/qa-moderation", "مراجعة الأسئلة", "shield"], ["/qa", "الأسئلة والأجوبة", "help"], ["/articles", "المدونة", "pen"]]],
    ["الرقابة", [["/oversight", "مراقبة الشات", "eye"], ["/violations", "المخالفات", "flag"], ["/reports", "ساعات المدرسين", "chart"]]],
    ["التواصل", [["/chat", "الشات", "chat"], ["/notifications", "الإشعارات", "bell"]]],
  ],
  admin: [
    ["", [["/home", "الرئيسية", "home"], ["/sessions", "الحصص", "calendar"], ["/subscriptions", "الاشتراكات", "wallet"], ["/users", "المستخدمين", "users"]]],
    ["المهام", [["/approvals", "اعتماد المدرسين", "shield"], ["/assign", "تعيين مدرسين", "swap"], ["/trials", "الحصص التجريبية", "gift"],
      ["/reschedules", "تغيير المواعيد", "clock"]]],
    ["الكورسات", [["/course-review", "مراجعة الكورسات", "checkCircle"], ["/t-courses", "كل الكورسات والدروس", "play"]]],
    ["الفلوس", [["/orders", "الطلبات والمدفوعات", "money"], ["/coupons", "أكواد الخصم", "ticket"], ["/reports", "ساعات المدرسين", "chart"]]],
    ["المحتوى", [["/articles", "المدونة", "pen"], ["/qa-moderation", "مراجعة الأسئلة", "shield"], ["/qa", "الأسئلة والأجوبة", "help"]]],
    ["الرقابة", [["/oversight", "مراقبة الشات", "eye"], ["/violations", "المخالفات", "flag"]]],
    ["التواصل", [["/chat", "الشات", "chat"], ["/notifications", "الإشعارات", "bell"]]],
  ],
};

// ===================== Login =====================
const DEMO = [
  ["الإدارة", ["admin", "supervisor"]],
  ["مدرسين", ["teacher1", "teacher2", "teacher3", "pending1"]],
  ["طلاب", ["student1", "student2", "student3", "student26"]],
];

function renderLogin() {
  document.title = "تسجيل الدخول";
  document.body.innerHTML = html`<div class="login">
    <section class="login-board">
      <div class="login-brand"><img src="/static/img/logo.svg" alt="" width="40" height="40" style="border-radius:12px;box-shadow:0 0 0 1px rgba(255,255,255,.2)">${state.config?.site_name || "EduPro"}</div>
      <h1>حصصك وكورساتك وواجباتك في مكان واحد</h1>
      <p>ادخل بحسابك وهتروح على طول للوحة بتاعتك، سواء كنت طالب أو مدرس أو من الإدارة.</p>
      <ul class="login-points"><li>${raw(icon("video", 18))} حصص لايف جوه الموقع — من غير أي برنامج</li><li>${raw(icon("play", 18))} كورسات مسجلة بتكمّل من مكان ما وقفت</li>
        <li>${raw(icon("award", 18))} واجبات وامتحانات وشهادات إتمام</li></ul>
      ${state.config?.demo_login ? html`<div class="demo" aria-label="حسابات التجربة">
        ${DEMO.map(([role, users]) => html`<div class="demo-row"><div class="demo-role">${role}</div>
          <div class="chips">${users.map(u => html`<button type="button" class="chip-btn" data-u="${u}"><b>${u}</b></button>`)}</div></div>`)}
      </div>
      <div class="login-note">حسابات التجربة كلمة سرها <span dir="ltr">admin12345</span> — دوس على أي اسم يدخلك على طول.</div>` : ""}
    </section>
    <section class="login-form"><div class="login-card">
      <h2>تسجيل الدخول</h2>
      <p class="muted">باسم المستخدم أو رقم الموبايل أو الإيميل</p>
      <form id="login-form" novalidate>
        <div class="field"><label for="identifier">اسم المستخدم</label>
          <input class="input" id="identifier" name="identifier" autocomplete="username" dir="ltr" required></div>
        <div class="field"><label for="password">كلمة السر</label>
          <input class="input" id="password" name="password" type="password" autocomplete="current-password" dir="ltr" required></div>
        <div class="err hidden" id="login-err" role="alert"></div>
        <button class="btn lg block" type="submit">دخول</button>
      </form>
      <p class="auth-switch">معندكش حساب؟ <a href="/signup/">اعمل حساب طالب</a> أو <a href="/signup/?role=teacher">قدّم كمدرس</a></p>
      <p class="small muted" style="margin-top:14px"><a href="/">← الرجوع للموقع</a></p>
    </div></section>
  </div>`;
  const f = $("#login-form");
  const doLogin = async (id, pw) => {
    const err = $("#login-err"); err.classList.add("hidden");
    const btn = f.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "جاري الدخول…";
    try {
      await login(id, pw);
      // لو كان جاي من لينك معين (زي "اسأل سؤال" في الموقع) نرجّعه له بعد الدخول
      let next = "#/home";
      try { next = sessionStorage.getItem("ep_next") || next; sessionStorage.removeItem("ep_next"); } catch {}
      if (location.pathname.startsWith("/app")) { location.hash = next; location.reload(); }
      else location.replace("/app/" + next);
    }
    catch (e) { err.textContent = e.message; err.classList.remove("hidden"); btn.disabled = false; btn.textContent = "دخول"; }
  };
  f.addEventListener("submit", e => { e.preventDefault(); doLogin(f.identifier.value.trim(), f.password.value); });
  $$(".chip-btn").forEach(b => b.addEventListener("click", () => {
    f.identifier.value = b.dataset.u; f.password.value = "admin12345"; doLogin(b.dataset.u, "admin12345");
  }));
  f.identifier.focus();
}

// ===================== Signup =====================
async function renderSignup() {
  let role = new URLSearchParams(location.search).get("role") === "teacher" ? "teacher" : "student";
  document.title = "حساب جديد";
  let tree = [], subjects = [];
  try { [tree, subjects] = await Promise.all([api("curricula/", { auth: false }), api("subjects/", { auth: false })]); } catch {}
  subjects = Array.isArray(subjects) ? subjects : (subjects?.results || []);
  const gradeOpts = tree.flatMap(c => (c.stages || []).map(st => html`<optgroup label="${tree.length > 1 ? c.name + " — " : ""}${st.name}">
      ${(st.grades || []).map(g => html`<option value="${g.id}">${g.name}</option>`)}</optgroup>`));
  const paint = () => {
    document.body.innerHTML = html`<div class="login">
    <section class="login-board">
      <a class="login-brand" href="/" style="text-decoration:none"><img src="/static/img/logo.svg" alt="" width="40" height="40" style="border-radius:12px;box-shadow:0 0 0 1px rgba(255,255,255,.2)">${state.config?.site_name || "EduPro"}</a>
      ${role === "teacher" ? html`<h1>درّس طلاب من كل مكان وانت في بيتك</h1>
        <p>قدّم طلبك في دقيقتين. الإدارة بتراجع بياناتك ومؤهلاتك، وأول ما تتقبل تقدر تفتح مواعيدك وترفع كورساتك.</p>
        <ul class="login-points"><li>${raw(icon("calendar", 18))} انت اللي بتحدد مواعيدك وسعر حصتك</li>
          <li>${raw(icon("video", 18))} فصل لايف جاهز جوه الموقع — سبورة ومشاركة شاشة وتسجيل</li>
          <li>${raw(icon("play", 18))} ارفع كورسات مسجلة (فيديو أو يوتيوب) وحدد مين يشوفها</li>
          <li>${raw(icon("wallet", 18))} محفظة بأرباحك وطلب سحب في أي وقت</li></ul>
        <ol class="signup-steps"><li><b>1</b>املا البيانات</li><li><b>2</b>ارفع شهاداتك من صفحتك</li><li><b>3</b>الإدارة توافق وتبدأ</li></ol>`
      : html`<h1>ابدأ تذاكر صح من النهارده</h1>
        <p>اعمل حسابك مجاناً واختار مدرسك وموادك. مفيش أي دفع لحد ما تختار باقة أو كورس.</p>
        <ul class="login-points"><li>${raw(icon("video", 18))} حصص لايف مع مدرسين متخصصين</li>
          <li>${raw(icon("play", 18))} كورسات مسجلة وفيديوهات مجانية</li>
          <li>${raw(icon("help", 18))} اسأل أي سؤال في قسم الأسئلة والمدرسين يجاوبوك</li>
          <li>${raw(icon("award", 18))} واجبات وامتحانات وشهادات إتمام</li></ul>`}
    </section>
    <section class="login-form"><div class="login-card signup-card">
      <h2>حساب جديد</h2>
      <div class="seg role-seg" role="radiogroup" aria-label="نوع الحساب">
        <button type="button" data-role="student" class="${role === "student" ? "on" : ""}">${raw(icon("users", 16))} أنا طالب</button>
        <button type="button" data-role="teacher" class="${role === "teacher" ? "on" : ""}">${raw(icon("book", 16))} أنا مدرس</button>
      </div>
      <form id="signup-form" novalidate>
        <div class="field"><label for="full_name">الاسم بالكامل</label><input class="input" id="full_name" name="full_name" autocomplete="name" required></div>
        <div class="grid2">
          <div class="field"><label for="phone">رقم الموبايل</label><input class="input" id="phone" name="phone" type="tel" dir="ltr" autocomplete="tel" placeholder="01xxxxxxxxx" required></div>
          <div class="field"><label for="gender">النوع</label><select class="input" id="gender" name="gender"><option value="">—</option><option value="male">ذكر</option><option value="female">أنثى</option></select></div>
        </div>
        <div class="field"><label for="email">الإيميل <span class="muted small">(اختياري)</span></label><input class="input" id="email" name="email" type="email" dir="ltr" autocomplete="email"></div>
        <div class="field"><label for="password">كلمة السر</label><input class="input" id="password" name="password" type="password" dir="ltr" autocomplete="new-password" minlength="8" required>
          <div class="hint">8 حروف على الأقل، ومتبقاش أرقام بس.</div></div>
        ${role === "student" ? html`<div class="field"><label for="grade">الصف الدراسي</label>
            <select class="input" id="grade" name="grade"><option value="">اختار صفك</option>${gradeOpts}</select></div>`
        : html`<div class="field"><label>المواد اللي بتدرّسها</label>
            <div class="subject-picks">${subjects.map(sb => html`<label><input type="checkbox" name="subject_ids" value="${sb.id}"><span>${sb.name}</span></label>`)}</div></div>
          <div class="field"><label for="headline">نبذة قصيرة</label><input class="input" id="headline" name="headline" maxlength="120" placeholder="مثلاً: مدرس رياضيات ثانوي — خبرة في المراجعات النهائية"></div>
          <div class="grid2"><div class="field"><label for="experience_years">سنين الخبرة</label><input class="input" id="experience_years" name="experience_years" type="number" min="0" max="60" dir="ltr"></div><div></div></div>
          <div class="field"><label for="bio">عرّف الطلاب بيك</label><textarea class="input" id="bio" name="bio" rows="3" placeholder="مؤهلاتك، طريقتك في الشرح، الصفوف اللي بتدرّسها…"></textarea></div>`}
        <div class="err hidden" id="signup-err" role="alert"></div>
        <button class="btn lg block" type="submit">${role === "teacher" ? "ابعت طلب الانضمام" : "اعمل الحساب"}</button>
        <p class="small muted" style="margin:0">بالتسجيل انت موافق على <a href="/p/terms/" target="_blank">الشروط والأحكام</a> و<a href="/p/privacy/" target="_blank">سياسة الخصوصية</a>.</p>
      </form>
      <p class="auth-switch">عندك حساب؟ <a href="/login/">سجّل دخول</a></p>
    </div></section></div>`;
    $$(".role-seg button").forEach(b => b.addEventListener("click", () => {
      role = b.dataset.role; history.replaceState(null, "", role === "teacher" ? "/signup/?role=teacher" : "/signup/"); paint();
    }));
    const f = $("#signup-form");
    f.addEventListener("submit", async e => {
      e.preventDefault();
      const err = $("#signup-err"); err.classList.add("hidden");
      const body = { role, full_name: f.full_name.value.trim(), phone: f.phone.value.trim(), email: f.email.value.trim(),
        password: f.password.value, gender: f.gender.value };
      if (role === "student") { if (f.grade.value) body.grade = +f.grade.value; }
      else {
        body.subject_ids = $$("input[name=subject_ids]:checked", f).map(i => +i.value);
        body.headline = f.headline.value.trim(); body.bio = f.bio.value.trim();
        if (f.experience_years.value) body.experience_years = +f.experience_years.value;
      }
      if (!body.full_name || !body.phone || !body.password) { err.textContent = "الاسم والموبايل وكلمة السر مطلوبين."; err.classList.remove("hidden"); return; }
      if (role === "teacher" && !body.subject_ids.length) { err.textContent = "اختار مادة واحدة على الأقل."; err.classList.remove("hidden"); return; }
      const btn = f.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "لحظة…";
      try {
        const d = await api("auth/register/", { method: "POST", body, auth: false });
        tokens.set(d.access, d.refresh);
        location.replace("/app/#/home");
      } catch (ex) {
        err.textContent = ex.message; err.classList.remove("hidden");
        btn.disabled = false; btn.textContent = role === "teacher" ? "ابعت طلب الانضمام" : "اعمل الحساب";
      }
    });
    f.full_name.focus();
  };
  paint();
}

// ===================== Shell =====================
function renderShell() {
  const u = state.user;
  const nav = NAV[u.role] || NAV.student;
  document.body.innerHTML = html`<div class="shell">
    <aside class="side" id="side">
      <a class="brand" href="#/home"><img src="/static/img/logo.svg" alt="" width="34" height="34"><span>${state.config?.site_name || "EduPro"}</span></a>
      <a class="who" href="#/profile" style="text-decoration:none">${avatar(u)}<div><div class="name">${u.full_name}</div>
        <div class="role">${ROLE_AR[u.role]} · <span dir="ltr">${u.username}</span></div></div></a>
      ${nav.map(([group, items]) => html`${group ? html`<div class="nav-group">${group}</div>` : ""}<nav class="nav">
        ${items.map(([href, label, ic]) => html`<a href="#${href}" data-href="${href}">${raw(icon(ic, 19))}<span>${label}</span>${href === "/notifications" ? raw('<span class="count hidden" id="nav-unread"></span>') : ""}</a>`)}
      </nav>`)}
      <div class="foot">
        <a href="#/profile">${raw(icon("user", 17))}حسابي</a>
        ${u.role === "admin" ? html`<a href="/admin/" target="_blank" rel="noopener">${raw(icon("settings", 17))}لوحة Django</a>` : ""}
        ${u.role === "admin" ? html`<a href="/api/docs/" target="_blank" rel="noopener">${raw(icon("book", 17))}توثيق الـ API</a>` : ""}
        <a href="/" target="_blank" rel="noopener">${raw(icon("globe", 17))}الموقع العام</a>
        <button type="button" id="logout">${raw(icon("logout", 17))}تسجيل الخروج</button>
      </div>
    </aside>
    <div class="scrim" id="scrim"></div>
    <div class="main">
      <header class="top">
        <button class="menu-btn" id="menu" aria-label="القائمة">${raw(icon("menu", 20))}</button>
        <div class="title" id="title"></div>
        <span class="ws-state" id="ws-state" title="الاتصال اللحظي بالسيرفر"><i></i><span>متصل</span></span>
        <button class="bell" id="bell" aria-label="الإشعارات">${raw(icon("bell", 19))}<span class="dot hidden" id="unread"></span></button>
      </header>
      <main class="page" id="page"></main>
    </div>
  </div>`;
  $("#logout").onclick = logout;
  $("#bell").onclick = () => go("/notifications");
  $("#menu").onclick = () => $("#side").classList.toggle("open");
  $("#scrim").onclick = () => $("#side").classList.remove("open");
  refreshUnread();
}

export async function refreshUnread() {
  try { const d = await api("notifications/unread-count/"); setUnread(d.unread); } catch {}
}
function setUnread(n) {
  state.unread = n;
  for (const id of ["unread", "nav-unread"]) {
    const el = document.getElementById(id); if (!el) continue;
    el.textContent = n > 99 ? "99+" : n; el.classList.toggle("hidden", !n);
  }
}

let cleanup = null;
async function render() {
  if (!state.user) return;
  const path = currentPath();
  const m = match(path);
  $$(".nav a").forEach(a => a.classList.toggle("on", path.split("?")[0] === a.dataset.href || (a.dataset.href !== "/home" && path.startsWith(a.dataset.href + "/"))));
  $("#side")?.classList.remove("open");
  const page = $("#page");
  if (typeof cleanup === "function") { try { cleanup(); } catch {} }
  cleanup = null;
  if (!m || (m.roles && !m.roles.includes(state.user.role))) {
    page.innerHTML = html`<div class="empty"><b>الصفحة دي مش متاحة لحسابك</b><a href="#/home">ارجع للرئيسية</a></div>`;
    return;
  }
  $("#title").textContent = typeof m.title === "function" ? m.title(m.params) : (m.title || "");
  document.title = `${$("#title").textContent} — ${state.config?.site_name || "EduPro"}`;
  page.innerHTML = '<div class="spinner" aria-label="جاري التحميل"></div>';
  try {
    cleanup = await m.view(page, m.params, m.query);
  } catch (e) {
    console.error(e);
    page.innerHTML = html`<div class="empty"><b>${e.message || "حصل خطأ"}</b><a href="#/home">الرئيسية</a></div>`;
  }
  page.focus?.();
}

// ===================== Boot =====================
async function boot() {
  try { state.config = await api("config/", { auth: false }); } catch {}
  const isLoginUrl = location.pathname.startsWith("/login") || location.pathname.startsWith("/signup");
  if (!tokens.access) {
    if (location.pathname.startsWith("/signup")) { renderSignup(); return; }
    if (location.pathname.startsWith("/app") && location.hash.length > 2 && location.hash !== "#/home") {
      try { sessionStorage.setItem("ep_next", location.hash); } catch {}
    }
    renderLogin(); return;
  }
  try { state.user = await api("me/"); }
  catch { tokens.clear(); renderLogin(); return; }
  if (isLoginUrl) { location.replace("/app/#/home"); return; }
  renderShell();
  onEvent((ev, data) => {
    if (ev === "notification.new") {
      setUnread(state.unread + 1);
      if (!(data.type === "new_message" && currentPath().startsWith("/chat"))) toast(`${data.title}${data.body ? " — " + data.body : ""}`);
    }
    if (ev === "ws.state") $("#ws-state")?.classList.toggle("on", data.on);
  });
  connectWS();
  window.addEventListener("hashchange", render);
  render();
}
window.EP = { refreshUnread };
boot();
