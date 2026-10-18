import { $, $$, api, avatar, badge, busy, confirmBox, empty, esc, fail, fmt, formData, go, html, list, loading, modal, onEvent,
  ico, raw, ROLE_AR, route, showErrors, state, toast, WEEKDAYS, wsSend } from "./core.js";

const me = () => state.user;
const isStaff = () => ["admin", "supervisor"].includes(me().role);

// ============================================================ Dashboard
route("/home", async page => {
  const d = await api("dashboard/");
  const r = me().role;
  if (r === "student") page.innerHTML = studentHome(d);
  else if (r === "teacher") page.innerHTML = teacherHome(d);
  else if (r === "supervisor") page.innerHTML = supervisorHome(d);
  else page.innerHTML = adminHome(d);
  bindSessionActions(page, () => go("/home"));
}, { title: "الرئيسية" });

const STAT_IC = { "حصة حضرتها": "checkCircle", "واجب/امتحان مستنيك": "clipboard", "متوسط درجاتك": "chart", "مرات غياب": "x",
  "طالب نشط": "users", "حصة الشهر ده": "calendar", "تقارير لسه متكتبتش": "pen", "تسليمات محتاجة تصحيح": "grading",
  "حصة النهارده": "calendar", "اشتراك محتاج مدرس": "swap", "حصة محتاجة تقييم": "star", "مخالفة تواصل": "flag",
  "إيراد الشهر ده": "money", "اشتراك نشط": "wallet", "حصة شغالة دلوقتي": "video", "طلب حصة تجريبية": "gift",
  "كورسات ومخالفات للمراجعة": "checkCircle", "مدرس مستني الاعتماد": "shield" };
const stat = (v, k, alert = false, href = "") => html`<${href ? "a" : "div"} class="stat ${alert ? "alert" : ""}" ${href ? raw(`href="#${href}" style="text-decoration:none;color:inherit"`) : ""}>
  <span class="si">${ico(STAT_IC[k] || "chart", 21)}</span><div><div class="v">${v}</div><div class="k">${k}</div></div></${href ? "a" : "div"}>`;

// بانر الحصة الجاية: عداد + زرار دخول الغرفة
export function nextHero(x) {
  if (!x) return "";
  const u = me(); const isT = u.id === x.teacher.id; const other = isT ? x.student : x.teacher;
  const mins = Math.round((Date.parse(x.scheduled_at) - Date.now()) / 60000);
  const when = x.status === "live" ? html`<b>شغالة دلوقتي</b>` : mins <= 0 ? html`<b>ميعادها جه</b>`
    : mins < 60 ? html`كمان <b>${fmt.num(mins)} دقيقة</b>` : mins < 1440 ? html`كمان <b>${fmt.num(Math.floor(mins / 60))} ساعة و${fmt.num(mins % 60)} دقيقة</b>` : html`<b>${fmt.date(x.scheduled_at)}</b> الساعة ${fmt.time(x.scheduled_at)}`;
  return html`<section class="hero-next"><span class="hn-ic">${ico("video", 28)}</span>
    <div><div class="count">${x.status === "live" ? "الحصة" : "حصتك الجاية"} · ${when}</div><h2>${x.subject.name} ${isT ? "للطالب" : "مع"} ${other.full_name}</h2>
      <div class="count">${fmt.time(x.scheduled_at)} · ${fmt.num(x.duration)} دقيقة</div></div>
    <a class="btn ${x.can_join ? "now" : "ghost"} lg" href="#/room/${x.id}" ${x.can_join ? "" : raw('style="background:transparent;color:#fff;border-color:rgba(255,255,255,.35)"')}>${ico(x.can_join ? "video" : "clock")} ${x.can_join ? "ادخل الحصة" : "صالة الانتظار"}</a></section>`;
}

function hello(sub) {
  const h = new Date().getHours();
  return html`<div class="page-head"><div><h1>${h < 12 ? "صباح الخير" : "مساء الخير"}، ${me().full_name.split(" ").slice(0, 2).join(" ")}</h1>
    <p>${sub}</p></div></div>`;
}

function studentSummary(d, compact = false) {
  const s = d.stats;
  return html`
    <div class="grid g4" style="margin-bottom:18px">
      ${stat(fmt.num(s.completed_sessions), "حصة حضرتها")}
      ${stat(fmt.num(s.pending_quizzes), "واجب/امتحان مستنيك", s.pending_quizzes > 0, compact ? "" : "/quizzes")}
      ${stat(s.avg_quiz_percent != null ? `${fmt.num(s.avg_quiz_percent)}٪` : "—", "متوسط درجاتك")}
      ${stat(fmt.num(s.absences), "مرات غياب", s.absences > 2)}
    </div>
    <div class="cols">
      <section class="panel"><div class="panel-head"><h2>الحصص الجاية</h2>${compact ? "" : html`<a href="#/sessions">كل الحصص</a>`}</div>
        ${d.upcoming_sessions.length ? html`<div class="sched">${d.upcoming_sessions.map(x => sessionSlot(x))}</div>` : empty("مفيش حصص جاية", "اشترك في باقة أو اطلب حصة تجريبية")}
      </section>
      <section class="stack">
        <div class="panel"><div class="panel-head"><h2>الاشتراكات</h2></div>
          ${d.subscriptions.length ? d.subscriptions.map(sb => html`<a class="row between" href="#/subscriptions/${sb.id}" style="padding:8px 0;border-bottom:1px solid var(--line-2);color:inherit;text-decoration:none">
            <div><b>${sb.subject.name}</b><div class="small muted">${sb.teacher ? sb.teacher.full_name : "لسه بيتحدد المدرس"}</div></div>
            <div style="text-align:end">${badge(sb.status)}<div class="small muted">${sb.sessions_remaining} حصة باقية</div></div></a>`) : empty("مفيش اشتراكات")}
        </div>
        <div class="panel"><div class="panel-head"><h2>آخر التقارير</h2></div>
          ${d.latest_reports.length ? d.latest_reports.map(rp => html`<a href="#/sessions/${rp.session_id}" style="display:block;padding:8px 0;border-bottom:1px solid var(--line-2);color:inherit;text-decoration:none">
            <div class="row between"><b>${rp.subject}</b><span class="stars">${"★".repeat(rp.performance)}</span></div>
            <div class="small">${rp.topics}</div>${rp.homework ? html`<div class="small muted">الواجب: ${rp.homework}</div>` : ""}</a>`) : empty("لسه مفيش تقارير")}
        </div>
      </section>
    </div>`;
}

