import { $, $$, api, avatar, badge, busy, confirmBox, empty, fail, fmt, formData, go, html, ico, list, modal, raw, route, score, showErrors,
  state, toast, WEEKDAYS } from "./core.js";
import { sessionSlot, bindSessionActions } from "./views-common.js";

const me = () => state.user;
const isStaff = () => ["admin", "supervisor"].includes(me().role);

// ============================================================ Teachers (browse + subscribe + trial)
route("/teachers", async (page, _p, q) => {
  const subjects = await api("subjects/");
  const d = await api("teachers/", { query: { subjects: q.subject, search: q.search, page_size: 60 } });
  page.innerHTML = html`<div class="page-head"><div><h1>المدرسين</h1><p>اختار مدرس واطلب حصة تجريبية أو اشترك على طول.</p></div>
    <form id="sf" class="row wrap"><select class="input" name="subject" style="width:auto"><option value="">كل المواد</option>
      ${subjects.map(s => html`<option value="${s.id}" ${String(q.subject) === String(s.id) ? "selected" : ""}>${s.name}</option>`)}</select>
      <input class="input" name="search" placeholder="اسم المدرس" value="${q.search || ""}" style="width:180px"><button class="btn ghost">بحث</button></form></div>
    <div class="grid g3">${list(d).map(t => html`<div class="card link" data-slug="${t.slug}">
      <div class="row">${avatar(t, "lg")}<div><b>${t.full_name}</b><div class="small muted">${t.headline}</div>
      ${t.rating_count ? html`<div class="small"><span class="stars">★ ${t.rating_avg}</span> <span class="muted">(${t.rating_count})</span></div>` : ""}</div></div>
      <div class="row wrap">${t.subjects.map(s => html`<span class="tag">${s.name}</span>`)}</div>
      <div class="row between small muted"><span>${t.experience_years} سنة خبرة</span><span>${fmt.money(t.hourly_rate)} / ساعة</span></div></div>`)}</div>
    ${list(d).length ? "" : empty("مفيش مدرسين بالبحث ده")}`;
  $("#sf").addEventListener("submit", e => { e.preventDefault(); const f = formData(e.target); go(`/teachers?subject=${f.subject}&search=${encodeURIComponent(f.search)}`); });
  page.addEventListener("click", e => { const c = e.target.closest("[data-slug]"); if (c) teacherModal(c.dataset.slug); });
}, { title: "المدرسين" });

async function teacherModal(slug) {
  const t = await api(`teachers/${slug}/`);
  const [av, rv] = await Promise.all([api("availability/", { query: { teacher: t.user_id } }), api("reviews/", { query: { teacher: t.user_id, page_size: 5 } })]);
  const canAct = me().role === "student";
  modal(t.full_name, html`<div class="row" style="margin-bottom:12px">${avatar(t, "lg")}<div><b>${t.headline}</b>
      <div class="small muted">${t.experience_years} سنة خبرة · ${t.rating_count ? `★ ${t.rating_avg} (${t.rating_count})` : "لسه مفيش تقييمات"}</div>
      <div class="row wrap" style="margin-top:4px">${t.subjects.map(s => html`<span class="tag">${s.name}</span>`)}</div></div></div>
    <p>${t.bio}</p>${t.qualifications ? html`<p class="small muted">${t.qualifications}</p>` : ""}
    <h3 style="margin:14px 0 6px">المواعيد المتاحة</h3>
    <div class="row wrap">${av.length ? av.map(a => html`<span class="tag">${WEEKDAYS[a.weekday]} <span dir="ltr">${a.start_time.slice(0, 5)}–${a.end_time.slice(0, 5)}</span></span>`) : html`<span class="muted small">مش محددة</span>`}</div>
    ${list(rv).length ? html`<h3 style="margin:16px 0 6px">آراء الطلاب</h3>${list(rv).map(r => html`<div class="small" style="padding:6px 0;border-bottom:1px solid var(--line-2)"><span class="stars">${"★".repeat(r.rating)}</span> <b>${r.student.full_name}</b> ${r.comment}</div>`)}` : ""}
    ${canAct ? html`<div class="row wrap" style="margin-top:18px"><a class="btn" href="#/subscribe?teacher=${t.user_id}&subject=${t.subjects[0]?.id || ""}" data-close>اشترك مع ${t.full_name.split(" ").slice(0, 2).join(" ")}</a>
      ${me().role === "student" ? html`<button class="btn ghost" id="trial">اطلب حصة تجريبية مجانية</button>` : ""}</div>` : ""}`, {
    wide: true,
    onMount: (b, close) => {
      b.querySelector("[data-close]")?.addEventListener("click", close);
      b.querySelector("#trial")?.addEventListener("click", () => { close(); trialDialog(t); });
    },
  });
}

