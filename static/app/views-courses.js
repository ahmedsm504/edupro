// ================= الكورسات المسجلة: تصفح، مشغل الدروس، بناء الكورس، الشهادات، مراجعة الإدارة =================
import { $, $$, api, badge, busy, confirmBox, dur, empty, fail, fmt, go, html, ico, icon, list, modal, raw, route, showErrors,
  state, toast, upload } from "./core.js";
import { checkout } from "./views-student.js";

const me = () => state.user;
const isStaff = () => ["admin", "supervisor"].includes(me().role);
const T_ROLES = ["teacher", "admin", "supervisor"];
const ACCESS = {
  free: { label: "مجاني للكل", short: "مجاني", hint: "أي حد يشوفه — حتى من غير حساب. أحسن حاجة تجذب بيها طلاب جداد.", cls: "free", ic: "gift" },
  members: { label: "للمسجلين", short: "للمسجلين", hint: "لازم يعمل حساب بس (ببلاش). بيجيب لك بيانات طلاب مهتمين.", cls: "members", ic: "user" },
  paid: { label: "بعد الدفع", short: "مدفوع", hint: "مقفول لحد ما الطالب يشترك في الكورس (أو اشتراك الحصص لو مفعّل).", cls: "paid", ic: "lock" },
};
const TYPE_IC = { video: "video", pdf: "file", text: "text", quiz: "clipboard" };
const TYPE_AR = { video: "فيديو", pdf: "ملف PDF", text: "درس مكتوب", quiz: "اختبار" };
const PROVIDER_AR = { youtube: "يوتيوب", vimeo: "فيميو", bunny: "Bunny", upload: "فيديو مرفوع", direct: "رابط مباشر", other: "رابط خارجي" };

// لون الغلاف من لون المادة (ولو مفيش لون: أخضر المنصة)
function coverBg(c) {
  const col = c.subject?.color || "#13245E";
  return `background:linear-gradient(135deg, ${col} 0%, color-mix(in srgb, ${col} 65%, #000) 100%)`;
}
const youtubeId = url => (String(url || "").match(/(?:youtu\.be\/|[?&]v=|\/(?:embed|shorts|live)\/)([\w-]{11})/) || [])[1];

// ============================================================ Course card
export function courseCard(c, { progress = null, unlocked = false } = {}) {
  const off = c.old_price && Number(c.old_price) > Number(c.price) ? Math.round(100 - (c.price * 100) / c.old_price) : 0;
  const ribbon = unlocked ? html`<span class="badge b-green">${ico("unlock", 13)} مفتوح لك ضمن اشتراكك</span>`
    : c.is_free ? html`<span class="badge b-green">مجاني</span>` : off ? html`<span class="badge b-yellow">خصم ${fmt.num(off)}٪</span>` : "";
  return html`<a class="card link ccard" href="#/courses/${c.slug}">
    <div class="cover">${c.thumbnail ? html`<img src="${c.thumbnail}" alt="" loading="lazy">`
      : html`<div class="art" style="${c.subject?.color ? raw(coverBg(c)) : raw(coverBg({}))}"><span class="sub">${c.subject?.name || ""}</span><span class="play">${ico("play", 20)}</span></div>`}
      ${ribbon ? html`<span class="ribbon">${ribbon}</span>` : ""}</div>
    <div class="cbody"><b>${c.title}</b>
      <div class="meta"><span>${ico("user", 14)}${c.instructor?.full_name || ""}</span></div>
      <div class="meta"><span>${ico("layers", 14)}${fmt.num(c.lessons_count || 0)} درس</span><span>${ico("users", 14)}${fmt.num(c.students_count)} طالب</span>
        ${c.rating_count ? html`<span class="stars">${ico("star", 14)}${Number(c.rating_avg).toFixed(1)}</span>` : ""}</div></div>
    <div class="cfoot">${progress != null
      ? html`<div style="flex:1"><div class="progress"><i style="width:${progress}%"></i></div></div><span class="small muted nowrap">${fmt.num(progress)}٪ مكتمل</span>`
      : html`<span class="price">${c.is_free ? "مجاني" : fmt.money(c.price, c.currency)}${off ? html`<s>${fmt.money(c.old_price)}</s>` : ""}</span>
        <span class="small muted">${c.subject?.name || ""}</span>`}</div></a>`;
}

// ============================================================ Browse
route("/courses", async (page, _p, q) => {
  const student = me().role === "student";
  const tab = q.tab || (student ? "mine" : "all");
  const T = (k, l, ic) => html`<button class="${tab === k ? "on" : ""}" data-tab="${k}">${ico(ic, 16)}${l}</button>`;
  let body;
  if (tab === "mine") {
    const [enr, forMe] = await Promise.all([api("my/enrollments/", { query: { page_size: 100 } }), api("courses/", { query: { for_me: "true", page_size: 100 } })]);
    const enrolled = list(enr);
    const ids = new Set(enrolled.map(e => e.course.id));
    const unlocked = list(forMe).filter(c => !ids.has(c.id));
    body = html`${enrolled.length ? html`<div class="grid g3">${enrolled.map(e => courseCard(e.course, { progress: e.progress_percent }))}</div>`
        : !unlocked.length ? empty("لسه مشتركتش في كورسات", raw('<p><a class="btn" href="#/courses?tab=all">تصفح الكورسات</a></p>'), "play") : ""}
      ${unlocked.length ? html`<h2 style="margin:26px 0 12px" class="row">${ico("gift", 20)} مفتوحة لك ببلاش ضمن اشتراك الحصص</h2>
        <div class="grid g3">${unlocked.map(c => courseCard(c, { unlocked: true }))}</div>` : ""}`;
  } else {
    const d = list(await api("courses/", { query: { page_size: 60, free: tab === "free" ? "true" : "", search: q.search || "" } }));
    body = d.length ? html`<div class="grid g3">${d.map(c => courseCard(c))}</div>` : empty("مفيش كورسات بالبحث ده", "", "search");
  }
  page.innerHTML = html`<div class="page-head"><div><h1>الكورسات المسجلة</h1><p>فيديوهات شرح متقسمة لوحدات ودروس — ذاكر في الوقت اللي يناسبك وكمّل من مكان ما وقفت.</p></div>
      <form id="srch" class="row"><input class="input" name="search" placeholder="دوّر على كورس…" value="${q.search || ""}" style="width:220px"><button class="btn ghost icon" aria-label="بحث">${ico("search")}</button></form></div>
    <div class="tabs">${student ? T("mine", "كورساتي", "book") : ""}${T("all", "كل الكورسات", "layers")}${T("free", "المجانية", "gift")}</div>${body}`;
  page.querySelector(".tabs").onclick = e => { const t = e.target.closest("[data-tab]")?.dataset.tab; if (t) go(`/courses?tab=${t}`); };
  $("#srch").onsubmit = e => { e.preventDefault(); go(`/courses?tab=all&search=${encodeURIComponent(e.target.search.value)}`); };
}, { title: "الكورسات" });