function studentHome(d) {
  return html`${hello("ده ملخص يومك. الحصة اللي ميعادها قرب هتلاقي زرار الدخول جنبها.")}
    ${nextHero(d.upcoming_sessions[0])}
    ${studentSummary(d)}
    ${d.continue_courses?.length ? html`<section class="panel" style="margin-top:18px"><div class="panel-head"><h2>كمّل الكورسات</h2><a href="#/courses">كل الكورسات</a></div>
      <div class="grid g3">${d.continue_courses.map(c => html`<a class="card link" href="#/courses/${c.slug}" style="color:inherit;text-decoration:none">
        <b>${c.title}</b><div class="progress"><i style="width:${c.progress_percent}%"></i></div><div class="small muted">${fmt.num(c.progress_percent)}٪ مكتمل</div></a>`)}</div></section>` : ""}`;
}

function teacherHome(d) {
  if (d.approval_status !== "approved") {
    return html`<div class="panel" style="max-width:620px">
      <h1>طلبك قيد المراجعة</h1>
      <p class="muted">الإدارة بتراجع بياناتك ومستنداتك. أول ما يتم الاعتماد هيوصلك إشعار وتقدر تستقبل طلاب.</p>
      <p>الحالة: ${badge(d.approval_status)}</p>
      <a class="btn ghost" href="#/profile">كمّل بياناتك وارفع مستنداتك</a></div>`;
  }
  const s = d.stats;
  return html`${hello(`عندك ${fmt.num(s.today_sessions)} حصة النهارده.`)}
    ${nextHero(d.upcoming_sessions[0])}
    <div class="grid g4" style="margin-bottom:18px">
      ${stat(fmt.num(s.active_students), "طالب نشط", false, "/students")}
      ${stat(fmt.num(s.month_completed_sessions), "حصة الشهر ده")}
      ${stat(fmt.num(s.reports_missing), "تقارير لسه متكتبتش", s.reports_missing > 0, "/sessions?tab=past")}
      ${stat(fmt.num(s.to_grade), "تسليمات محتاجة تصحيح", s.to_grade > 0, "/grading")}
    </div>
    <div class="cols"><section class="panel"><div class="panel-head"><h2>جدولك الجاي</h2><a href="#/sessions">الجدول كامل</a></div>
      ${d.upcoming_sessions.length ? html`<div class="sched">${d.upcoming_sessions.map(x => sessionSlot(x))}</div>` : empty("مفيش حصص جاية")}</section>
      <section class="stack">
        <div class="panel"><h2>تقييمك</h2><p style="font-size:32px;font-weight:700;margin:6px 0" class="stars">★ ${Number(s.rating_avg).toFixed(1)}</p><p class="muted small">${fmt.num(s.rating_count)} تقييم من الطلاب</p></div>
        <div class="panel"><h2>دقايق التدريس الشهر ده</h2><p style="font-size:32px;font-weight:700;margin:6px 0">${fmt.num(s.month_minutes)}</p><p class="muted small">≈ ${fmt.num(Math.round(s.month_minutes / 6) / 10)} ساعة</p></div>
      </section></div>`;
}

function supervisorHome(d) {
  const s = d.stats;
  return html`${hello(`بتتابع ${fmt.num(d.teachers_count)} مدرس.`)}
    <div class="grid g4" style="margin-bottom:18px">
      ${stat(fmt.num(s.today_sessions), "حصة النهارده", false, "/sessions")}
      ${stat(fmt.num(s.pending_assignment), "اشتراك محتاج مدرس", s.pending_assignment > 0, "/assign")}
      ${stat(fmt.num(s.to_evaluate), "حصة محتاجة تقييم", s.to_evaluate > 0, "/sessions?tab=past")}
      ${stat(fmt.num(s.unreviewed_violations), "مخالفة تواصل", s.unreviewed_violations > 0, "/violations")}
    </div>
    <section class="panel"><div class="panel-head"><h2>شغالة دلوقتي</h2></div>
      ${d.live_now.length ? html`<div class="sched">${d.live_now.map(x => sessionSlot(x))}</div>` : empty("مفيش حصص شغالة دلوقتي")}</section>`;
}