function trialDialog(t) {
  modal("طلب حصة تجريبية", html`<form class="stack">
    <div class="field"><label>المادة</label><select class="input" name="subject">${t.subjects.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></div>
    <div class="field"><label>المواعيد اللي تناسبك</label><input class="input" name="preferred_times" placeholder="مثلاً: أي يوم بعد 6 المغرب"></div>
    <div class="field"><label>ملاحظات</label><textarea class="input" name="notes"></textarea></div>
    <button class="btn">ابعت الطلب</button></form>`, {
    onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault();
      try { await api("trials/", { method: "POST", body: { ...formData(e.target), preferred_teacher: t.user_id } }); close(); toast("الطلب اتبعت — الإدارة هتحدد الميعاد", "good"); }
      catch (err) { showErrors(e.target, err); }
    }),
  });
}

// ============================================================ Subscribe wizard
route("/subscribe", async (page, _p, q) => {
  const subjects = await api("subjects/");
  let subject = q.subject || subjects[0]?.id;
  const draw = async () => {
    const [pkgs, teachers] = await Promise.all([api("packages/", { query: { subject } }), api("teachers/", { query: { subjects: subject, page_size: 50 } })]);
    page.innerHTML = html`<div class="page-head"><div><h1>اشتراك جديد</h1><p>اختار المادة والباقة، والمدرس لو حابب. بعد الدفع الإدارة بتحدد مواعيدك.</p></div></div>
      <form id="sub" class="stack" style="max-width:760px">
        <div class="panel"><div class="field"><label>المادة</label><select class="input" name="subject" id="subj">
          ${subjects.map(s => html`<option value="${s.id}" ${String(s.id) === String(subject) ? "selected" : ""}>${s.name}</option>`)}</select></div></div>
        <div class="panel"><h2 style="margin-bottom:12px">الباقة</h2><div class="grid g3">${pkgs.map((p, i) => html`<label class="card link" style="gap:4px">
          <div class="row between"><b>${p.name}</b><input type="radio" name="package" value="${p.id}" ${p.is_featured || (i === 0 && !pkgs.some(x => x.is_featured)) ? "checked" : ""}></div>
          <div class="price" style="font-size:22px">${fmt.money(p.price, p.currency)}${p.old_price ? html`<s>${fmt.money(p.old_price)}</s>` : ""}</div>
          <div class="small muted">${p.sessions_count} حصة × ${p.session_duration} دقيقة · صالحة ${p.duration_days} يوم</div></label>`)}</div></div>
        <div class="panel"><div class="form-grid">
          <div class="field"><label>المدرس المفضّل (اختياري)</label><select class="input" name="preferred_teacher"><option value="">الإدارة تختار الأنسب</option>
            ${list(teachers).map(t => html`<option value="${t.user_id}" ${String(q.teacher) === String(t.user_id) ? "selected" : ""}>${t.full_name}</option>`)}</select></div>
          <div class="field"><label>المواعيد اللي تناسبك</label><input class="input" name="preferred_times" placeholder="مثلاً: السبت والثلاثاء بعد 5"></div></div>
          <div class="field" style="margin-top:12px"><label>كود خصم (اختياري)</label><input class="input" name="coupon" dir="ltr" placeholder="WELCOME20" style="max-width:220px"></div></div>
        <div><button class="btn lg">اشترك وكمّل للدفع</button></div></form>`;
    $("#subj").onchange = e => { subject = e.target.value; draw(); };
    $("#sub").addEventListener("submit", async e => {
      e.preventDefault();
      const f = formData(e.target);
      await busy(e.submitter, async () => {
        const body = { package: Number(f.package), subject: Number(f.subject), preferred_times: f.preferred_times };
        if (f.preferred_teacher) body.preferred_teacher = Number(f.preferred_teacher);
        const sub = await api("subscriptions/", { method: "POST", body });
        await checkout({ kind: "subscription", subscription_id: sub.id, coupon: f.coupon }, `/subscriptions/${sub.id}`);
      });
    });
  };
  await draw();
}, { title: "اشتراك جديد", roles: ["student"] });