// ============================================================ Player
route("/courses/:slug", async (page, { slug }, q) => {
  let c, flat, current, content, exam = null, ytPlayer, saveTimer, wmTimer, lastSaved = 0;
  const disposers = [];
  const cleanup = () => { clearInterval(saveTimer); clearInterval(wmTimer); disposers.forEach(f => f()); disposers.length = 0; try { ytPlayer?.destroy?.(); } catch {} ytPlayer = null; };

  async function loadCourse() {
    c = await api(`courses/${slug}/`);
    flat = c.sections.flatMap(s => s.lessons.map(l => ({ ...l, section: s })));
  }

  async function open(lessonId, { push = true } = {}) {
    cleanup();
    exam = null;
    current = flat.find(l => String(l.id) === String(lessonId)) || flat.find(l => !l.locked && !l.completed) || flat.find(l => !l.locked) || flat[0];
    content = null;
    if (current && !current.locked) { try { content = await api(`courses/${slug}/lessons/${current.id}/`); } catch (e) { fail(e); } }
    if (push && current) history.replaceState(null, "", `#/courses/${slug}?lesson=${current.id}`);
    render();
    if (push) scrollStage();
  }
  // على الموبايل المحتوى فوق والقايمة تحت: نطلع لفوق لما يفتح درس
  const scrollStage = () => { if (innerWidth <= 980) $(".stage", page)?.scrollIntoView({ behavior: "smooth", block: "start" }); };

  // امتحان آخر الوحدة
  function openExam(sectionId, { push = true } = {}) {
    cleanup();
    const s = c.sections.find(x => String(x.id) === String(sectionId));
    if (!s?.exam) return open(null);
    exam = s; content = null; current = null;
    if (push) history.replaceState(null, "", `#/courses/${slug}?exam=${s.id}`);
    render();
    if (push) scrollStage();
  }

  const startQuiz = (btn, qid) => busy(btn, async () => { const a = await api(`quizzes/${qid}/start/`, { method: "POST" }); go(`/attempts/${a.id}`); });

  // كارت الكويز/الامتحان: الحالة + زرار البدء
  function quizCard(qz, { unit = false } = {}) {
    const student = me().role === "student";
    const left = qz.max_attempts ? qz.max_attempts - qz.attempts : null;
    const status = qz.passed ? html`<span class="qstate ok">${ico("check", 15)} نجحت${qz.best_percent != null ? ` · ${fmt.num(qz.best_percent)}٪` : ""}</span>`
      : qz.pending ? html`<span class="qstate wait">${ico("clock", 15)} مستني تصحيح المدرس</span>`
      : qz.attempts ? html`<span class="qstate bad">${ico("x", 15)} أعلى نتيجة ${fmt.num(qz.best_percent || 0)}٪ — محتاج ${fmt.num(qz.pass_percent)}٪</span>` : "";
    const locked = qz.locked;
    const lockMsg = unit ? (qz.lock_reason === "unit" ? "خلّص كل دروس الوحدة الأول وبعدها الامتحان هيتفتح."
      : "خلّص دروس الوحدة وانجح في الكويزات اللي قبله الأول.") : "لازم تنجح في الكويز أو الامتحان اللي قبله الأول.";
    return html`<div class="quiz-card ${unit ? "unit" : ""} ${qz.passed ? "passed" : ""}">
      <span class="qi">${ico(unit ? "award" : "clipboard", 22)}</span>
      <div class="qb"><div class="qk">${unit ? "امتحان الوحدة" : "كويز الدرس"}${qz.required ? html` <span class="req">${unit ? "مطلوب عشان تكمّل الوحدة اللي بعدها" : "مطلوب عشان تكمّل"}</span>` : ""}</div>
        <b>${qz.title}</b>
        <div class="meta"><span>${fmt.num(qz.questions_count)} سؤال</span><span>النجاح من ${fmt.num(qz.pass_percent)}٪</span>
          ${qz.time_limit_minutes ? html`<span>${fmt.num(qz.time_limit_minutes)} دقيقة</span>` : ""}
          ${left != null ? html`<span>${left > 0 ? `باقي ${fmt.num(left)} محاولة` : "خلصت المحاولات"}</span>` : ""}</div>
        ${status}${locked ? html`<div class="small muted" style="margin-top:6px">${ico("lock", 13)} ${lockMsg}</div>` : ""}</div>
      ${student && c.access.full ? html`<button class="btn ${qz.passed ? "ghost" : "now"}" data-quiz="${qz.id}" ${locked || (left != null && left <= 0) || qz.pending ? "disabled" : ""}>
        ${qz.passed ? "حلّه تاني" : qz.attempts ? "حاول تاني" : unit ? "ابدأ الامتحان" : "ابدأ الكويز"}</button>`
        : !student ? html`<a class="btn ghost sm" href="#/t-quizzes/${qz.id}">${ico("edit", 15)} الأسئلة</a>` : ""}</div>`;
  }

  const saveProgress = async (pos, { completed = false, duration } = {}) => {
    if (completed && current.quiz?.required && !current.quiz.passed) {
      // الدرس ده بيخلص بالنجاح في الكويز — نحفظ المكان بس ونفكّره
      completed = false;
      if (!current._quizHint) { current._quizHint = true; toast("خلصت الفيديو 👌 حل كويز الدرس عشان الدرس اللي بعده يتفتح"); }
    }
    if (!c.is_enrolled && c.access.via !== "subscription" && !(c.is_free && me().role === "student")) return;
    if (me().role !== "student") return;
    try {
      const r = await api(`courses/${slug}/lessons/${current.id}/progress/`, { method: "POST", body: { position_seconds: Math.floor(pos || 0), completed, duration_seconds: duration ? Math.round(duration) : undefined } });
      if (completed && !current.completed) {
        current.completed = true; flat.find(l => l.id === current.id).completed = true;
        if (r?.progress_percent != null) c.progress_percent = r.progress_percent;
        refreshOutline();
        toast(c.progress_percent === 100 ? "مبروك! خلصت الكورس كله 🎓" : "عاش 👏 الدرس اتعلّم عليه إنه خلص", "good");
        if (c.progress_percent === 100) { await loadCourse(); render(); }
      }
    } catch {}
  };

  function stageHTML() {
    if (exam) return html`<div class="exam-stage"><div class="es-top"><span class="es-ic">${ico("award", 30)}</span>
        <div><div class="small" style="opacity:.8">${exam.title}</div><h2>امتحان الوحدة</h2>
        <p>امتحان شامل على دروس الوحدة. ${exam.exam.required ? "لازم تنجح فيه عشان الوحدة اللي بعدها تتفتح." : ""}</p></div></div>
      ${quizCard(exam.exam, { unit: true })}</div>`;
    if (!current) return html`<div class="panel">${empty("الكورس لسه مفيهوش دروس", "", "layers")}</div>`;
    if (current.locked && current.lock_reason === "sequence") {
      const b = blocker();
      return html`<div class="locked-stage seq"><div><div class="lk">${ico("lock", 28)}</div>
        <h2>الدرس ده هيتفتح بعد ما تنجح في اللي قبله</h2>
        <p>الكورس ماشي بالترتيب: كل درس بعده كويز قصير، وكل وحدة في آخرها امتحان. انجح فيهم عشان تكمّل.</p>
        <div class="row wrap">${b?.exam ? html`<button class="btn now lg" data-exam="${b.exam.id}">${ico("award")} روح لامتحان «${b.exam.title}»</button>`
          : b?.lesson ? html`<button class="btn now lg" data-go="${b.lesson.id}">${ico("clipboard")} روح لكويز «${b.lesson.title}»</button>` : ""}</div></div></div></div>`;
    }
    if (current.locked) {
      const login = current.lock_reason === "login";
      const canBuy = me().role === "student";
      return html`<div class="locked-stage"><div><div class="lk">${ico("lock", 28)}</div>
        <h2>${login ? "سجّل دخول عشان تشوف الدرس ده" : "الدرس ده للمشتركين بس"}</h2>
        <p>${login ? "الدرس ده ببلاش لأي حد عنده حساب." : c.included_in_subscription
          ? `اشترك في الكورس، أو اشترك في الحصص اللايف مع ${c.instructor.full_name} والكورس كله هيتفتح لك ببلاش.`
          : `اشترك في الكورس وكل الدروس (${fmt.num(flat.length)} درس) هتتفتح لك على طول.`}</p>
        <div class="row wrap">${canBuy ? html`<button class="btn now lg" data-buy>${ico("unlock")} ${c.is_free ? "اشترك مجاناً" : `اشترك بـ ${fmt.money(c.price, c.currency)}`}</button>` : ""}
          ${canBuy && c.included_in_subscription ? html`<a class="btn ghost lg" href="#/subscribe?teacher=${c.instructor.id}&subject=${c.subject.id}" style="background:transparent;color:#fff;border-color:rgba(255,255,255,.35)">${ico("calendar")} اشترك في الحصص</a>` : ""}
          ${flat.some(l => !l.locked) ? html`<button class="btn ghost lg" data-free style="background:transparent;color:#fff;border-color:rgba(255,255,255,.35)">${ico("gift")} شوف الدروس المجانية</button>` : ""}</div></div></div>`;
    }
    if (!content) return html`<div class="panel">${empty("مقدرناش نحمّل الدرس", "جرّب تاني بعد شوية", "info")}</div>`;
    const wm = content.watermark ? html`<span class="wm" id="wm">${content.watermark}</span>` : "";
    if (content.type === "video") {
      if (content.stream_url) return html`<div class="video" id="vbox"><video id="vid" controls playsinline preload="metadata" controlslist="nodownload noplaybackrate" disablepictureinpicture
          src="${content.stream_url}" poster=""></video>${wm}</div>`;
      if (content.embed_url) {
        const src = content.embed_url + (content.video_provider === "youtube" ? `&start=${content.position_seconds || 0}&origin=${encodeURIComponent(location.origin)}` : "");
        return html`<div class="video" id="vbox"><iframe id="yt" src="${src}" title="${content.title}" allow="accelerometer; autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>${wm}</div>`;
      }
      if (content.video_provider === "direct" && content.external_url) return html`<div class="video" id="vbox"><video id="vid" controls playsinline src="${content.external_url}"></video>${wm}</div>`;
      if (content.external_url) return html`<div class="locked-stage"><div><div class="lk">${ico("external", 26)}</div><h2>الفيديو على موقع تاني</h2>
        <p>المدرس حط رابط لفيديو برا المنصة.</p><a class="btn now lg" href="${content.external_url}" target="_blank" rel="noopener">افتح الفيديو</a></div></div>`;
    }
    if (content.type === "pdf" && content.attachment_url) return html`<iframe class="pdf-frame" src="${content.attachment_url}" title="${content.title}"></iframe>`;
    return html`<div class="panel lesson-text">${raw(content.content_html || "")}</div>`;
  }

  const idx = () => flat.indexOf(current);
  // أول كويز/امتحان مطلوب لسه ما اتعدّاش قبل الدرس الحالي
  const blocker = () => {
    for (const sec of c.sections) {
      for (const l of sec.lessons) {
        if (current && l.id === current.id) return null;
        if (l.quiz?.required && !l.quiz.passed) return { lesson: flat.find(x => x.id === l.id) };
      }
      if (sec.exam?.required && !sec.exam.passed) return { exam: sec };
    }
    return null;
  };
  const prev = () => flat[idx() - 1], next = () => flat[idx() + 1];
  // الخطوة اللي بعد الدرس: لو آخر درس في وحدة ليها امتحان → الامتحان، غير كده الدرس اللي بعده
  const nextStep = () => {
    const n = next();
    if (current && current.section.exam && (!n || n.section.id !== current.section.id)) return { exam: current.section.id };
    return n;
  };

  function outlineHTML() {
    const total = flat.length, done = flat.filter(l => l.completed).length;
    const exams = c.sections.filter(s => s.exam).length;
    return html`<div class="outline-head"><div class="row between"><b>محتوى الكورس</b><span class="small muted">${fmt.num(done)} من ${fmt.num(total)} درس${exams ? ` · ${fmt.num(exams)} امتحان` : ""}</span></div>
      ${c.access.full && me().role === "student" ? html`<div class="progress"><i style="width:${c.progress_percent}%"></i></div>` : ""}</div>
      <div class="outline-body">${c.sections.map((s, si) => {
        const ls = flat.filter(l => l.section.id === s.id);
        const open = ls.some(l => l.id === current?.id) || exam?.id === s.id || (!current && !exam && si === 0);
        const secDur = ls.reduce((a, l) => a + (l.duration_seconds || 0), 0);
        return html`<details class="osec" ${open ? "open" : ""}><summary><span>${s.title}<br><small>${fmt.num(ls.length)} درس${secDur ? ` · ${dur(secDur)}` : ""}</small></span>${raw(icon("down", 18, "chev"))}</summary>
          ${ls.map(l => html`<button class="les ${l.id === current?.id ? "on" : ""} ${l.completed ? "done" : ""} ${l.locked ? "locked" : ""}" data-l="${l.id}" aria-current="${l.id === current?.id ? "true" : "false"}">
            <span class="st">${ico(l.completed ? "check" : l.locked ? "lock" : TYPE_IC[l.type] || "video", 14)}</span>
            <span class="lt">${l.title}</span>
            <span class="lm">${l.duration_seconds ? html`<span>${dur(l.duration_seconds)}</span>` : ""}
              ${l.quiz ? html`<span class="qtag ${l.quiz.passed ? "ok" : ""}" title="كويز بعد الدرس">${ico(l.quiz.passed ? "check" : "clipboard", 12)}كويز</span>` : ""}
              ${!c.access.full && l.access !== "paid" ? html`<span class="acc-${l.access}">${ACCESS[l.access].short}</span>` : ""}</span></button>`)}
          ${s.exam ? html`<button class="les exam-row ${exam?.id === s.id ? "on" : ""} ${s.exam.passed ? "done" : ""} ${s.exam.locked ? "locked" : ""}" data-exam="${s.id}">
            <span class="st">${ico(s.exam.passed ? "check" : s.exam.locked ? "lock" : "award", 14)}</span>
            <span class="lt">امتحان الوحدة</span><span class="lm">${s.exam.passed ? html`<span class="qtag ok">${fmt.num(s.exam.best_percent || 0)}٪</span>` : html`<span>${fmt.num(s.exam.questions_count)} سؤال</span>`}</span></button>` : ""}</details>`;
      })}</div>`;
  }
  const refreshOutline = () => { const o = $("#outline", page); if (o) o.innerHTML = outlineHTML().s; };

  function render() {
    const student = me().role === "student";
    const head = c.access.full
      ? html`<div class="stack" style="min-width:240px">${c.certificate_code ? html`<a class="btn now" href="/certificates/${c.certificate_code}/" target="_blank">${ico("award")} شهادتك جاهزة</a>`
          : student ? html`<div class="row between small"><span class="muted">تقدّمك</span><b>${fmt.num(c.progress_percent)}٪</b></div><div class="progress lg"><i style="width:${c.progress_percent}%"></i></div>` : ""}
          ${c.access.via === "subscription" ? html`<span class="badge b-green">${ico("unlock", 13)} مفتوح ضمن اشتراك الحصص</span>` : ""}
          ${c.access.via === "owner" ? html`<span class="badge b-purple">${ico("eye", 13)} بتعاين الكورس كمدرس/إدارة</span>` : ""}</div>`
      : student ? html`<div class="row wrap"><button class="btn now lg" data-buy>${ico("unlock")} ${c.is_free ? "اشترك مجاناً" : `اشترك بـ ${fmt.money(c.price, c.currency)}`}</button>
          ${c.old_price ? html`<s class="muted">${fmt.money(c.old_price)}</s>` : ""}</div>` : "";
    page.innerHTML = html`<div class="crumbs"><a href="#/courses">الكورسات</a>${ico("arrowNext", 14)}<span>${c.subject.name}</span></div>
      <div class="course-top"><div><h1>${c.title}</h1>
        <div class="meta" style="margin-top:6px"><span>${ico("user", 15)}${c.instructor.full_name}</span><span>${ico("layers", 15)}${fmt.num(flat.length)} درس</span>
          ${c.total_duration_seconds ? html`<span>${ico("clock", 15)}${dur(c.total_duration_seconds)}</span>` : ""}<span>${ico("users", 15)}${fmt.num(c.students_count)} طالب</span>
          ${c.rating_count ? html`<span class="stars">${ico("star", 15)}${Number(c.rating_avg).toFixed(1)} (${fmt.num(c.rating_count)})</span>` : ""}
          ${!c.access.full && c.free_lessons_count ? html`<span class="acc-free">${ico("gift", 15)}${fmt.num(c.free_lessons_count)} درس مجاني</span>` : ""}</div></div>${head}</div>
      <div class="player"><div class="stage">
        ${stageHTML()}
        ${exam ? html`<div class="lesson-head"><div><div class="small muted">${exam.title}</div><h2>امتحان الوحدة</h2></div>
          <div class="lesson-actions">${(() => { const last = [...flat].reverse().find(l => l.section.id === exam.id); return last ? html`<button class="btn ghost" data-go="${last.id}">${ico("arrowPrev", 16)} آخر درس</button>` : ""; })()}
            ${(() => { const n = flat.find(l => c.sections.indexOf(l.section) > c.sections.indexOf(exam)); return n ? html`<button class="btn ${exam.exam.passed ? "" : "ghost"}" data-go="${n.id}">الوحدة اللي بعدها ${ico("arrowNext", 16)}</button>` : ""; })()}</div></div>` : ""}
        ${current ? html`<div class="lesson-head"><div><div class="small muted">${current.section.title} · الدرس ${fmt.num(idx() + 1)} من ${fmt.num(flat.length)}</div><h2>${current.title}</h2></div>
          <div class="lesson-actions">
            ${prev() ? html`<button class="btn ghost" data-go="${prev().id}">${ico("arrowPrev", 16)} السابق</button>` : ""}
            ${content && student && c.access.full ? (current.quiz?.required && !current.quiz.passed
              ? html`<a class="btn" href="#quizbox" id="toquiz">${ico("clipboard", 16)} حل كويز الدرس عشان تكمّل</a>`
              : html`<button class="btn ${current.completed ? "ghost" : ""}" id="done" ${current.completed ? "disabled" : ""}>${ico("check", 16)} ${current.completed ? "خلّصته" : "خلّصت الدرس"}</button>`) : ""}
            ${nextStep() ? html`<button class="btn ${current.completed || !content ? "" : "ghost"}" ${raw(nextStep().exam ? `data-exam="${nextStep().exam}"` : `data-go="${nextStep().id}"`)}>${nextStep().exam ? "امتحان الوحدة" : "التالي"} ${ico("arrowNext", 16)}</button>` : ""}</div></div>` : ""}
        ${current && current.quiz && !current.locked ? html`<div id="quizbox">${quizCard(current.quiz)}</div>` : ""}
        ${exam ? "" : content ? html`<div class="panel"><div class="tabs" id="ltabs" style="margin-top:-6px">
            <button class="on" data-t="about">${ico("info", 16)}عن الدرس</button>${student ? html`<button data-t="notes">${ico("note", 16)}ملاحظاتي</button>` : ""}
            <button data-t="course">${ico("book", 16)}عن الكورس</button></div><div id="lpane"></div></div>`
          : html`<div class="panel"><h2 style="margin-bottom:8px">عن الكورس</h2>${aboutCourse()}</div>`}
      </div>
      <aside class="outline" id="outline">${outlineHTML()}</aside></div>`;
    wire();
  }

  function aboutCourse() {
    return html`<p style="margin-top:0">${c.description || c.short_description || ""}</p>
      ${c.what_you_learn?.length ? html`<h3 style="margin:10px 0 6px">هتتعلم إيه</h3><ul class="checklist">${c.what_you_learn.map(x => html`<li class="ok"><span class="ck">${ico("check", 13)}</span>${x}</li>`)}</ul>` : ""}
      ${c.included_in_subscription ? html`<div class="callout good" style="margin-top:14px">${ico("gift")}<div>الكورس ده مفتوح ببلاش لأي طالب عنده اشتراك حصص لايف مع ${c.instructor.full_name}.</div></div>` : ""}`;
  }

  async function pane(t) {
    $$("#ltabs button", page).forEach(b => b.classList.toggle("on", b.dataset.t === t));
    const box = $("#lpane", page);
    if (t === "about") {
      box.innerHTML = html`${content.content_html ? html`<div class="lesson-text">${raw(content.content_html)}</div>` : html`<p class="muted">مفيش ملاحظات مكتوبة للدرس ده.</p>`}
        ${content.attachment_url ? html`<div class="attach" style="margin-top:12px"><span class="fi">${ico("file", 20)}</span><div style="flex:1;min-width:0"><b>ملف مرفق مع الدرس</b><div class="small muted ltr" style="text-align:start">${content.attachment_name}</div></div>
          <a class="btn sm" href="${content.attachment_url}" target="_blank" rel="noopener">${ico("download", 15)} تحميل</a></div>` : ""}
        <div class="row wrap" style="margin-top:14px"><a class="btn ghost sm" href="#/qa/ask?subject=${c.subject.id}&title=${encodeURIComponent("سؤال عن درس: " + current.title)}">${ico("help", 15)} عندك سؤال عن الدرس؟ اسأل المدرسين</a></div>`.s;
    } else if (t === "course") {
      box.innerHTML = aboutCourse().s;
    } else if (t === "notes") {
      box.innerHTML = '<div class="spinner"></div>';
      const notes = await api(`courses/${slug}/lessons/${current.id}/notes/`);
      const pos = () => Math.floor($("#vid", page)?.currentTime || ytPlayer?.getCurrentTime?.() || 0);
      box.innerHTML = html`<form id="nform" class="row" style="align-items:flex-start;margin-bottom:12px"><textarea class="input" name="text" required maxlength="2000" placeholder="اكتب ملاحظة… هتتحفظ عند الثانية اللي إنت فيها في الفيديو" style="min-height:44px;flex:1"></textarea>
          <button class="btn">${ico("plus", 16)} حفظ</button></form>
        <div class="notes">${notes.length ? notes.map(n => html`<div class="note"><button class="ts" data-seek="${n.position_seconds}" title="روح للثانية دي">${dur(n.position_seconds, true)}</button>
          <div style="white-space:pre-wrap">${n.text}</div><button class="btn ghost icon sm" data-dn="${n.id}" aria-label="مسح">${ico("trash", 15)}</button></div>`) : html`<p class="muted small">ملاحظاتك الخاصة بتتحفظ هنا مربوطة بالدقيقة في الفيديو — محدش بيشوفها غيرك.</p>`}</div>`.s;
      $("#nform", page).onsubmit = async e => {
        e.preventDefault();
        await busy(e.submitter, async () => { await api(`courses/${slug}/lessons/${current.id}/notes/`, { method: "POST", body: { text: e.target.text.value, position_seconds: pos() } }); pane("notes"); });
      };
    }
  }

  function seek(sec) {
    const v = $("#vid", page);
    if (v) { v.currentTime = sec; v.play?.(); return; }
    if (ytPlayer?.seekTo) { ytPlayer.seekTo(sec, true); ytPlayer.playVideo?.(); }
  }

  function wire() {
    $("#outline", page).onclick = e => { const x = e.target.closest("[data-exam]"); if (x) return openExam(x.dataset.exam); const b = e.target.closest("[data-l]"); if (b) open(b.dataset.l); };
    page.querySelectorAll("[data-go]").forEach(b => b.onclick = () => open(b.dataset.go));
    page.querySelectorAll(".stage [data-exam], .lesson-actions [data-exam]").forEach(b => b.onclick = () => openExam(b.dataset.exam));
    page.querySelectorAll("[data-quiz]").forEach(b => b.onclick = () => startQuiz(b, b.dataset.quiz));
    $("#toquiz", page)?.addEventListener("click", e => { e.preventDefault(); $("#quizbox", page)?.scrollIntoView({ behavior: "smooth", block: "center" }); });
    page.querySelectorAll("[data-buy]").forEach(b => b.onclick = () => busy(b, async () => {
      if (c.is_free) { await api(`courses/${slug}/enroll/`, { method: "POST" }); toast("اشتركت ✅ كل الدروس اتفتحت", "good"); await loadCourse(); open(current?.id); }
      else await checkout({ kind: "course", course_id: c.id }, `/courses/${slug}`);
    }));
    $("[data-free]", page)?.addEventListener("click", () => open(flat.find(l => !l.locked).id));
    $("#done", page)?.addEventListener("click", e => busy(e.target, () => saveProgress($("#vid", page)?.currentTime || current.duration_seconds, { completed: true })));
    $("#ltabs", page)?.addEventListener("click", e => { const t = e.target.closest("[data-t]")?.dataset.t; if (t) pane(t); });
    if (content) pane("about");
    page.onclick = async e => {
      const s = e.target.closest("[data-seek]"); if (s) { seek(Number(s.dataset.seek)); window.scrollTo({ top: 0, behavior: "smooth" }); }
      const d = e.target.closest("[data-dn]");
      if (d && await confirmBox("تمسح الملاحظة؟", "مسح")) { await api(`my/notes/${d.dataset.dn}/`, { method: "DELETE" }); pane("notes"); }
    };
    // العلامة المائية: بتتحرك كل شوية عشان متتقصّش من تصوير الشاشة
    const wm = $("#wm", page), box = $("#vbox", page);
    if (wm && box) {
      const move = () => { wm.style.top = `${8 + Math.random() * 78}%`; wm.style.left = `${4 + Math.random() * 60}%`; };
      move(); wmTimer = setInterval(move, 9000);
    }
    // فيديو مرفوع: نكمّل من مكان ما وقف، ونحفظ كل 15 ثانية، ويتعلّم خلص عند 90٪
    const v = $("#vid", page);
    if (v) {
      v.addEventListener("contextmenu", e => e.preventDefault());
      v.addEventListener("loadedmetadata", () => { if (content.position_seconds && content.position_seconds < v.duration - 5) v.currentTime = content.position_seconds; });
      v.addEventListener("timeupdate", () => {
        if (Math.abs(v.currentTime - lastSaved) >= 15) { lastSaved = v.currentTime; saveProgress(v.currentTime, { duration: v.duration }); }
        if (!current.completed && v.duration && v.currentTime / v.duration > 0.9) saveProgress(v.currentTime, { completed: true, duration: v.duration });
      });
      v.addEventListener("pause", () => saveProgress(v.currentTime, { duration: v.duration }));
      v.addEventListener("ended", () => { saveProgress(v.duration, { completed: true, duration: v.duration }); if (next() && !next().locked) setTimeout(() => toast("الدرس اللي بعده جاهز ⏭"), 400); });
    }
    if ($("#yt", page) && content.video_provider === "youtube") trackYouTube();
  }

  // يوتيوب: بنستخدم IFrame API عشان نعرف الطالب وصل لفين ونحفظ تقدمه
  function trackYouTube() {
    const start = () => {
      ytPlayer = new window.YT.Player("yt", {
        events: {
          onStateChange: ev => {
            const p = ytPlayer; if (!p?.getCurrentTime) return;
            if (ev.data === 0) saveProgress(p.getDuration(), { completed: true, duration: p.getDuration() });
            if (ev.data === 2) saveProgress(p.getCurrentTime(), { duration: p.getDuration() });
          },
        },
      });
      saveTimer = setInterval(() => {
        const p = ytPlayer; if (!p?.getCurrentTime || p.getPlayerState?.() !== 1) return;
        const t = p.getCurrentTime(), d = p.getDuration();
        saveProgress(t, { duration: d, completed: !current.completed && d && t / d > 0.9 });
      }, 15000);
    };
    if (window.YT?.Player) return start();
    if (!document.getElementById("yt-api")) {
      const s = document.createElement("script"); s.id = "yt-api"; s.src = "https://www.youtube.com/iframe_api"; document.head.append(s);
    }
    const prevCb = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prevCb?.(); if ($("#yt", page)) start(); };
  }

  await loadCourse();
  if (q.exam) openExam(q.exam, { push: false });
  else await open(q.lesson, { push: false });
  return cleanup;
}, { title: "الكورس" });