function adminHome(d) {
  const s = d.stats;
  const max = Math.max(1, ...d.revenue_by_month.map(r => Number(r.total)));
  return html`${hello("نظرة سريعة على المنصة.")}
    <div class="grid g4" style="margin-bottom:16px">
      ${stat(fmt.money(s.month_revenue), "إيراد الشهر ده")}
      ${stat(fmt.num(s.active_subscriptions), "اشتراك نشط", false, "/subscriptions?status=active")}
      ${stat(fmt.num(s.today_sessions), "حصة النهارده", false, "/sessions")}
      ${stat(fmt.num(s.live_now), "حصة شغالة دلوقتي", s.live_now > 0, "/sessions?tab=upcoming")}
    </div>
    <div class="grid g4" style="margin-bottom:18px">
      ${stat(fmt.num(s.pending_teachers), "مدرس مستني الاعتماد", s.pending_teachers > 0, "/approvals")}
      ${stat(fmt.num(s.pending_assignment), "اشتراك محتاج مدرس", s.pending_assignment > 0, "/assign")}
      ${stat(fmt.num(s.pending_trials), "طلب حصة تجريبية", s.pending_trials > 0, "/trials")}
      ${stat(fmt.num(s.courses_pending_review + s.unreviewed_violations), "كورسات ومخالفات للمراجعة", (s.courses_pending_review + s.unreviewed_violations) > 0, "/course-review")}
    </div>
    <div class="cols">
      <section class="panel"><div class="panel-head"><h2>الإيرادات آخر 12 شهر</h2><span class="muted small">الإجمالي ${fmt.money(s.total_revenue)}</span></div>
        <div class="bar" role="img" aria-label="إيرادات شهرية">${d.revenue_by_month.map(r => html`<div class="col" title="${r.month}: ${fmt.money(r.total)}">
          <i style="height:${Math.round(Number(r.total) / max * 100)}%"></i><span>${r.month.slice(5)}/${r.month.slice(2, 4)}</span></div>`)}</div></section>
      <section class="panel"><div class="panel-head"><h2>المستخدمين</h2><a href="#/users">إدارة</a></div>
        ${Object.entries(d.users).map(([k, v]) => html`<div class="row between" style="padding:6px 0;border-bottom:1px solid var(--line-2)"><span>${ROLE_AR[k] || k}</span><b>${fmt.num(v)}</b></div>`)}</section>
    </div>`;
}

// ============================================================ Sessions
export function sessionSlot(x) {
  const u = me();
  const other = u.id === x.teacher.id ? x.student : x.teacher;
  const isTeacher = u.id === x.teacher.id;
  const now = x.status === "live" || x.can_join;
  const acts = [];
  if (x.can_join) acts.push(html`<button class="btn now sm" data-act="join" data-id="${x.id}">${ico("video", 15)} ${x.status === "live" ? "ادخل الحصة الآن" : "ادخل الحصة"}</button>`);
  else if (x.status === "scheduled" && !isStaff()) acts.push(html`<a class="btn ghost sm" href="#/room/${x.id}">${ico("clock", 15)} صالة الانتظار</a>`);
  if (isTeacher && x.status === "live") acts.push(html`<button class="btn sm" data-act="end" data-id="${x.id}">إنهاء الحصة</button>`);
  if (isTeacher && x.status === "completed" && !x.has_report) acts.push(html`<a class="btn ghost sm" href="#/sessions/${x.id}?report=1">اكتب التقرير</a>`);
  const people = isStaff() ? html`${x.teacher.full_name} ← ${x.student.full_name}` : html`${isTeacher ? "الطالب" : "مع"} ${other.full_name}`;
  return html`<div class="slot ${now ? "is-now" : ""}">
    <div class="when"><div class="d">${fmt.short(x.scheduled_at)}</div><div class="h">${fmt.time(x.scheduled_at)}</div></div>
    <a href="#/sessions/${x.id}" style="color:inherit;text-decoration:none;min-width:0"><div class="row wrap"><b>${x.subject.name}</b>${badge(x.status)}${x.is_trial ? html`<span class="badge b-blue">تجريبية</span>` : ""}</div>
      <div class="small muted">${people} · ${fmt.num(x.duration)} دقيقة${x.title ? ` · ${x.title}` : ""}</div></a>
    <div class="actions">${acts}</div></div>`;
}

export function bindSessionActions(root, reload) {
  root.addEventListener("click", async e => {
    const b = e.target.closest("[data-act]"); if (!b) return;
    const id = b.dataset.id;
    const act = b.dataset.act;
    if (act === "join") return busy(b, () => joinSession(id));
    if (act === "end") return busy(b, async () => {
      if (!(await confirmBox("تنهي الحصة دلوقتي؟ بعدها هتكتب التقرير.", "إنهاء الحصة"))) return;
      await api(`sessions/${id}/end/`, { method: "POST" }); toast("الحصة خلصت", "good"); go(`/sessions/${id}?report=1`);
    });
    if (act === "cancel") return cancelDialog(id, reload);
    if (act === "absent-student" || act === "absent-teacher") return busy(b, async () => {
      const who = act === "absent-student" ? "student" : "teacher";
      if (!(await confirmBox(who === "student" ? "تسجل غياب الطالب؟ الحصة هتتخصم من رصيده." : "تسجل غياب المدرس؟ الحصة هتتعوض.", "تسجيل الغياب"))) return;
      await api(`sessions/${id}/mark-absent/`, { method: "POST", body: { who } }); toast("تم تسجيل الغياب", "good"); reload();
    });
    if (act === "reschedule") return rescheduleDialog(id, reload);
  });
}

function joinSession(id) { go(`/room/${id}`); }

const roomNotes = id => { try { return localStorage.getItem(`ep_room_notes_${id}`) || ""; } catch { return ""; } };

function cancelDialog(id, reload) {
  modal("إلغاء الحصة", html`<form class="stack"><p class="muted">لو إنت الطالب ولغيت قبل الحصة بأقل من ساعتين، الحصة هتتخصم من رصيدك.</p>
    <div class="field"><label>السبب</label><textarea class="input" name="reason" required></textarea></div>
    <button class="btn danger">إلغاء الحصة</button></form>`, {
    onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault();
      await busy(e.submitter, async () => {
        const r = await api(`sessions/${id}/cancel/`, { method: "POST", body: formData(e.target) });
        close(); toast(r.counted ? "اتلغت واتخصمت من الرصيد" : "اتلغت الحصة", "good"); reload();
      });
    }),
  });
}

function rescheduleDialog(id, reload) {
  modal("طلب تغيير الميعاد", html`<form class="stack">
    <div class="field"><label>الميعاد الجديد</label><input class="input" type="datetime-local" name="proposed_time" required></div>
    <div class="field"><label>السبب</label><input class="input" name="reason"></div>
    <button class="btn">ابعت الطلب</button></form>`, {
    onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault();
      const f = formData(e.target);
      try {
        await api(`sessions/${id}/reschedule/`, { method: "POST", body: { ...f, proposed_time: new Date(f.proposed_time).toISOString() } });
        close(); toast(isStaff() ? "اتغير الميعاد" : "الطلب اتبعت للإدارة", "good"); reload();
      } catch (err) { showErrors(e.target, err); }
    }),
  });
}