// يبدأ الدفع: لو مجاني بيتفعل فوراً، غير كده يفتح صفحة الدفع ويستنى النتيجة
export async function checkout(body, after) {
  const r = await api("payments/checkout/", { method: "POST", body: Object.fromEntries(Object.entries(body).filter(([, v]) => v)) });
  if (r.order.status === "paid") { toast("تم التفعيل ✅", "good"); go(after); return; }
  const w = window.open(r.checkout_url, "_blank");
  const close = modal("كمّل الدفع", html`<p>صفحة الدفع اتفتحت في تاب جديد. بعد ما تدفع ارجع هنا.</p>
    <p class="muted small">المبلغ: <b>${fmt.money(r.order.total, r.order.currency)}</b>${Number(r.order.discount) ? ` (خصم ${fmt.money(r.order.discount)})` : ""}</p>
    <div class="row wrap"><a class="btn ghost" href="${r.checkout_url}" target="_blank">افتح صفحة الدفع</a><button class="btn" id="chk">دفعت، اتأكد</button></div>
    <p class="small muted" id="st" style="margin-top:10px">مستني الدفع…</p>`, {
    onMount: (b, c) => b.querySelector("#chk").addEventListener("click", () => poll(true)),
  });
  let tries = 0;
  const poll = async manual => {
    const o = await api(`payments/orders/${r.order.id}/`);
    const st = $("#st");
    if (o.status === "paid") { close(); toast("تم الدفع والتفعيل ✅", "good"); go(after); location.reload(); return; }
    if (o.status === "failed") { if (st) st.textContent = "عملية الدفع فشلت — جرّب تاني."; return; }
    if (manual && st) st.textContent = "لسه الدفع موصلش…";
    if (++tries < 90 && document.body.contains(st)) setTimeout(poll, 2000);
  };
  setTimeout(poll, 2500);
  void w;
}