// ============================================================ Certificates (student)
route("/certificates", async page => {
  const d = list(await api("my/certificates/"));
  page.innerHTML = html`<div class="page-head"><div><h1>شهاداتي</h1><p>لما تخلّص أي كورس بتاخد شهادة إتمام ليها رابط تحقق عام — تقدر تطبعها أو تبعتها لأي حد.</p></div></div>
    ${d.length ? html`<div class="grid g2">${d.map(x => html`<div class="panel cert"><span class="ci">${ico("award", 26)}</span>
      <div><b>${x.course_title}</b><div class="small muted">${x.instructor_name} · ${fmt.date(x.created_at)}${Number(x.hours) ? ` · ${x.hours} ساعة` : ""}</div><div class="small muted ltr" style="text-align:start">${x.code}</div></div>
      <a class="btn" href="${x.url}" target="_blank" rel="noopener">${ico("eye", 16)} عرض</a></div>`)}</div>`
      : empty("لسه مخدتش شهادات", raw('<p>خلّص كورس للآخر وشهادتك هتطلع لوحدها. <a href="#/courses">كورساتي</a></p>'), "award")}`;
}, { title: "شهاداتي", roles: ["student"] });

// ============================================================ Instructor: list
route("/t-courses", async (page, _p, q) => {
  const staff = isStaff();
  const st = q.status || "";
  const d = list(await api("instructor/courses/", { query: { page_size: 100, status: st } }));
  const T = (k, l) => html`<button class="${st === k ? "on" : ""}" data-st="${k}">${l}</button>`;
  page.innerHTML = html`<div class="page-head"><div><h1>${staff ? "كل الكورسات والدروس" : "كورساتي وفيديوهاتي"}</h1>
      <p>${staff ? "من هنا تقدر تفتح أي كورس وتحدد بنفسك أي درس مجاني وأي درس بعد الدفع." : "اعمل كورس، قسّمه وحدات، وارفع فيديوهات الشرح أو حط روابط يوتيوب — وحدد أي درس مجاني وأي درس بعد الدفع."}</p></div>
      ${me().role === "teacher" ? html`<button class="btn lg" id="new">${ico("plus")} كورس جديد</button>` : ""}</div>
    ${staff ? html`<div class="tabs">${T("", "الكل")}${T("pending_review", "مستني مراجعة")}${T("published", "منشور")}${T("draft", "مسودة")}${T("rejected", "مرفوض")}</div>` : ""}
    ${d.length ? html`<div class="grid g3">${d.map(c => html`<a class="card link ccard" href="#/t-courses/${c.id}">
      <div class="cover">${c.thumbnail ? html`<img src="${c.thumbnail}" alt="">` : html`<div class="art" style="${raw(coverBg({}))}"><span class="sub">${ico("layers", 22)}</span><span class="play">${ico("edit", 18)}</span></div>`}
        <span class="ribbon">${badge(c.status)}</span></div>
      <div class="cbody"><b>${c.title}</b>${staff ? html`<div class="meta"><span>${ico("user", 14)}${c.instructor?.full_name}</span></div>` : ""}
        <div class="meta"><span>${ico("layers", 14)}${fmt.num(c.sections_count)} وحدة · ${fmt.num(c.lessons_count)} درس</span><span>${ico("users", 14)}${fmt.num(c.students_count)} طالب</span></div></div>
      <div class="cfoot"><span class="price">${Number(c.price) ? fmt.money(c.price) : "مجاني"}</span>${c.included_in_subscription ? html`<span class="badge b-green">ضمن الاشتراك</span>` : ""}</div></a>`)}</div>`
      : empty(staff ? "مفيش كورسات هنا" : "لسه معملتش كورسات", staff ? "" : "دوس «كورس جديد» وابدأ بأول وحدة وأول فيديو.", "play")}`;
  page.querySelector(".tabs")?.addEventListener("click", e => { const b = e.target.closest("[data-st]"); if (b) go(`/t-courses${b.dataset.st ? `?status=${b.dataset.st}` : ""}`); });
  $("#new")?.addEventListener("click", () => courseSettings(null));
}, { title: "الكورسات", roles: T_ROLES });