route("/sessions", async (page, _p, q) => {
  const tab = q.tab || "upcoming";
  const query = { page_size: 50 };
  if (tab === "upcoming") query.upcoming = "true";
  if (tab === "past") { query.ordering = "-scheduled_at"; query.to = new Date().toISOString().slice(0, 10); }
  if (q.status) query.status = q.status;
  const d = await api("sessions/", { query });
  let rows = list(d);
  if (tab === "past") rows = rows.filter(x => !["scheduled", "live"].includes(x.status));
  const T = (k, l) => html`<button class="${tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`;
  page.innerHTML = html`<div class="page-head"><div><h1>${me().role === "teacher" ? "جدولي" : "الحصص"}</h1><p>${fmt.num(d.count)} حصة</p></div></div>
    <div class="tabs">${T("upcoming", "الجاية")}${T("past", "اللي فاتت")}${T("all", "الكل")}</div>
    ${rows.length ? html`<div class="sched">${rows.map(x => sessionSlot(x))}</div>` : empty("مفيش حصص هنا")}`;
  page.querySelector(".tabs").onclick = e => { const t = e.target.dataset.tab; if (t) go(`/sessions?tab=${t}`); };
  bindSessionActions(page, () => location.reload());
  return onEvent(ev => { if (ev === "session.updated") location.reload(); });
}, { title: "الحصص" });