// ============================================================ Subscriptions
route("/subscriptions", async (page, _p, q) => {
  const d = await api("subscriptions/", { query: { status: q.status, page_size: 100 } });
  const rows = list(d);
  const canNew = me().role === "student";
  page.innerHTML = html`<div class="page-head"><div><h1>${isStaff() ? "الاشتراكات" : "اشتراكاتي"}</h1><p>${fmt.num(d.count)} اشتراك</p></div>
    <div class="row wrap">${isStaff() ? html`<select class="input" id="flt" style="width:auto"><option value="">كل الحالات</option>
      ${["pending_payment", "pending_assignment", "active", "paused", "expired", "cancelled"].map(s => html`<option value="${s}" ${q.status === s ? "selected" : ""}>${raw(badge(s).s.replace(/<[^>]+>/g, ""))}</option>`)}</select>` : ""}
      ${canNew ? html`<a class="btn" href="#/subscribe">اشتراك جديد</a>` : ""}</div></div>
    ${rows.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>المادة</th>${me().role !== "student" ? html`<th>الطالب</th>` : ""}<th>المدرس</th><th>الباقة</th><th>الحصص</th><th>الحالة</th><th>الحصة الجاية</th></tr></thead>
      <tbody>${rows.map(s => html`<tr class="click" data-id="${s.id}"><td><b>${s.subject.name}</b></td>${me().role !== "student" ? html`<td>${s.student.full_name}</td>` : ""}
        <td>${s.teacher?.full_name || html`<span class="muted">لسه</span>`}</td><td>${s.package.name}</td><td>${s.sessions_used}/${s.sessions_total}</td><td>${badge(s.status)}</td>
        <td class="small">${s.next_session ? fmt.full(s.next_session) : "—"}</td></tr>`)}</tbody></table></div>` : empty("مفيش اشتراكات", canNew ? raw('<p><a class="btn" href="#/subscribe">اشترك دلوقتي</a></p>') : "")}`;
  page.querySelector("tbody")?.addEventListener("click", e => { const tr = e.target.closest("tr"); if (tr) go(`/subscriptions/${tr.dataset.id}`); });
  $("#flt")?.addEventListener("change", e => go(`/subscriptions?status=${e.target.value}`));
}, { title: "الاشتراكات" });

route("/subscriptions/:id", async (page, { id }) => {
  const s = await api(`subscriptions/${id}/`);
  const sess = list(await api("sessions/", { query: { subscription: id, page_size: 100, ordering: "scheduled_at" } }));
  const mine = me().role === "student";
  page.innerHTML = html`<div class="page-head"><div><h1>${s.subject.name} — ${s.package.name}</h1><p>${s.student.full_name}${s.teacher ? ` مع ${s.teacher.full_name}` : ""}</p></div>
    <div class="row wrap">${badge(s.status)}
      ${mine && s.status === "pending_payment" ? html`<button class="btn" id="pay">ادفع ${fmt.money(s.package.price)}</button>` : ""}
      ${mine && ["expired", "active"].includes(s.status) ? html`<button class="btn ghost" id="renew">جدّد الاشتراك</button>` : ""}
      ${isStaff() && ["pending_assignment", "active", "paused"].includes(s.status) ? html`<a class="btn" href="#/assign?sub=${s.id}">${s.teacher ? "تغيير المدرس/المواعيد" : "تعيين مدرس"}</a>` : ""}
      ${isStaff() && s.status === "pending_payment" ? html`<button class="btn ghost" data-adm="mark-paid">تسجيل دفع كاش</button>` : ""}
      ${isStaff() && s.status === "active" ? html`<button class="btn ghost" data-adm="pause">إيقاف مؤقت</button>` : ""}
      ${isStaff() && s.status === "paused" ? html`<button class="btn ghost" data-adm="resume">استئناف</button>` : ""}
      ${isStaff() && !["cancelled", "expired"].includes(s.status) ? html`<button class="btn danger" data-adm="cancel">إلغاء</button>` : ""}</div></div>
    <div class="grid g4" style="margin-bottom:18px">
      <div class="stat"><div class="v">${s.sessions_remaining}</div><div class="k">حصة باقية من ${s.sessions_total}</div></div>
      <div class="stat"><div class="v">${s.session_duration}</div><div class="k">دقيقة للحصة</div></div>
      <div class="stat"><div class="v small" style="font-size:16px">${s.end_date ? fmt.short(s.end_date) : "—"}</div><div class="k">ينتهي في</div></div>
      <div class="stat"><div class="v small" style="font-size:16px">${s.slots.length ? s.slots.map(x => `${WEEKDAYS[x.weekday]} ${x.start_time.slice(0, 5)}`).join(" · ") : "—"}</div><div class="k">المواعيد الثابتة</div></div>
    </div>
    ${s.status === "pending_assignment" ? html`<div class="panel" style="margin-bottom:18px;background:var(--chalk-soft);border-color:#EED38A">الإدارة بتحدد ${s.preferred_times ? "المواعيد المناسبة" : "المدرس والمواعيد"} — هيوصلك إشعار أول ما يتفعل.</div>` : ""}
    <section class="panel"><div class="panel-head"><h2>الحصص</h2><span class="muted small">${sess.length} حصة</span></div>
      ${sess.length ? html`<div class="sched">${sess.map(x => sessionSlot(x))}</div>` : empty("لسه مفيش حصص")}</section>`;
  bindSessionActions(page, () => location.reload());
  $("#pay")?.addEventListener("click", e => busy(e.target, () => checkout({ kind: "subscription", subscription_id: s.id }, `/subscriptions/${s.id}`)));
  $("#renew")?.addEventListener("click", e => busy(e.target, async () => {
    const n = await api(`subscriptions/${s.id}/renew/`, { method: "POST" });
    await checkout({ kind: "subscription", subscription_id: n.id }, `/subscriptions/${n.id}`);
  }));
  page.addEventListener("click", async e => {
    const b = e.target.closest("[data-adm]"); if (!b) return;
    const a = b.dataset.adm;
    if (!(await confirmBox({ "mark-paid": "تأكيد إن الطالب دفع كاش؟", pause: "إيقاف الاشتراك مؤقتاً؟ الحصص الجاية هتتلغي.", resume: "استئناف الاشتراك؟", cancel: "إلغاء الاشتراك نهائياً؟" }[a]))) return;
    busy(b, async () => { await api(`subscriptions/${s.id}/${a}/`, { method: "POST", body: a === "cancel" ? { reason: "من الإدارة" } : undefined }); toast("تم", "good"); location.reload(); });
  });
}, { title: "تفاصيل الاشتراك" });

// ============================================================ Quizzes (student)
route("/quizzes", async page => {
  const d = list(await api("quizzes/", { query: { page_size: 100 } }));
  const KIND = { homework: "واجب", quiz: "اختبار قصير", exam: "امتحان" };
  page.innerHTML = html`<div class="page-head"><div><h1>الواجبات والامتحانات</h1><p>اللي اتبعتلك من مدرسينك واختبارات الكورسات.</p></div><a class="btn ghost" href="#/results">نتايجي</a></div>
    ${d.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>العنوان</th><th>النوع</th><th>المدرس</th><th>الوقت</th><th>آخر ميعاد</th><th>محاولاتك</th><th>أعلى درجة</th><th></th></tr></thead><tbody>
      ${d.map(x => html`<tr><td><b>${x.title}</b><div class="small muted">${x.questions_count} سؤال · ${x.total_points} درجة</div></td><td>${KIND[x.kind]}</td><td>${x.owner?.full_name}</td>
        <td>${x.time_limit_minutes ? `${x.time_limit_minutes} دقيقة` : "مفتوح"}</td><td class="small">${x.due_at ? fmt.full(x.due_at) : "—"}</td>
        <td>${x.my_attempts}${x.max_attempts ? ` / ${x.max_attempts}` : ""}</td><td>${x.best_score != null ? score(x.best_score, x.total_points) : "—"}</td>
        <td><button class="btn sm" data-start="${x.id}" ${x.max_attempts && x.my_attempts >= x.max_attempts ? "disabled" : ""}>${x.my_attempts ? "حاول تاني" : "ابدأ"}</button></td></tr>`)}</tbody></table></div>` : empty("مفيش واجبات دلوقتي")}`;
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-start]"); if (!b) return;
    busy(b, async () => { const a = await api(`quizzes/${b.dataset.start}/start/`, { method: "POST" }); go(`/attempts/${a.id}`); });
  });
}, { title: "الواجبات والامتحانات", roles: ["student"] });