async function courseSettings(c) {
  const subjects = await api("subjects/");
  const lines = a => (a || []).join("\n");
  modal(c ? "إعدادات الكورس" : "كورس جديد", html`<form class="stack lg" id="cform">
    <div class="field"><label>اسم الكورس</label><input class="input" name="title" required value="${c?.title || ""}" placeholder="مثلاً: مراجعة التفاضل والتكامل — ثالثة ثانوي"></div>
    <div class="form-grid"><div class="field"><label>المادة</label><select class="input" name="subject">${subjects.map(s => html`<option value="${s.id}" ${c?.subject === s.id ? "selected" : ""}>${s.name}</option>`)}</select></div>
      <div class="field"><label>المستوى</label><select class="input" name="level">${[["all", "كل المستويات"], ["beginner", "مبتدئ"], ["intermediate", "متوسط"], ["advanced", "متقدم"]].map(([k, l]) => html`<option value="${k}" ${c?.level === k ? "selected" : ""}>${l}</option>`)}</select></div></div>
    <div class="form-grid"><div class="field"><label>السعر بالجنيه</label><input class="input" type="number" min="0" step="1" name="price" value="${c ? Number(c.price) : 0}"><span class="hint">0 = الكورس كله مجاني</span></div>
      <div class="field"><label>السعر قبل الخصم (اختياري)</label><input class="input" type="number" min="0" step="1" name="old_price" value="${c?.old_price ? Number(c.old_price) : ""}"></div></div>
    <div class="field"><label>وصف مختصر (بيظهر في الكارت)</label><input class="input" name="short_description" maxlength="300" value="${c?.short_description || ""}"></div>
    <div class="field"><label>وصف الكورس</label><textarea class="input" name="description">${c?.description || ""}</textarea></div>
    <div class="field"><label>هيتعلم إيه؟ (كل نقطة في سطر)</label><textarea class="input" name="wyl" placeholder="حل مسائل القيم العظمى والصغرى&#10;فهم التكامل بالتعويض">${lines(c?.what_you_learn)}</textarea></div>
    <div class="field"><label>صورة الغلاف (16:9)</label><input type="file" name="thumbnail" accept="image/*">${c?.thumbnail ? html`<img src="${c.thumbnail}" alt="" style="width:180px;border-radius:8px;margin-top:6px">` : ""}</div>
    <label class="check"><input type="checkbox" name="included_in_subscription" ${c?.included_in_subscription ? "checked" : ""}> <span><b>افتح الكورس ببلاش لطلاب الحصص اللايف بتوعي</b><br><span class="hint">أي طالب عنده اشتراك حصص شغال معاك يشوف كل الدروس من غير ما يدفع تاني.</span></span></label>
    <label class="check"><input type="checkbox" name="sequential" ${c ? (c.sequential ? "checked" : "") : "checked"}> <span><b>الكورس بالترتيب</b> <span class="hint">كويز بعد كل درس وامتحان آخر كل وحدة لازم ينجح فيهم عشان يكمّل</span></span></label>
    <label class="check"><input type="checkbox" name="certificate_enabled" ${c ? (c.certificate_enabled ? "checked" : "") : "checked"}> <span><b>شهادة إتمام</b> <span class="hint">لما الطالب يخلّص الكورس كله</span></span></label>
    <div class="row end"><button class="btn lg">${c ? "حفظ" : "إنشاء الكورس"}</button></div></form>`, {
    wide: true,
    onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault();
      const f = e.target, fd = new FormData(f);
      fd.set("included_in_subscription", f.included_in_subscription.checked ? "true" : "false");
      fd.set("certificate_enabled", f.certificate_enabled.checked ? "true" : "false");
      fd.set("sequential", f.sequential.checked ? "true" : "false");
      if (!fd.get("thumbnail")?.size) fd.delete("thumbnail");
      if (!fd.get("old_price")) fd.delete("old_price");
      fd.delete("wyl");
      await busy(e.submitter, async () => {
        try {
          const saved = await upload(c ? `instructor/courses/${c.id}/` : "instructor/courses/", fd, { method: c ? "PATCH" : "POST" });
          await api(`instructor/courses/${saved.id}/`, { method: "PATCH", body: { what_you_learn: f.wyl.value.split("\n").map(x => x.trim()).filter(Boolean) } });
          close(); toast(c ? "اتحفظ ✅" : "الكورس اتعمل — ضيف أول وحدة ودرس", "good");
          if (c) location.reload(); else go(`/t-courses/${saved.id}`);
        } catch (err) { showErrors(f, err); }
      });
    }),
  });
}