route("/sessions/:id", async (page, { id }, q) => {
  const load = async () => {
    const s = await api(`sessions/${id}/`);
    const u = me();
    const isTeacher = u.id === s.teacher.id, isStudent = u.id === s.student.id;
    const open = ["scheduled", "live"].includes(s.status);
    const acts = [];
    if (s.can_join) acts.push(html`<button class="btn now" data-act="join" data-id="${s.id}">${ico("video", 16)} ${s.status === "live" ? "ادخل الحصة الآن" : "ادخل غرفة الحصة"}</button>`);
    else if (s.status === "scheduled" && (isTeacher || isStudent)) acts.push(html`<a class="btn ghost" href="#/room/${s.id}">${ico("clock", 16)} صالة الانتظار</a>`);
    if (isStudent && s.status === "completed") acts.push(html`<a class="btn ${s.feedback ? "ghost" : ""}" href="#/room/${s.id}">${ico("star", 16)} ${s.feedback ? "تقييمك للحصة" : "قيّم الحصة"}</a>`);
    if ((isTeacher || isStaff()) && s.status === "live") acts.push(html`<button class="btn" data-act="end" data-id="${s.id}">إنهاء الحصة</button>`);
    if (s.status === "scheduled" && (isTeacher || isStudent || isStaff())) {
      acts.push(html`<button class="btn ghost" data-act="reschedule" data-id="${s.id}">${isStaff() ? "تغيير الميعاد" : "طلب تغيير الميعاد"}</button>`);
      acts.push(html`<button class="btn danger" data-act="cancel" data-id="${s.id}">إلغاء</button>`);
    }
    if (open && (isTeacher || isStaff())) acts.push(html`<button class="btn ghost" data-act="absent-student" data-id="${s.id}">غياب الطالب</button>`);
    if (open && (isStudent || isStaff())) acts.push(html`<button class="btn ghost" data-act="absent-teacher" data-id="${s.id}">المدرس مجاش</button>`);
    const rep = s.report;
    const canWrite = (isTeacher || isStaff()) && ["completed", "student_absent", "live"].includes(s.status);
    page.innerHTML = html`<div class="page-head"><div><h1>${s.subject.name}${s.title ? ` — ${s.title}` : ""}</h1>
      <p>${fmt.date(s.scheduled_at)} · ${fmt.time(s.scheduled_at)} إلى ${fmt.time(s.ends_at)}</p></div><div class="row wrap">${acts}</div></div>
      <div class="cols">
        <div class="stack">
          <section class="panel"><div class="panel-head"><h2>تقرير الحصة</h2>${rep && canWrite ? html`<button class="btn ghost sm" id="edit-rep">تعديل</button>` : ""}</div>
            <div id="rep-box">${rep ? reportView(rep) : (canWrite ? "" : empty("التقرير لسه متكتبش"))}</div></section>
          ${isStaff() ? html`<section class="panel"><div class="panel-head"><h2>تقييم المشرف</h2></div>
            ${s.evaluation ? html`<p><b style="font-size:22px">${s.evaluation.score}/10</b> — ${s.evaluation.notes}</p><p class="small muted">${s.evaluation.supervisor?.full_name || ""}</p>` : ""}
            <form id="eval" class="row wrap" style="align-items:flex-end">
              <div class="field" style="width:110px"><label>الدرجة من 10</label><input class="input" name="score" type="number" min="1" max="10" value="${s.evaluation?.score || 8}"></div>
              <div class="field" style="flex:1;min-width:200px"><label>ملاحظات</label><input class="input" name="notes" value="${s.evaluation?.notes || ""}"></div>
              <button class="btn">حفظ التقييم</button></form></section>` : ""}
        </div>
        <aside class="stack">
          <div class="panel"><div class="stack">
            <div class="row between"><span class="muted">الحالة</span>${badge(s.status)}</div>
            <div class="row between"><span class="muted">المدرس</span><b>${s.teacher.full_name}</b></div>
            <div class="row between"><span class="muted">الطالب</span><b>${s.student.full_name}</b></div>
            <div class="row between"><span class="muted">المدة</span><span>${fmt.num(s.duration)} دقيقة</span></div>
            <div class="row between"><span class="muted">اتخصمت من الرصيد</span><span>${s.counted ? "أيوه" : "لأ"}</span></div>
            ${s.teacher_joined_at ? html`<div class="row between"><span class="muted">دخول المدرس</span><span>${fmt.time(s.teacher_joined_at)}</span></div>` : ""}
            ${s.student_joined_at ? html`<div class="row between"><span class="muted">دخول الطالب</span><span>${fmt.time(s.student_joined_at)}</span></div>` : ""}
            ${s.cancel_reason ? html`<div class="row between"><span class="muted">سبب الإلغاء</span><span>${s.cancel_reason}</span></div>` : ""}
          </div></div>
          ${s.feedback && !isStudent ? html`<div class="panel"><h3 style="margin-bottom:6px">تقييم الطالب للحصة</h3>
            <div class="stars" style="font-size:18px">${"★".repeat(s.feedback.rating)}<span style="color:var(--line)">${"★".repeat(5 - s.feedback.rating)}</span></div>
            ${s.feedback.issues?.length ? html`<div class="row wrap" style="margin-top:6px">${s.feedback.issues.map(i => html`<span class="badge b-red">${ISSUE_AR[i] || i}</span>`)}</div>` : ""}
            ${s.feedback.comment && isStaff() ? html`<p class="small" style="margin:8px 0 0">${s.feedback.comment}</p>` : ""}</div>` : ""}
          ${s.previous_homework ? html`<div class="panel"><h3 style="margin-bottom:6px">واجب الحصة اللي فاتت</h3><p style="margin:0">${s.previous_homework.homework}</p></div>` : ""}
          ${s.subscription ? html`<a class="btn ghost block" href="#/subscriptions/${s.subscription}">تفاصيل الاشتراك</a>` : ""}
          <button class="btn ghost block" id="chat-other">راسل ${isTeacher ? "الطالب" : "المدرس"}</button>
        </aside></div>`;
    const writeForm = r => html`<form id="rep-form" class="stack">
      <div class="form-grid">
        <div class="field"><label>الحضور</label><select class="input" name="attendance">
          ${[["present", "حاضر"], ["late", "متأخر"], ["absent", "غائب"]].map(([v, l]) => html`<option value="${v}" ${r?.attendance === v ? "selected" : ""}>${l}</option>`)}</select></div>
        <div class="field"><label>المستوى (1-5)</label><input class="input" type="number" min="1" max="5" name="performance" value="${r?.performance || 4}"></div>
        <div class="field"><label>السلوك (1-5)</label><input class="input" type="number" min="1" max="5" name="behavior" value="${r?.behavior || 4}"></div>
      </div>
      <div class="field"><label>اتشرح إيه في الحصة</label><textarea class="input" name="topics" required>${r?.topics || roomNotes(id)}</textarea>
        ${!r && roomNotes(id) ? html`<span class="hint">${ico("note", 13)} اتملت من ملاحظاتك اللي كتبتها جوه الحصة — عدّلها براحتك.</span>` : ""}</div>
      <div class="field"><label>الواجب</label><input class="input" name="homework" value="${r?.homework || ""}"></div>
      <div class="field"><label>نصيحة للطالب</label><input class="input" name="notes_for_student" value="${r?.notes_for_student || ""}"></div>
      <div class="field"><label>ملاحظة خاصة للمشرف (مش بتظهر للطالب)</label><input class="input" name="private_notes" value="${r?.private_notes || ""}"></div>
      <button class="btn">حفظ التقرير وإرساله</button></form>`;
    const showForm = () => {
      $("#rep-box").innerHTML = writeForm(rep);
      $("#rep-form").addEventListener("submit", async e => {
        e.preventDefault();
        try {
          await api(`sessions/${id}/report/`, { method: rep ? "PUT" : "POST", body: formData(e.target) });
          try { localStorage.removeItem(`ep_room_notes_${id}`); } catch {}
          toast("التقرير اتبعت للطالب", "good"); if (q.report) go(`/sessions/${id}`); else load();
        }
        catch (err) { showErrors(e.target, err); }
      });
    };
    if (canWrite && (!rep || q.report)) showForm();
    $("#edit-rep")?.addEventListener("click", showForm);
    $("#eval")?.addEventListener("submit", async e => {
      e.preventDefault();
      try { await api(`sessions/${id}/evaluate/`, { method: "POST", body: formData(e.target) }); toast("اتحفظ التقييم", "good"); load(); }
      catch (err) { showErrors(e.target, err); }
    });
    $("#chat-other").onclick = () => busy($("#chat-other"), async () => {
      const other = isTeacher ? s.student : s.teacher;
      const c = await api("chat/conversations/start/", { method: "POST", body: { user_id: other.id } });
      go(`/chat?c=${c.id}`);
    });
  };
  bindSessionActions(page, load);
  await load();
  return onEvent((ev, d) => { if (ev === "session.updated" && String(d.session_id) === String(id)) load(); });
}, { title: "تفاصيل الحصة" });

const ISSUE_AR = { audio: "الصوت", video: "الصورة", connection: "النت/الاتصال", late: "المدرس اتأخر", unclear: "الشرح مش واضح", short: "الحصة اتقصرت" };
const reportView = r => html`<div class="stack">
  <div class="row wrap">${badge(r.attendance === "present" ? "completed" : "student_absent")}
    <span>المستوى <span class="stars">${"★".repeat(r.performance)}</span></span><span class="muted">·</span><span>السلوك <span class="stars">${"★".repeat(r.behavior)}</span></span></div>
  <div><div class="small muted">اتشرح</div>${r.topics}</div>
  ${r.homework ? html`<div><div class="small muted">الواجب</div>${r.homework}</div>` : ""}
  ${r.notes_for_student ? html`<div><div class="small muted">نصيحة للطالب</div>${r.notes_for_student}</div>` : ""}
  ${r.private_notes ? html`<div><div class="small muted">ملاحظة خاصة</div>${r.private_notes}</div>` : ""}</div>`;