// نتيجة كويز درس/امتحان وحدة: رسالة واضحة + رجوع للكورس
function linkedBox(a) {
  const L = a.quiz.linked;
  if (!L || a.student.id !== me().id) return "";
  const back = L.role === "lesson" ? `#/courses/${L.course_slug}?lesson=${L.lesson_id}` : `#/courses/${L.course_slug}?exam=${L.section_id}`;
  const graded = a.status === "graded";
  const left = a.quiz.max_attempts ? a.quiz.max_attempts - a.quiz.my_attempts : null;
  return html`<div class="callout ${!graded ? "warn" : a.passed ? "good" : "bad"} linked-res">${ico(a.passed ? "award" : "info")}<div style="flex:1">
    <b>${!graded ? "مستني تصحيح المدرس" : a.passed ? (L.role === "lesson" ? "نجحت في كويز الدرس 🎉 الدرس اللي بعده اتفتح" : "نجحت في امتحان الوحدة 🎉 الوحدة اللي بعدها اتفتحت")
      : `محتاج ${a.quiz.pass_percent}٪ عشان تنجح — راجع ${L.role === "lesson" ? "الدرس" : "دروس الوحدة"} وحاول تاني`}</b>
    <div class="small">${L.course_title} · ${L.role === "lesson" ? L.lesson_title : L.section_title}${!a.passed && left != null ? ` · باقي ${left} محاولة` : ""}</div></div>
    <div class="row wrap">${graded && !a.passed && (left == null || left > 0) ? html`<button class="btn sm" data-retry="${a.quiz.id}">حاول تاني</button>` : ""}
      <a class="btn ${a.passed ? "" : "ghost"} sm" href="${back}">${ico("arrowPrev", 15)} ارجع للكورس</a></div></div>`;
}