// ============================================================ Instructor: course builder
route("/t-courses/:id", async (page, { id }) => {
  const canFree = () => isStaff() || state.config?.courses?.teacher_can_set_free_lessons !== false;
  let c, units;
  const load = async () => {
    [c, units] = await Promise.all([api(`instructor/courses/${id}/`), api(`instructor/courses/${id}/outline/`)]);
    render();
  };
  const allLessons = () => units.flatMap(u => u.lessons);

  function lessonRow(l, i, n, u) {
    const thumb = l.thumbnail ? html`<span class="lthumb yt">${ico("youtube", 20)}<img src="${l.thumbnail}" alt="" loading="lazy" onerror="this.remove()"></span>`
      : l.has_video_file ? html`<span class="lthumb up">${ico("video", 20)}</span>`
      : l.type === "pdf" ? html`<span class="lthumb pdf">${ico("file", 20)}</span>` : html`<span class="lthumb">${ico(TYPE_IC[l.type] || "text", 20)}</span>`;
    const src = l.type === "video" ? (PROVIDER_AR[l.video_provider] || "") : TYPE_AR[l.type];
    return html`<div class="lrow" data-lid="${l.id}">
      <span class="order"><button data-mv="-1" data-lid="${l.id}" data-u="${u.id}" ${i === 0 ? "disabled" : ""} aria-label="لفوق">${ico("up", 16)}</button>
        <button data-mv="1" data-lid="${l.id}" data-u="${u.id}" ${i === n - 1 ? "disabled" : ""} aria-label="لتحت">${ico("down", 16)}</button></span>
      ${thumb}
      <div class="lname"><b>${l.title}</b><div class="meta"><span>${ico(TYPE_IC[l.type] || "video", 13)}${src}</span>${l.duration_seconds ? html`<span>${ico("clock", 13)}${dur(l.duration_seconds)}</span>` : ""}
        ${l.attachment_name ? html`<span>${ico("file", 13)}مرفق</span>` : ""}</div></div>
      ${l.quiz_info ? html`<a class="qchip ${l.quiz_info.is_published && l.quiz_info.questions_count ? "on" : "draft"}" href="#/t-quizzes/${l.quiz_info.id}" title="كويز بعد الدرس">${ico("clipboard", 14)}كويز · ${fmt.num(l.quiz_info.questions_count)} سؤال${l.quiz_info.is_published ? "" : " · مسودة"}</a>`
        : html`<button class="qchip add" data-addquiz="${l.id}">${ico("plus", 14)}كويز</button>`}
      <select class="acc-sel ${l.access}" data-acc="${l.id}" aria-label="مين يشوف الدرس">${Object.entries(ACCESS).map(([k, a]) => html`<option value="${k}" ${l.access === k ? "selected" : ""} ${k !== "paid" && !canFree() ? "disabled" : ""}>${a.label}</option>`)}</select>
      <span class="row lacts" style="gap:4px"><button class="btn ghost icon sm" data-edit="${l.id}" aria-label="تعديل">${ico("edit", 15)}</button>
        <button class="btn danger icon sm" data-del="${l.id}" aria-label="حذف">${ico("trash", 15)}</button></span></div>`;
  }

  function render() {
    const staff = isStaff();
    const lessons = allLessons();
    const total = lessons.reduce((a, l) => a + (l.duration_seconds || 0), 0);
    const counts = { free: 0, members: 0, paid: 0 }; lessons.forEach(l => counts[l.access]++);
    const reqOk = c.checklist.filter(x => x.required).every(x => x.done);
    page.innerHTML = html`<div class="crumbs"><a href="#/t-courses">${staff ? "كل الكورسات" : "كورساتي"}</a>${ico("arrowNext", 14)}<span>${c.title}</span></div>
      <div class="page-head"><div><div class="row wrap"><h1>${c.title}</h1>${badge(c.status)}</div>
        <p>${staff ? html`${c.instructor?.full_name} · ` : ""}${Number(c.price) ? fmt.money(c.price) : "مجاني"} · ${fmt.num(units.length)} وحدة · ${fmt.num(lessons.length)} درس${total ? ` · ${dur(total)}` : ""} · ${fmt.num(c.students_count)} طالب</p></div>
        <div class="row wrap"><button class="btn ghost" id="settings">${ico("settings", 16)} إعدادات الكورس</button>
          ${lessons.length ? html`<a class="btn ghost" href="#/courses/${c.slug}">${ico("eye", 16)} شوفه زي الطالب</a>` : ""}
          ${["draft", "rejected"].includes(c.status) && !staff ? html`<button class="btn" id="submit" ${reqOk ? "" : "disabled"}>${ico("checkCircle", 16)} ابعته للمراجعة</button>` : ""}
          ${staff && c.status !== "published" ? html`<button class="btn" data-mod="approve">${ico("check", 16)} نشر</button>` : ""}
          ${staff && c.status === "pending_review" ? html`<button class="btn danger" data-mod="reject">رفض</button>` : ""}</div></div>
      ${c.rejection_reason && c.status === "rejected" ? html`<div class="callout bad" style="margin-bottom:16px">${ico("info")}<div><b>سبب الرفض:</b> ${c.rejection_reason}</div></div>` : ""}
      ${c.status === "pending_review" && !staff ? html`<div class="callout warn" style="margin-bottom:16px">${ico("clock")}<div>الكورس عند الإدارة للمراجعة. تقدر تكمّل تعديل لحد ما يتنشر.</div></div>` : ""}
      <div class="cb-layout"><div>
        ${units.map((u, ui) => html`<section class="unit" data-unit="${u.id}"><div class="unit-head"><span class="un">${fmt.num(ui + 1)}</span>
            <h3>${u.title}<small>${fmt.num(u.lessons.length)} درس${u.lessons.length ? ` · ${dur(u.lessons.reduce((a, l) => a + (l.duration_seconds || 0), 0))}` : ""}</small></h3>
            <span class="row" style="gap:4px"><button class="btn ghost icon sm" data-umv="-1" data-u="${u.id}" ${ui === 0 ? "disabled" : ""} aria-label="الوحدة لفوق">${ico("up", 15)}</button>
              <button class="btn ghost icon sm" data-umv="1" data-u="${u.id}" ${ui === units.length - 1 ? "disabled" : ""} aria-label="الوحدة لتحت">${ico("down", 15)}</button>
              <button class="btn ghost icon sm" data-uren="${u.id}" aria-label="تغيير الاسم">${ico("edit", 15)}</button>
              <button class="btn danger icon sm" data-udel="${u.id}" aria-label="حذف الوحدة">${ico("trash", 15)}</button>
              <button class="btn sm" data-add="${u.id}">${ico("plus", 15)} درس</button></span></div>
          ${u.lessons.length ? u.lessons.map((l, i) => lessonRow(l, i, u.lessons.length, u)) : html`<div class="unit-empty">الوحدة فاضية — <button class="btn ghost sm" data-add="${u.id}">${ico("plus", 14)} ضيف أول درس</button></div>`}
          ${u.exam_info ? html`<div class="exam-line"><span class="ei">${ico("award", 18)}</span><div style="flex:1;min-width:0"><b>امتحان الوحدة</b>
              <div class="small muted">${fmt.num(u.exam_info.questions_count)} سؤال · النجاح من ${fmt.num(u.exam_info.pass_percent)}٪${u.exam_info.is_published ? "" : " · مسودة — انشره من صفحة الأسئلة"}</div></div>
              <label class="check small"><input type="checkbox" data-exreq="${u.id}" ${u.exam_required ? "checked" : ""}> لازم ينجح عشان يكمّل</label>
              <a class="btn sm" href="#/t-quizzes/${u.exam_info.id}">${ico("edit", 15)} الأسئلة</a>
              <button class="btn danger icon sm" data-delexam="${u.id}" aria-label="شيل الامتحان">${ico("trash", 15)}</button></div>`
            : u.lessons.length ? html`<button class="exam-add" data-addexam="${u.id}">${ico("award", 16)} ضيف امتحان آخر الوحدة</button>` : ""}
        </section>`)}
        <form class="add-unit" id="addu"><div class="field" style="flex:1"><label>${units.length ? "وحدة جديدة" : "ابدأ بأول وحدة"}</label><input class="input" name="title" required placeholder="${units.length ? `الوحدة ${units.length + 1}: …` : "مثلاً: الوحدة الأولى — الأساسيات"}"></div>
          <button class="btn">${ico("plus", 16)} إضافة وحدة</button></form>
      </div>
      <aside class="cb-side">
        <div class="panel"><h3 style="margin-bottom:12px">جاهزية الكورس</h3><ul class="checklist">${c.checklist.map(x => html`<li class="${x.done ? "ok" : ""} ${x.required ? "req" : ""}"><span class="ck">${ico("check", 13)}</span><span>${x.label}${x.required ? "" : html` <span class="hint">(مستحسن)</span>`}</span></li>`)}</ul></div>
        <div class="panel"><h3 style="margin-bottom:8px">الكويزات والامتحانات</h3>
          <p class="small muted" style="margin:0 0 10px">ضيف كويز قصير بعد كل درس (3–5 أسئلة) وامتحان شامل آخر كل وحدة — زي نظام التقييمات الأسبوعية والشهرية في المدارس.</p>
          <label class="check"><input type="checkbox" id="seq" ${c.sequential ? "checked" : ""}> <span><b>الكورس بالترتيب</b><br><span class="hint">الطالب ميفتحش الدرس اللي بعده غير لما ينجح في كويز الدرس، ولا الوحدة اللي بعدها غير لما ينجح في امتحان الوحدة.</span></span></label>
          <div class="small" style="margin-top:8px">${fmt.num(lessons.filter(l => l.quiz_info).length)} من ${fmt.num(lessons.length)} درس عليهم كويز · ${fmt.num(units.filter(u => u.exam_info).length)} من ${fmt.num(units.length)} وحدة عليها امتحان</div></div>
        <div class="panel"><h3 style="margin-bottom:10px">مين يشوف إيه؟</h3>
          <div class="stack">${Object.entries(ACCESS).map(([k, a]) => html`<div class="row" style="align-items:flex-start"><span class="acc-sel ${k}" style="pointer-events:none;padding:3px 10px">${a.label} · ${fmt.num(counts[k])}</span></div><div class="hint" style="margin-top:-4px">${a.hint}</div>`)}</div>
          ${!canFree() ? html`<div class="callout warn" style="margin-top:10px">${ico("lock")}<div>الإدارة بس اللي تقدر تفتح دروس مجاناً.</div></div>` : ""}
          ${c.included_in_subscription ? html`<div class="callout good" style="margin-top:10px">${ico("gift")}<div>الكورس كله مفتوح لطلاب الحصص اللايف بتوعك.</div></div>` : ""}</div>
        <div class="panel"><h3 style="margin-bottom:8px">نصايح للفيديو</h3><ul class="small muted" style="margin:0;padding-inline-start:18px;line-height:1.9">
          <li>لو يوتيوب: خلّي الفيديو <b>«غير مدرج Unlisted»</b> مش «عام» — كده محدش يلاقيه غير من المنصة.</li>
          <li>الفيديو المرفوع مباشرة محمي: بيتعرض برابط مؤقت وعليه اسم الطالب.</li>
          <li>الدروس القصيرة (5–15 دقيقة) الطلاب بيكمّلوها أكتر.</li></ul></div>
      </aside></div>`;
    wire();
  }

  async function reorderUnit(uid, ids) { await api(`instructor/courses/${id}/reorder/`, { method: "POST", body: { lessons: { [uid]: ids } } }); }

  function wire() {
    $("#settings").onclick = () => courseSettings(c);
    $("#submit")?.addEventListener("click", e => busy(e.target, async () => { await api(`instructor/courses/${id}/submit/`, { method: "POST" }); toast("اتبعت للإدارة ✅", "good"); load(); }));
    page.querySelectorAll("[data-mod]").forEach(b => b.onclick = () => moderateCourse(c, b.dataset.mod, load));
    $("#addu").onsubmit = async e => {
      e.preventDefault();
      await busy(e.submitter, async () => { await api("instructor/sections/", { method: "POST", body: { course: Number(id), title: e.target.title.value, order: units.length + 1 } }); toast("الوحدة اتضافت", "good"); load(); });
    };
    page.querySelectorAll("[data-acc]").forEach(sel => sel.onchange = () => busy(sel, async () => {
      await api(`instructor/lessons/${sel.dataset.acc}/`, { method: "PATCH", body: { access: sel.value } });
      sel.className = `acc-sel ${sel.value}`; allLessons().find(l => l.id === Number(sel.dataset.acc)).access = sel.value;
      toast(`الدرس بقى «${ACCESS[sel.value].label}»`, "good");
    }));
    $("#seq")?.addEventListener("change", e => busy(e.target, async () => {
      await api(`instructor/courses/${id}/`, { method: "PATCH", body: { sequential: e.target.checked } }); c.sequential = e.target.checked;
      toast(e.target.checked ? "الكورس بقى بالترتيب" : "الدروس بقت مفتوحة من غير ترتيب", "good");
    }));
    page.querySelectorAll("[data-exreq]").forEach(cb => cb.onchange = () => busy(cb, async () => {
      await api(`instructor/sections/${cb.dataset.exreq}/`, { method: "PATCH", body: { exam_required: cb.checked } }); toast("اتحفظ", "good");
    }));
    page.onclick = async e => {
      const t = e.target.closest("button"); if (!t) return;
      const d = t.dataset;
      if (d.addquiz) return busy(t, async () => { const r = await api(`instructor/lessons/${d.addquiz}/quiz/`, { method: "POST" }); toast("اتعمل الكويز — ضيف الأسئلة وانشره", "good"); go(`/t-quizzes/${r.quiz_info.id}`); });
      if (d.addexam) return busy(t, async () => { const r = await api(`instructor/sections/${d.addexam}/exam/`, { method: "POST" }); toast("اتعمل امتحان الوحدة — ضيف الأسئلة وانشره", "good"); go(`/t-quizzes/${r.exam_info.id}`); });
      if (d.delexam) {
        if (!(await confirmBox("تشيل امتحان الوحدة؟ لو فيه طلاب حلّوه نتايجهم هتفضل محفوظة.", "شيل الامتحان"))) return;
        return busy(t, async () => { await api(`instructor/sections/${d.delexam}/exam/`, { method: "DELETE" }); load(); });
      }
      if (d.add) return lessonEditor({ section: Number(d.add) });
      if (d.edit) return lessonEditor(allLessons().find(l => l.id === Number(d.edit)));
      if (d.del) {
        if (!(await confirmBox("تحذف الدرس ده؟ لو فيه فيديو مرفوع هيتمسح كمان.", "حذف"))) return;
        return busy(t, async () => { await api(`instructor/lessons/${d.del}/`, { method: "DELETE" }); toast("اتحذف", "good"); load(); });
      }
      if (d.mv) {
        const u = units.find(x => x.id === Number(d.u)); const ids = u.lessons.map(l => l.id); const i = ids.indexOf(Number(d.lid)); const j = i + Number(d.mv);
        [ids[i], ids[j]] = [ids[j], ids[i]];
        return busy(t, async () => { await reorderUnit(u.id, ids); load(); });
      }
      if (d.umv) {
        const ids = units.map(u => u.id); const i = ids.indexOf(Number(d.u)); const j = i + Number(d.umv);
        [ids[i], ids[j]] = [ids[j], ids[i]];
        return busy(t, async () => { await api(`instructor/courses/${id}/reorder/`, { method: "POST", body: { sections: ids } }); load(); });
      }
      if (d.uren) {
        const u = units.find(x => x.id === Number(d.uren));
        return modal("اسم الوحدة", html`<form class="stack"><input class="input" name="title" required value="${u.title}"><div class="row end"><button class="btn">حفظ</button></div></form>`, {
          onMount: (b, close) => b.querySelector("form").onsubmit = async ev => { ev.preventDefault(); await api(`instructor/sections/${u.id}/`, { method: "PATCH", body: { title: ev.target.title.value } }); close(); load(); },
        });
      }
      if (d.udel) {
        const u = units.find(x => x.id === Number(d.udel));
        if (!(await confirmBox(`تحذف «${u.title}»${u.lessons.length ? ` وكل دروسها (${u.lessons.length})` : ""}؟`, "حذف الوحدة"))) return;
        return busy(t, async () => { await api(`instructor/sections/${u.id}/`, { method: "DELETE" }); load(); });
      }
    };
  }

  // ---------- lesson editor (create / edit) ----------
  function lessonEditor(l) {
    const isNew = !l.id;
    const maxMb = state.config?.courses?.video_max_upload_mb || 2048;
    let file = null, fileDur = 0;
    const srcDefault = l.has_video_file ? "upload" : "link";
    modal(isNew ? "درس جديد" : "تعديل الدرس", html`<form class="stack lg" id="lform">
      <div class="field"><label>عنوان الدرس</label><input class="input" name="title" required value="${l.title || ""}" placeholder="مثلاً: قواعد الاشتقاق"></div>
      <div class="field"><span class="label">نوع الدرس</span><div class="seg" role="radiogroup">${[["video", "فيديو شرح", "video"], ["pdf", "ملف PDF", "file"], ["text", "درس مكتوب", "text"]].map(([k, t, ic]) =>
        html`<label><input type="radio" name="type" value="${k}" ${(l.type || "video") === k ? "checked" : ""}>${ico(ic, 16)}${t}</label>`)}</div></div>
      <div id="vsec" class="stack lg">
        <div class="src-pick"><label><input type="radio" name="src" value="link" ${srcDefault === "link" ? "checked" : ""}>${ico("youtube", 22)}<span>رابط يوتيوب أو فيميو<small>الصق الرابط وخلاص</small></span></label>
          <label><input type="radio" name="src" value="upload" ${srcDefault === "upload" ? "checked" : ""}>${ico("upload", 22)}<span>ارفع فيديو من جهازك<small>محمي ومش بيتحمّل — حتى ${fmt.num(maxMb)} ميجا</small></span></label></div>
        <div id="src-link" class="stack"><div class="field"><label>رابط الفيديو</label><input class="input ltr" name="video_url" value="${l.video_url || ""}" placeholder="https://youtu.be/…" style="text-align:left">
          <span class="hint">أي شكل للرابط ينفع: youtube.com/watch · youtu.be · shorts · vimeo. خلّي فيديو يوتيوب «غير مدرج Unlisted».</span></div><div id="ytprev"></div></div>
        <div id="src-upload" class="stack"><label class="drop" id="drop"><input type="file" name="video_file" accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov,.m4v">${ico("upload", 30)}
            <div class="dt" id="dtext">${l.has_video_file ? `الفيديو الحالي: ${l.video_file_name} — اختار ملف تاني لو عايز تغيره` : "اسحب الفيديو هنا أو دوس واختار"}</div><div class="hint">MP4 أحسن صيغة · الفيديو بيتحفظ محمي</div></label>
          <div id="upwrap" class="hidden"><div class="row between small"><span id="uplabel">جاري الرفع…</span><b id="uppct">0٪</b></div><div class="upbar"><i id="upbar"></i></div></div></div>
      </div>
      <div class="form-grid"><div class="field"><label>المدة بالدقايق</label><input class="input" type="number" min="0" name="minutes" value="${l.duration_seconds ? Math.round(l.duration_seconds / 60) : ""}" placeholder="بتتحسب لوحدها للفيديو المرفوع"></div>
        <div class="field"><label>ملف مرفق (ملخص/تمارين) — اختياري</label><input type="file" name="attachment" accept=".pdf,.doc,.docx,.ppt,.pptx,.zip,image/*">
          ${l.attachment_name ? html`<label class="check small"><input type="checkbox" name="remove_attachment"> امسح المرفق الحالي (${l.attachment_name})</label>` : ""}</div></div>
      <div class="field"><span class="label">مين يشوف الدرس ده؟</span><div class="acc-pick">${Object.entries(ACCESS).map(([k, a]) =>
        html`<label class="${k !== "paid" && !canFree() ? "dis" : ""}"><input type="radio" name="access" value="${k}" ${(l.access || "paid") === k ? "checked" : ""} ${k !== "paid" && !canFree() ? "disabled" : ""}><span class="row" style="gap:6px">${ico(a.ic, 16)}${a.label}</span><small>${a.hint}</small></label>`)}</div></div>
      ${l.quiz_info ? html`<div class="callout good">${ico("clipboard")}<div style="flex:1"><b>عليه كويز:</b> ${l.quiz_info.title} · ${fmt.num(l.quiz_info.questions_count)} سؤال
          <label class="check small" style="margin-top:6px"><input type="checkbox" name="quiz_required" ${l.quiz_required !== false ? "checked" : ""}> الدرس ميخلصش غير لما الطالب ينجح في الكويز</label></div>
          <button type="button" class="btn danger sm" id="rmquiz">شيل الكويز</button></div>` : ""}
      <div class="field"><label id="clabel">ملاحظات تحت الفيديو (اختياري)</label><textarea class="input" name="content" placeholder="ملخص، قوانين، أو واجب الدرس">${l.content || ""}</textarea></div>
      <div class="row end"><button class="btn lg" id="lsave">${isNew ? "إضافة الدرس" : "حفظ التعديلات"}</button></div></form>`, {
      wide: true,
      onMount: (b, close) => {
        const f = b.querySelector("form");
        const sync = () => {
          const type = f.type.value, src = f.src.value;
          $("#vsec", b).classList.toggle("hidden", type !== "video");
          $("#src-link", b).classList.toggle("hidden", src !== "link");
          $("#src-upload", b).classList.toggle("hidden", src !== "upload");
          $("#clabel", b).textContent = type === "text" ? "نص الدرس" : type === "pdf" ? "وصف الملف (اختياري)" : "ملاحظات تحت الفيديو (اختياري)";
        };
        const preview = () => {
          const idv = youtubeId(f.video_url.value);
          $("#ytprev", b).innerHTML = idv ? html`<div class="yt-prev"><img src="https://i.ytimg.com/vi/${idv}/hqdefault.jpg" alt=""><div><b class="row" style="gap:6px">${ico("check", 16)} فيديو يوتيوب</b><div class="small muted ltr" style="text-align:start">${idv}</div></div></div>`.s
            : f.video_url.value && /youtu/.test(f.video_url.value) ? html`<div class="callout bad">${ico("info")}<div>الرابط ده مش مفهوم — انسخه من زرار «مشاركة» في يوتيوب.</div></div>`.s : "";
        };
        f.addEventListener("change", sync); sync();
        $("#rmquiz", b)?.addEventListener("click", async e => {
          if (!(await confirmBox("تشيل كويز الدرس؟", "شيل"))) return;
          await busy(e.target, async () => { await api(`instructor/lessons/${l.id}/quiz/`, { method: "DELETE" }); close(); load(); });
        });
        f.video_url.addEventListener("input", preview); preview();
        const drop = $("#drop", b), inp = f.video_file;
        const pick = fl => {
          if (!fl) return;
          if (fl.size > maxMb * 1024 * 1024) { toast(`الفيديو أكبر من ${maxMb} ميجا`, "bad"); return; }
          file = fl; $("#dtext", b).textContent = `${fl.name} — ${(fl.size / 1048576).toFixed(1)} ميجا`;
          const v = document.createElement("video"); v.preload = "metadata";
          v.onloadedmetadata = () => { fileDur = v.duration; if (fileDur && !f.minutes.value) f.minutes.value = Math.max(1, Math.round(fileDur / 60)); URL.revokeObjectURL(v.src); };
          v.src = URL.createObjectURL(fl);
          if (!f.title.value) f.title.value = fl.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
        };
        inp.addEventListener("change", () => pick(inp.files[0]));
        ["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
        ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("over"); }));
        drop.addEventListener("drop", e => pick(e.dataTransfer.files[0]));
        f.addEventListener("submit", async e => {
          e.preventDefault();
          const type = f.type.value, src = f.src.value;
          if (type === "video" && src === "upload" && !file && !l.has_video_file) return toast("اختار الفيديو اللي هترفعه", "bad");
          if (type === "video" && src === "link" && !f.video_url.value.trim()) return toast("حط رابط الفيديو", "bad");
          if (type === "pdf" && !f.attachment.files[0] && !l.attachment_name) return toast("ارفع ملف الـ PDF", "bad");
          const fd = new FormData();
          fd.append("title", f.title.value); fd.append("type", type); fd.append("access", f.access.value); fd.append("content", f.content.value);
          if (isNew) fd.append("section", l.section);
          const secs = fileDur && src === "upload" && file ? Math.round(fileDur) : Number(f.minutes.value || 0) * 60;
          fd.append("duration_seconds", String(secs));
          if (type === "video" && src === "link") fd.append("video_url", f.video_url.value.trim());
          if (type === "video" && src === "upload" && file) fd.append("video_file", file);
          if (f.attachment.files[0]) fd.append("attachment", f.attachment.files[0]);
          if (f.remove_attachment?.checked) fd.append("remove_attachment", "true");
          if (f.quiz_required) fd.append("quiz_required", f.quiz_required.checked ? "true" : "false");
          const btn = $("#lsave", b); btn.disabled = true;
          const big = file && src === "upload";
          if (big) { $("#upwrap", b).classList.remove("hidden"); }
          try {
            await upload(isNew ? "instructor/lessons/" : `instructor/lessons/${l.id}/`, fd, {
              method: isNew ? "POST" : "PATCH",
              onProgress: p => { if (!big) return; $("#upbar", b).style.width = p + "%"; $("#uppct", b).textContent = `${fmt.num(p)}٪`; if (p === 100) $("#uplabel", b).textContent = "بنحفظ الفيديو…"; },
            });
            close(); toast(isNew ? "الدرس اتضاف ✅" : "اتحفظ ✅", "good"); load();
          } catch (err) { btn.disabled = false; showErrors(f, err); }
        });
      },
    });
  }

  await load();
}, { title: "بناء الكورس", roles: T_ROLES });