// ============================================================ Chat
route("/chat", (page, _p, q) => chatView(page, q, false), { title: "الشات" });
route("/oversight", (page, _p, q) => chatView(page, q, true), { title: "مراقبة الشات", roles: ["admin", "supervisor"] });

async function chatView(page, q, oversight) {
  let convs = list(await api("chat/conversations/", { query: oversight ? { all: "true", page_size: 100 } : { page_size: 100 } }));
  let current = q.c ? Number(q.c) : null;
  let typingTimer;
  page.innerHTML = html`<div class="page-head" style="margin-bottom:12px"><div><h1>${oversight ? "مراقبة الشات" : "الشات"}</h1>
    <p>${oversight ? "كل المحادثات بين المدرسين والطلاب. الرسائل المخالفة معلّمة باللون الأصفر وفيها النص الأصلي." : "كلامك مع مدرسينك/طلابك والإدارة. أرقام التليفون واللينكات بتتخفى تلقائياً."}</p></div>
    ${oversight ? "" : html`<div class="row"><button class="btn ghost" id="support">كلم الدعم</button><button class="btn" id="new">محادثة جديدة</button></div>`}</div>
    <div class="chat" id="chat"><div class="conv-list" id="convs"></div>
    <div class="thread" id="thread">${empty("اختار محادثة")}</div></div>`;
  const nameOf = c => c.other_members.map(m => m.full_name).join("، ") || (c.type === "support" ? "الدعم الفني" : "محادثة");
  const drawList = () => {
    $("#convs").innerHTML = convs.length ? convs.map(c => html`<div class="conv ${c.id === current ? "on" : ""}" data-id="${c.id}">
      ${avatar(c.other_members[0])}<div class="meta"><div class="row between"><b class="small">${nameOf(c)}</b>
      <span class="small muted">${c.last_message ? fmt.ago(c.last_message.created_at) : ""}</span></div>
      <div class="row between"><div class="last">${c.last_message ? (c.last_message.is_flagged ? "⚠ " : "") + (c.last_message.text || "📎 مرفق") : "—"}</div>
      ${c.unread_count ? html`<span class="unread">${c.unread_count}</span>` : ""}</div></div></div>`).join("") : empty("مفيش محادثات").s;
  };
  const msgHTML = m => {
    const mine = m.sender?.id === me().id;
    const att = m.attachment ? (m.type === "image" ? html`<a href="${m.attachment}" target="_blank"><img src="${m.attachment}" alt=""></a>` :
      m.type === "voice" ? html`<audio controls src="${m.attachment}"></audio>` : html`<a href="${m.attachment}" target="_blank">📎 ملف مرفق</a>`) : "";
    return html`<div class="msg ${mine ? "me" : ""} ${m.is_flagged ? "flag" : ""}" data-mid="${m.id}">
      ${!mine && oversight ? html`<div class="small" style="font-weight:600">${m.sender?.full_name}</div>` : ""}
      ${m.text ? html`<div class="txt">${m.text}</div>` : ""}${att}
      ${m.is_flagged ? html`<div class="orig">${m.original_text ? `النص الأصلي: ${m.original_text}` : "تم إخفاء محتوى مخالف لسياسة المنصة"}</div>` : ""}
      <div class="t">${fmt.time(m.created_at)}</div></div>`;
  };
  const openConv = async id => {
    current = id; drawList();
    $("#chat").classList.add("has-thread");
    history.replaceState(null, "", `#/chat${oversight ? "" : ""}?c=${id}`.replace("/chat", oversight ? "/oversight" : "/chat"));
    const c = convs.find(x => x.id === id) || await api(`chat/conversations/${id}/`);
    $("#thread").innerHTML = html`<div class="thread-head"><button class="btn ghost sm menu-back" id="back" aria-label="رجوع">→</button>${avatar(c.other_members[0])}<div><b>${nameOf(c)}</b>
      <div class="small muted">${c.other_members.map(m => ROLE_AR[m.role]).join("، ")}</div></div>
      ${oversight ? html`<button class="btn ghost sm" id="lock" style="margin-inline-start:auto">${c.is_locked ? "فتح المحادثة" : "قفل المحادثة"}</button>` : ""}</div>
      <div class="msgs" id="msgs">${loading()}</div><div class="typing" id="typing"></div>
      <form class="composer" id="composer"><label class="btn ghost" title="إرفاق صورة أو ملف">📎<input type="file" id="file" hidden></label>
        <input class="input" name="text" placeholder="${c.is_locked ? "المحادثة مقفولة" : "اكتب رسالة…"}" autocomplete="off" ${c.is_locked ? "disabled" : ""}>
        <button class="btn" ${c.is_locked ? "disabled" : ""}>إرسال</button></form>`;
    $("#back").onclick = () => { $("#chat").classList.remove("has-thread"); };
    const d = await api(`chat/conversations/${id}/messages/`, { query: { page_size: 60 } });
    $("#msgs").innerHTML = d.results.slice().reverse().map(msgHTML).join("") || empty("ابدأ المحادثة").s;
    $("#msgs").scrollTop = 1e9;
    if (!oversight) { api(`chat/conversations/${id}/read/`, { method: "POST" }).catch(() => {}); c.unread_count = 0; drawList(); window.EP.refreshUnread(); }
    $("#lock")?.addEventListener("click", async () => { await api(`chat/conversations/${id}/lock/`, { method: "POST" }); toast("اتغيرت حالة المحادثة"); convs = list(await api("chat/conversations/", { query: { all: "true", page_size: 100 } })); openConv(id); });
    const f = $("#composer");
    f.text.addEventListener("input", () => { wsSend({ action: "typing", conversation_id: id, is_typing: true }); });
    f.addEventListener("submit", async e => {
      e.preventDefault();
      const text = f.text.value.trim(); if (!text) return;
      f.text.value = "";
      try { const m = await api(`chat/conversations/${id}/messages/`, { method: "POST", body: { type: "text", text } }); appendMsg(m); if (m.is_flagged) toast("الرسالة فيها بيانات تواصل واتخفت", "bad"); }
      catch (err) { fail(err); f.text.value = text; }
    });
    $("#file").addEventListener("change", async e => {
      const file = e.target.files[0]; if (!file) return;
      const fd = new FormData(); fd.append("attachment", file); fd.append("type", file.type.startsWith("image/") ? "image" : "file");
      try { appendMsg(await api(`chat/conversations/${id}/messages/`, { method: "POST", form: fd })); } catch (err) { fail(err); }
      e.target.value = "";
    });
  };
  const appendMsg = m => {
    if (m.conversation !== current || $(`[data-mid="${m.id}"]`)) return;
    const box = $("#msgs"); if (!box) return;
    box.querySelector(".empty")?.remove();
    box.insertAdjacentHTML("beforeend", msgHTML(m).s);
    box.scrollTop = 1e9;
  };
  drawList();
  $("#convs").onclick = e => { const el = e.target.closest(".conv"); if (el) openConv(Number(el.dataset.id)); };
  $("#new")?.addEventListener("click", newConversation);
  $("#support")?.addEventListener("click", async () => { const c = await api("chat/conversations/support/", { method: "POST" }); if (!convs.find(x => x.id === c.id)) convs.unshift(c); openConv(c.id); });
  if (current) openConv(current);
  return onEvent(async (ev, d) => {
    if (ev === "message.new") {
      const c = convs.find(x => x.id === d.conversation_id);
      if (c) { c.last_message = d.message; if (d.conversation_id !== current && d.message.sender?.id !== me().id) c.unread_count++; convs = [c, ...convs.filter(x => x !== c)]; }
      else if (!oversight) convs = list(await api("chat/conversations/", { query: { page_size: 100 } }));
      drawList();
      if (d.conversation_id === current) { appendMsg(d.message); if (!oversight) api(`chat/conversations/${current}/read/`, { method: "POST" }).catch(() => {}); }
    }
    if (ev === "typing" && d.conversation_id === current) {
      $("#typing").textContent = "بيكتب…"; clearTimeout(typingTimer); typingTimer = setTimeout(() => { const t = $("#typing"); if (t) t.textContent = ""; }, 3000);
    }
  });
}