route("/attempts/:id", async (page, { id }) => {
  const a = await api(`attempts/${id}/`);
  const answers = Object.fromEntries((a.answers || []).map(x => [x.question, x]));
  const solving = a.status === "in_progress" && a.student.id === me().id;
  let timer;
  if (solving) {
    page.innerHTML = html`<div class="page-head"><div><h1>${a.quiz.title}</h1><p>${a.quiz.linked ? `${a.quiz.linked.course_title} · ` : ""}${a.questions.length} سؤال · النجاح من ${a.quiz.pass_percent}٪ · إجاباتك بتتحفظ أول بأول</p></div>
      ${a.remaining_seconds != null ? html`<div class="timer" id="timer"></div>` : ""}</div>
      <form id="qz">${a.questions.map((q, i) => html`<div class="q" data-q="${q.id}"><div class="row between"><b>${i + 1}. ${q.text}</b><span class="small muted">${q.points} درجة</span></div>
        ${q.image ? html`<img src="${q.image}" alt="" style="max-width:320px;margin-top:8px">` : ""}
        ${["single", "true_false"].includes(q.type) ? q.choices.map(c => html`<label class="opt"><input type="radio" name="q${q.id}" value="${c.id}" ${answers[q.id]?.selected_choices?.includes(c.id) ? "checked" : ""}> ${c.text}</label>`) : ""}
        ${q.type === "multiple" ? q.choices.map(c => html`<label class="opt"><input type="checkbox" name="q${q.id}" value="${c.id}" ${answers[q.id]?.selected_choices?.includes(c.id) ? "checked" : ""}> ${c.text}</label>`) : ""}
        ${q.type === "short" ? html`<input class="input" style="margin-top:8px" name="q${q.id}" value="${answers[q.id]?.text_answer || ""}" dir="auto">` : ""}
        ${q.type === "essay" ? html`<textarea class="input" style="margin-top:8px" name="q${q.id}">${answers[q.id]?.text_answer || ""}</textarea>` : ""}
        ${q.type === "file" ? html`<input type="file" style="margin-top:8px" name="q${q.id}">` : ""}</div>`)}
      <div style="margin-top:18px"><button class="btn lg">تسليم</button></div></form>`;
    const save = async qEl => {
      const qid = Number(qEl.dataset.q);
      const q = a.questions.find(x => x.id === qid);
      const inputs = $$(`[name="q${qid}"]`, qEl);
      if (q.type === "file") {
        const f = inputs[0].files[0]; if (!f) return;
        const fd = new FormData(); fd.append("question", qid); fd.append("file", f);
        return api(`attempts/${id}/answer/`, { method: "POST", form: fd });
      }
      const body = { question: qid };
      if (["single", "true_false", "multiple"].includes(q.type)) body.selected_choices = inputs.filter(x => x.checked).map(x => Number(x.value));
      else body.text_answer = inputs[0].value;
      return api(`attempts/${id}/answer/`, { method: "POST", body });
    };
    const f = $("#qz");
    f.addEventListener("change", e => { const qEl = e.target.closest(".q"); if (qEl) save(qEl).catch(fail); });
    f.addEventListener("submit", async e => {
      e.preventDefault();
      if (!(await confirmBox("تسلّم الإجابات؟ مش هتقدر تعدل بعدها.", "تسليم"))) return;
      await busy(e.submitter, async () => {
        for (const qEl of $$(".q", f)) if (qEl.querySelector("textarea,input[type=text],input:not([type])")) await save(qEl);
        await api(`attempts/${id}/submit/`, { method: "POST" }); toast("اتسلمت ✅", "good"); location.reload();
      });
    });
    if (a.remaining_seconds != null) {
      let left = a.remaining_seconds;
      const tick = () => {
        const el = $("#timer"); if (!el) return clearInterval(timer);
        el.textContent = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")}`;
        if (left-- <= 0) { clearInterval(timer); api(`attempts/${id}/submit/`, { method: "POST" }).finally(() => location.reload()); }
      };
      tick(); timer = setInterval(tick, 1000);
    }
    return () => clearInterval(timer);
  }
  // النتيجة
  const canGrade = ["teacher", "admin", "supervisor"].includes(me().role) && a.status !== "in_progress";
  page.innerHTML = html`<div class="page-head"><div><h1>${a.quiz.title}</h1><p>${a.student.full_name} · ${fmt.full(a.submitted_at || a.started_at)}</p></div>
    <div class="row">${badge(a.status)}<div class="stat" style="padding:8px 16px"><div class="v">${score(a.score, a.max_score)}</div><div class="k">${a.percent}٪ ${a.status === "graded" ? (a.passed ? "· ناجح" : "· محتاج تحسين") : ""}</div></div></div></div>
    ${linkedBox(a)}
    ${a.status === "submitted" && !canGrade ? html`<div class="panel" style="margin-bottom:14px;background:var(--chalk-soft);border-color:#EED38A">فيه أسئلة مقالية المدرس هيصححها، والنتيجة النهائية هتوصلك في إشعار.</div>` : ""}
    ${a.teacher_feedback ? html`<div class="panel" style="margin-bottom:14px"><b>ملاحظة المدرس:</b> ${a.teacher_feedback}</div>` : ""}
    <form id="grade">${a.questions.map((q, i) => {
      const ans = answers[q.id] || {};
      const manual = ["essay", "file"].includes(q.type);
      return html`<div class="q"><div class="row between"><b>${i + 1}. ${q.text}</b><span class="small">${ans.points_awarded != null ? score(ans.points_awarded, q.points) : html`<span class="badge b-yellow">مستني تصحيح</span>`}</span></div>
        ${q.choices.map(c => {
          const chosen = ans.selected_choices?.includes(c.id); const right = ans.correct_choices?.includes(c.id);
          return html`<div class="opt ${right ? "right" : chosen ? "wrong" : ""}">${chosen ? "◉" : "○"} ${c.text}${right ? " ✓" : ""}</div>`;
        })}
        ${ans.text_answer ? html`<div class="opt">${ans.text_answer}</div>` : ""}${ans.file ? html`<p><a href="${ans.file}" target="_blank">ملف الحل</a></p>` : ""}
        ${ans.explanation ? html`<p class="small muted">${ans.explanation}</p>` : ""}${ans.feedback ? html`<p class="small"><b>تعليق:</b> ${ans.feedback}</p>` : ""}
        ${canGrade && manual && ans.id ? html`<div class="row wrap" style="margin-top:10px"><input class="input" type="number" step="0.5" min="0" max="${q.points}" name="p_${ans.id}" value="${ans.points_awarded ?? ""}" placeholder="الدرجة" style="width:110px">
          <input class="input" name="f_${ans.id}" placeholder="تعليق" value="${ans.feedback || ""}" style="flex:1"></div>` : ""}</div>`;
    })}
    ${canGrade ? html`<div class="panel" style="margin-top:12px"><div class="field"><label>ملاحظة عامة للطالب</label><input class="input" name="teacher_feedback" value="${a.teacher_feedback || ""}"></div>
      <button class="btn" style="margin-top:12px">حفظ التصحيح</button></div>` : ""}</form>`;
  $("[data-retry]", page)?.addEventListener("click", e => busy(e.target, async () => {
    const n = await api(`quizzes/${e.target.dataset.retry}/start/`, { method: "POST" }); go(`/attempts/${n.id}`);
  }));
  $("#grade").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = formData(e.target);
    const items = Object.keys(fd).filter(k => k.startsWith("p_") && fd[k] !== "").map(k => ({ answer_id: Number(k.slice(2)), points_awarded: fd[k], feedback: fd["f_" + k.slice(2)] || "" }));
    await busy(e.submitter, async () => { await api(`attempts/${id}/grade/`, { method: "POST", body: { answers: items, teacher_feedback: fd.teacher_feedback } }); toast("اتحفظ التصحيح", "good"); location.reload(); });
  });
}, { title: "الاختبار" });

route("/results", async page => {
  const d = list(await api("attempts/", { query: { page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>نتايجي</h1></div></div>
    ${d.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>الاختبار</th><th>الحالة</th><th>الدرجة</th><th>النسبة</th><th>التاريخ</th></tr></thead><tbody>
      ${d.map(a => html`<tr class="click" data-id="${a.id}"><td><b>${a.quiz_title}</b></td><td>${badge(a.status)}</td>
        <td>${score(a.score, a.max_score)}</td><td>${a.percent}٪</td><td class="small">${fmt.full(a.submitted_at || a.started_at)}</td></tr>`)}</tbody></table></div>` : empty("لسه مفيش نتايج")}`;
  page.querySelector("tbody")?.addEventListener("click", e => { const tr = e.target.closest("tr"); if (tr) go(`/attempts/${tr.dataset.id}`); });
}, { title: "النتائج", roles: ["student"] });