function moderateCourse(c, action, after) {
  if (action === "approve") return busy(null, async () => { await api(`instructor/courses/${c.id}/moderate/`, { method: "POST", body: { action: "approve" } }); toast("الكورس اتنشر 🎉", "good"); after(); });
  modal("رفض الكورس", html`<form class="stack"><div class="field"><label>قول للمدرس محتاج يعدّل إيه</label><textarea class="input" name="reason" required></textarea></div>
    <div class="row end"><button class="btn danger">رفض وإرسال الملاحظات</button></div></form>`, {
    onMount: (b, close) => b.querySelector("form").onsubmit = async e => {
      e.preventDefault();
      await busy(e.submitter, async () => { await api(`instructor/courses/${c.id}/moderate/`, { method: "POST", body: { action: "reject", reason: e.target.reason.value } }); close(); toast("اتبعت للمدرس", "good"); after(); });
    },
  });
}

// ============================================================ Admin: review queue
route("/course-review", async page => {
  const d = list(await api("instructor/courses/", { query: { status: "pending_review", page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>مراجعة الكورسات</h1><p>الكورسات اللي المدرسين بعتوها للنشر. افتح الكورس عشان تشوف الدروس وتحدد المجاني والمدفوع قبل ما تنشر.</p></div>
      <a class="btn ghost" href="#/t-courses">${ico("layers", 16)} كل الكورسات</a></div>
    ${d.length ? html`<div class="grid g2">${d.map(c => html`<div class="panel"><div class="row between" style="align-items:flex-start"><div><b style="font-size:16px">${c.title}</b>
        <div class="meta" style="margin-top:4px"><span>${ico("user", 14)}${c.instructor?.full_name}</span><span>${ico("layers", 14)}${fmt.num(c.lessons_count)} درس</span><span>${Number(c.price) ? fmt.money(c.price) : "مجاني"}</span></div></div>${badge(c.status)}</div>
      <p class="small muted">${c.short_description || ""}</p>
      <div class="row wrap"><a class="btn ghost sm" href="#/t-courses/${c.id}">${ico("eye", 15)} راجع الدروس</a><button class="btn sm" data-m="approve" data-id="${c.id}">${ico("check", 15)} نشر</button>
        <button class="btn danger sm" data-m="reject" data-id="${c.id}">رفض</button></div></div>`)}</div>` : empty("مفيش كورسات مستنية مراجعة", "", "checkCircle")}`;
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-m]"); if (!b) return;
    moderateCourse(d.find(x => x.id === Number(b.dataset.id)), b.dataset.m, () => location.reload());
  });
}, { title: "مراجعة الكورسات", roles: ["admin", "supervisor"] });