async function newConversation() {
  const d = await api("chat/conversations/contacts/", { query: { page_size: 100 } });
  const people = list(d);
  modal("محادثة جديدة", people.length ? html`<input class="input" id="q" placeholder="دوّر بالاسم" style="margin-bottom:10px">
    <div class="stack" id="people">${people.map(p => html`<button class="btn ghost" style="justify-content:flex-start" data-id="${p.id}" data-n="${p.full_name}">${avatar(p)} ${p.full_name}
      <span class="badge" style="margin-inline-start:auto">${ROLE_AR[p.role]}</span></button>`)}</div>` : empty("مفيش حد متاح تكلمه دلوقتي", "لما يكون عندك اشتراك نشط هتقدر تكلم مدرسك"), {
    onMount: (b, close) => {
      b.querySelector("#q")?.addEventListener("input", e => $$("#people button", b).forEach(x => x.classList.toggle("hidden", !x.dataset.n.includes(e.target.value))));
      b.addEventListener("click", async e => {
        const btn = e.target.closest("[data-id]"); if (!btn) return;
        const c = await api("chat/conversations/start/", { method: "POST", body: { user_id: Number(btn.dataset.id) } });
        close(); location.hash = `#/chat?c=${c.id}`; location.reload();
      });
    },
  });
}

// ============================================================ Notifications
export function notifTarget(n) {
  const d = n.data || {};
  if (["session_started", "session_reminder"].includes(n.type) && d.id) return `/room/${d.id}`;
  if (n.type === "session_completed" && d.id && me().role === "student") return `/room/${d.id}`;
  switch (d.screen) {
    case "certificate": return "/certificates";
    case "session": return `/sessions/${d.id}`;
    case "subscription": return `/subscriptions/${d.id}`;
    case "chat": return `/chat?c=${d.conversation_id}`;
    case "quiz": return "/quizzes";
    case "attempt": return `/attempts/${d.id}`;
    case "course": return `/courses/${d.slug}`;
    case "order": return isStaff() ? "/orders" : "/subscriptions";
    case "trial": return "/trials";
    case "reschedule": return "/reschedules";
    case "violation": return "/violations";
    case "course_review": return "/course-review";
    case "question": return `/qa/${d.slug}`;
    case "qa_moderation": return "/qa-moderation";
    case "blog_manage": return d.id ? `/articles/${d.id}` : "/articles";
    default: return n.type === "teacher_application" ? "/approvals" : null;
  }
}

route("/notifications", async page => {
  const load = async () => {
    const d = await api("notifications/", { query: { page_size: 60 } });
    const rows = list(d);
    page.innerHTML = html`<div class="page-head"><div><h1>الإشعارات</h1><p>${fmt.num(d.count)} إشعار</p></div>
      <button class="btn ghost" id="all">تعليم الكل كمقروء</button></div>
      <div class="panel" style="padding:0">${rows.length ? rows.map(n => html`<div class="notif ${n.is_read ? "" : "unread"}" data-id="${n.id}" data-to="${notifTarget(n) || ""}">
        <div style="flex:1"><div class="row between"><b>${n.title}</b><span class="small muted">${fmt.ago(n.created_at)}</span></div>
        ${n.body ? html`<div class="small muted">${n.body}</div>` : ""}</div></div>`) : empty("مفيش إشعارات")}</div>`;
    $("#all").onclick = async () => { await api("notifications/read-all/", { method: "POST" }); window.EP.refreshUnread(); load(); };
  };
  page.addEventListener("click", async e => {
    const el = e.target.closest(".notif"); if (!el) return;
    if (el.classList.contains("unread")) { await api(`notifications/${el.dataset.id}/read/`, { method: "POST" }).catch(() => {}); window.EP.refreshUnread(); }
    if (el.dataset.to) go(el.dataset.to); else el.classList.remove("unread");
  });
  await load();
  return onEvent(ev => { if (ev === "notification.new") load(); });
}, { title: "الإشعارات" });

// ============================================================ Profile
route("/profile", async page => {
  const u = await api("me/");
  state.user = u;
  const subjects = u.role === "teacher" ? await api("subjects/") : [];
  const docs = u.role === "teacher" ? await api("me/teacher-documents/") : [];
  const grades = u.role === "student" ? await api("grades/") : [];
  const p = u.profile || {};
  page.innerHTML = html`<div class="page-head"><div><h1>حسابي</h1><p>${ROLE_AR[u.role]} · اسم الدخول <span dir="ltr">${u.username}</span> · ${u.phone}</p></div></div>
    <div class="cols"><div class="stack">
      <form class="panel" id="me-form"><div class="panel-head"><h2>البيانات الأساسية</h2></div>
        <div class="row" style="margin-bottom:14px">${avatar(u, "lg")}<label class="btn ghost sm">تغيير الصورة<input type="file" name="avatar" accept="image/*" hidden></label></div>
        <div class="form-grid">
          <div class="field"><label>الاسم</label><input class="input" name="full_name" value="${u.full_name}"></div>
          <div class="field"><label>الإيميل</label><input class="input" name="email" type="email" value="${u.email || ""}" dir="ltr"></div>
          <div class="field"><label>النوع</label><select class="input" name="gender"><option value="">—</option>
            <option value="male" ${u.gender === "male" ? "selected" : ""}>ذكر</option><option value="female" ${u.gender === "female" ? "selected" : ""}>أنثى</option></select></div>
        </div><div style="margin-top:14px"><button class="btn">حفظ</button></div></form>
      ${u.role === "student" ? html`<form class="panel" id="st-form"><div class="panel-head"><h2>بيانات الدراسة</h2></div><div class="form-grid">
          <div class="field"><label>الصف</label><select class="input" name="grade">${grades.map(g => html`<option value="${g.id}" ${p.grade === g.id ? "selected" : ""}>${g.name}</option>`)}</select></div>
          <div class="field"><label>المدرسة</label><input class="input" name="school" value="${p.school || ""}"></div></div>
          <div style="margin-top:14px"><button class="btn">حفظ</button></div></form>` : ""}
      ${u.role === "teacher" ? html`<form class="panel" id="tp-form"><div class="panel-head"><h2>البروفايل العام</h2>${badge(p.approval_status)}</div>
          <div class="stack">
          <div class="field"><label>العنوان المختصر</label><input class="input" name="headline" value="${p.headline || ""}"></div>
          <div class="field"><label>نبذة</label><textarea class="input" name="bio">${p.bio || ""}</textarea></div>
          <div class="form-grid"><div class="field"><label>سنين الخبرة</label><input class="input" type="number" name="experience_years" value="${p.experience_years || 0}"></div>
          <div class="field"><label>سعر الساعة</label><input class="input" type="number" name="hourly_rate" value="${p.hourly_rate || 0}"></div></div>
          <div class="field"><label>المواد</label><div class="row wrap">${subjects.map(sb => html`<label class="tag" style="cursor:pointer"><input type="checkbox" name="subject_ids" value="${sb.id}" ${(p.subjects || []).some(x => x.id === sb.id) ? "checked" : ""}> ${sb.name}</label>`)}</div></div>
          </div><div style="margin-top:14px"><button class="btn">حفظ</button></div></form>
        <section class="panel"><div class="panel-head"><h2>المستندات</h2></div>
          ${docs.map(dc => html`<div class="row between" style="padding:6px 0"><a href="${dc.file}" target="_blank">${dc.title}</a><span class="small muted">${fmt.short(dc.created_at)}</span></div>`)}
          <form id="doc-form" class="row wrap" style="margin-top:10px;align-items:flex-end"><div class="field"><label>اسم المستند</label><input class="input" name="title" required></div>
            <input type="file" name="file" required><button class="btn ghost">رفع</button></form></section>` : ""}
    </div><aside class="stack">
      <form class="panel" id="pw-form"><h2>تغيير كلمة السر</h2><div class="stack" style="margin-top:12px">
        <div class="field"><label>كلمة السر الحالية</label><input class="input" type="password" name="old_password" dir="ltr"></div>
        <div class="field"><label>الجديدة</label><input class="input" type="password" name="new_password" dir="ltr"></div>
        <button class="btn ghost">تغيير</button></div></form>
    </aside></div>`;
  $("#me-form").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    if (!fd.get("avatar")?.size) fd.delete("avatar");
    try { state.user = await api("me/", { method: "PATCH", form: fd }); toast("اتحفظ", "good"); location.reload(); } catch (err) { showErrors(e.target, err); }
  });
  $("#st-form")?.addEventListener("submit", async e => { e.preventDefault(); try { await api("me/student-profile/", { method: "PATCH", body: formData(e.target) }); toast("اتحفظ", "good"); } catch (err) { showErrors(e.target, err); } });
  $("#tp-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const body = formData(e.target); body.subject_ids = new FormData(e.target).getAll("subject_ids").map(Number);
    try { await api("me/teacher-profile/", { method: "PATCH", body }); toast("اتحفظ", "good"); } catch (err) { showErrors(e.target, err); }
  });
  $("#doc-form")?.addEventListener("submit", async e => { e.preventDefault(); try { await api("me/teacher-documents/", { method: "POST", form: new FormData(e.target) }); toast("اترفع", "good"); location.reload(); } catch (err) { showErrors(e.target, err); } });
  $("#pw-form").addEventListener("submit", async e => { e.preventDefault(); try { await api("auth/password/change/", { method: "POST", body: formData(e.target) }); toast("اتغيرت كلمة السر", "good"); e.target.reset(); } catch (err) { showErrors(e.target, err); } });
}, { title: "حسابي" });

void esc;
