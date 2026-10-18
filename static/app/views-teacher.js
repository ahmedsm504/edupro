import { $, $$, api, avatar, badge, busy, confirmBox, empty, fmt, formData, go, html, list, modal, route, score, showErrors, state, toast,
  WEEKDAYS } from "./core.js";

const T_ROLES = ["teacher", "admin", "supervisor"];

// ============================================================ My students
route("/students", async page => {
  const rows = await api("teacher/students/");
  page.innerHTML = html`<div class="page-head"><div><h1>طلابي</h1><p>${rows.length} طالب عندهم اشتراك نشط معاك.</p></div></div>
    ${rows.length ? html`<div class="grid g3">${rows.map(r => html`<div class="card"><div class="row">${avatar(r.student)}<b>${r.student.full_name}</b></div>
      ${r.subscriptions.map(s => html`<div class="row between small" style="border-top:1px solid var(--line-2);padding-top:8px">
        <span>${s.subject.name} · ${s.slots.map(x => `${WEEKDAYS[x.weekday]} ${x.start_time.slice(0, 5)}`).join("، ")}</span>
        <span>${s.sessions_used}/${s.sessions_total} ${badge(s.status)}</span></div>`)}
      <div class="row wrap"><button class="btn ghost sm" data-chat="${r.student.id}">راسله</button>
        <a class="btn ghost sm" href="#/sessions?tab=all">الحصص</a></div></div>`)}</div>` : empty("لسه مفيش طلاب", "الإدارة بتعيّن الطلاب للمدرسين حسب المواعيد")}`;
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-chat]"); if (!b) return;
    busy(b, async () => { const c = await api("chat/conversations/start/", { method: "POST", body: { user_id: Number(b.dataset.chat) } }); go(`/chat?c=${c.id}`); });
  });
}, { title: "طلابي", roles: ["teacher"] });

// ============================================================ Availability week editor
route("/availability", async page => {
  let items = (await api("availability/")).map(a => ({ weekday: a.weekday, start_time: a.start_time.slice(0, 5), end_time: a.end_time.slice(0, 5) }));
  const draw = () => {
    page.innerHTML = html`<div class="page-head"><div><h1>مواعيدي المتاحة</h1><p>الطلاب والإدارة بيشوفوها عشان يختاروا مواعيد حصصك. بتوقيت ${state.user.timezone}.</p></div>
      <button class="btn" id="save">حفظ المواعيد</button></div>
      <div class="week">${WEEKDAYS.map((d, i) => html`<div class="day"><h3>${d}</h3>
        ${items.map((it, k) => it.weekday === i ? html`<div class="rng"><span>${it.start_time} – ${it.end_time}</span><button data-del="${k}" aria-label="حذف">×</button></div>` : "")}
        <button class="btn ghost sm block" data-add="${i}">+ ميعاد</button></div>`)}</div>`;
  };
  draw();
  page.addEventListener("click", async e => {
    const del = e.target.closest("[data-del]"); const add = e.target.closest("[data-add]");
    if (del) { items.splice(Number(del.dataset.del), 1); draw(); }
    if (add) {
      modal(`ميعاد يوم ${WEEKDAYS[add.dataset.add]}`, html`<form class="stack"><div class="form-grid">
        <div class="field"><label>من</label><input class="input" type="time" name="start_time" value="16:00" required></div>
        <div class="field"><label>إلى</label><input class="input" type="time" name="end_time" value="20:00" required></div></div>
        <button class="btn">إضافة</button></form>`, {
        onMount: (b, close) => b.querySelector("form").addEventListener("submit", ev => {
          ev.preventDefault(); const f = formData(ev.target);
          if (f.start_time >= f.end_time) return toast("وقت البداية لازم قبل النهاية", "bad");
          items.push({ weekday: Number(add.dataset.add), ...f }); close(); draw();
        }),
      });
    }
    if (e.target.id === "save") busy(e.target, async () => { await api("availability/bulk/", { method: "PUT", body: items }); toast("اتحفظت المواعيد", "good"); });
  });
}, { title: "مواعيدي المتاحة", roles: ["teacher"] });

// ============================================================ Quizzes (teacher)
const KIND = { homework: "واجب", quiz: "اختبار قصير", exam: "امتحان" };
const QTYPE = { single: "اختيار واحد", multiple: "اختيار متعدد", true_false: "صح وغلط", short: "إجابة قصيرة", essay: "مقالي", file: "رفع ملف" };

route("/t-quizzes", async page => {
  const d = list(await api("teacher/quizzes/", { query: { page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>الواجبات والامتحانات</h1><p>اعمل واجب أو امتحان وابعته لطلابك، والتصحيح التلقائي بيتم فوراً.</p></div>
    <button class="btn" id="new">واجب/امتحان جديد</button></div>
    ${d.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>العنوان</th><th>النوع</th><th>الأسئلة</th><th>الوقت</th><th>الحالة</th></tr></thead><tbody>
      ${d.map(q => html`<tr class="click" data-id="${q.id}"><td><b>${q.title}</b></td><td>${KIND[q.kind]}</td><td>${q.questions_count} (${q.total_points} درجة)</td>
        <td>${q.time_limit_minutes ? `${q.time_limit_minutes} د` : "مفتوح"}</td><td>${q.is_published ? html`<span class="badge b-green">منشور</span>` : html`<span class="badge">مسودة</span>`}</td></tr>`)}</tbody></table></div>` : empty("لسه معملتش واجبات")}`;
  page.querySelector("tbody")?.addEventListener("click", e => { const tr = e.target.closest("tr"); if (tr) go(`/t-quizzes/${tr.dataset.id}`); });
  $("#new").onclick = async () => {
    const subjects = await api("subjects/");
    modal("واجب/امتحان جديد", html`<form class="stack">
      <div class="field"><label>العنوان</label><input class="input" name="title" required></div>
      <div class="form-grid"><div class="field"><label>النوع</label><select class="input" name="kind">${Object.entries(KIND).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select></div>
        <div class="field"><label>المادة</label><select class="input" name="subject">${subjects.map(s => html`<option value="${s.id}">${s.name}</option>`)}</select></div>
        <div class="field"><label>الوقت بالدقايق (فاضي = مفتوح)</label><input class="input" type="number" name="time_limit_minutes" min="1"></div>
        <div class="field"><label>عدد المحاولات (0 = مفتوح)</label><input class="input" type="number" name="max_attempts" value="1" min="0"></div></div>
      <div class="field"><label>وصف</label><textarea class="input" name="description"></textarea></div>
      <button class="btn">إنشاء وإضافة الأسئلة</button></form>`, {
      onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
        e.preventDefault(); const f = formData(e.target); if (!f.time_limit_minutes) delete f.time_limit_minutes;
        try { const q = await api("teacher/quizzes/", { method: "POST", body: f }); close(); go(`/t-quizzes/${q.id}`); } catch (err) { showErrors(e.target, err); }
      }),
    });
  };
}, { title: "الواجبات والامتحانات", roles: T_ROLES });

route("/t-quizzes/:id", async (page, { id }) => {
  const q = await api(`teacher/quizzes/${id}/`);
  const atts = list(await api(`teacher/quizzes/${id}/attempts/`));
  page.innerHTML = html`<div class="page-head"><div><h1>${q.title}</h1><p>${KIND[q.kind]} · ${q.questions.length} سؤال · ${q.total_points} درجة</p></div>
    <div class="row wrap">${q.is_published ? html`<span class="badge b-green">منشور</span>` : html`<button class="btn ghost" id="pub">نشر</button>`}
      <button class="btn" id="assign">ابعته لطلاب</button></div></div>
    <div class="cols"><div>
      ${q.questions.map((x, i) => html`<div class="q"><div class="row between"><b>${i + 1}. ${x.text}</b><div class="row"><span class="badge">${QTYPE[x.type]}</span><span class="small muted">${x.points} درجة</span>
        <button class="btn danger sm" data-delq="${x.id}">حذف</button></div></div>
        ${x.choices.map(c => html`<div class="opt ${c.is_correct ? "right" : ""}">${c.text}${c.is_correct ? " ✓" : ""}</div>`)}
        ${x.type === "short" ? html`<div class="small muted">الإجابات المقبولة: ${x.correct_text}</div>` : ""}</div>`)}
      ${q.questions.length ? "" : empty("ضيف أول سؤال")}
      <form class="panel" id="addq" style="margin-top:14px"><h2>سؤال جديد</h2><div class="stack" style="margin-top:12px">
        <div class="form-grid"><div class="field"><label>النوع</label><select class="input" name="type" id="qtype">${Object.entries(QTYPE).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select></div>
          <div class="field"><label>الدرجة</label><input class="input" type="number" step="0.5" name="points" value="1"></div></div>
        <div class="field"><label>نص السؤال</label><textarea class="input" name="text" required></textarea></div>
        <div id="choices"></div>
        <div class="field hidden" id="short"><label>الإجابات المقبولة (افصل بينها بـ |)</label><input class="input" name="correct_text" dir="auto"></div>
        <div class="field"><label>شرح الإجابة (يظهر بعد التسليم)</label><input class="input" name="explanation"></div>
        <button class="btn">إضافة السؤال</button></div></form>
    </div><aside class="panel"><div class="panel-head"><h2>المحاولات</h2><span class="muted small">${atts.length}</span></div>
      ${atts.length ? atts.map(a => html`<a href="#/attempts/${a.id}" class="row between" style="padding:8px 0;border-bottom:1px solid var(--line-2);color:inherit;text-decoration:none">
        <span>${a.student.full_name}</span><span>${badge(a.status)} ${score(a.score, a.max_score)}</span></a>`) : empty("لسه محدش حل")}</aside></div>`;
  const drawChoices = () => {
    const t = $("#qtype").value;
    $("#short").classList.toggle("hidden", t !== "short");
    if (t === "true_false") $("#choices").innerHTML = html`<div class="field"><label>الإجابة الصحيحة</label><div class="row"><label><input type="radio" name="tf" value="1" checked> صح</label><label><input type="radio" name="tf" value="0"> غلط</label></div></div>`;
    else if (["single", "multiple"].includes(t)) $("#choices").innerHTML = html`<div class="field"><label>الاختيارات — علّم الصح</label>${[0, 1, 2, 3].map(i => html`<div class="row" style="margin-bottom:6px">
      <input type="${t === "single" ? "radio" : "checkbox"}" name="ok" value="${i}" ${i === 0 ? "checked" : ""}><input class="input" name="c${i}" placeholder="اختيار ${i + 1}"></div>`)}</div>`;
    else $("#choices").innerHTML = "";
  };
  $("#qtype").onchange = drawChoices; drawChoices();
  $("#addq").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target); const f = formData(e.target);
    const body = { quiz: Number(id), type: f.type, text: f.text, points: f.points, explanation: f.explanation, correct_text: f.correct_text || "", order: q.questions.length + 1 };
    if (f.type === "true_false") body.choices = [{ text: "صح", is_correct: f.tf === "1" }, { text: "غلط", is_correct: f.tf === "0" }];
    if (["single", "multiple"].includes(f.type)) {
      const ok = fd.getAll("ok");
      body.choices = [0, 1, 2, 3].filter(i => f[`c${i}`]).map(i => ({ text: f[`c${i}`], is_correct: ok.includes(String(i)) }));
    }
    try { await api("teacher/questions/", { method: "POST", body }); toast("اتضاف السؤال", "good"); location.reload(); } catch (err) { showErrors(e.target, err); }
  });
  page.addEventListener("click", async e => {
    const d = e.target.closest("[data-delq]");
    if (d && await confirmBox("تحذف السؤال؟", "حذف")) { await api(`teacher/questions/${d.dataset.delq}/`, { method: "DELETE" }); location.reload(); }
  });
  $("#pub")?.addEventListener("click", e => busy(e.target, async () => { await api(`teacher/quizzes/${id}/publish/`, { method: "POST" }); location.reload(); }));
  $("#assign").onclick = async () => {
    const rows = state.user.role === "teacher" ? await api("teacher/students/") : [];
    modal("ابعته لطلاب", rows.length ? html`<form class="stack">${rows.map(r => html`<label class="row"><input type="checkbox" name="s" value="${r.student.id}" checked> ${r.student.full_name}</label>`)}
      <div class="field"><label>آخر ميعاد للتسليم</label><input class="input" type="datetime-local" name="due_at"></div><button class="btn">إرسال</button></form>` : empty("مفيش طلاب عندك دلوقتي"), {
      onMount: (b, close) => b.querySelector("form")?.addEventListener("submit", async ev => {
        ev.preventDefault(); const fd = new FormData(ev.target);
        const body = { student_ids: fd.getAll("s").map(Number) }; if (fd.get("due_at")) body.due_at = new Date(fd.get("due_at")).toISOString();
        try { const r = await api(`teacher/quizzes/${id}/assign/`, { method: "POST", body }); close(); toast(`اتبعت لـ ${r.assigned} طالب`, "good"); location.reload(); } catch (err) { showErrors(ev.target, err); }
      }),
    });
  };
}, { title: "الواجب", roles: T_ROLES });

route("/grading", async page => {
  const d = list(await api("attempts/", { query: { status: "submitted", page_size: 100 } }));
  const all = list(await api("attempts/", { query: { page_size: 30 } }));
  const table = rows => html`<div class="table-wrap"><table class="t"><thead><tr><th>الطالب</th><th>الاختبار</th><th>الحالة</th><th>الدرجة</th><th>التاريخ</th></tr></thead><tbody>
    ${rows.map(a => html`<tr class="click" data-id="${a.id}"><td>${a.student.full_name}</td><td>${a.quiz_title}</td><td>${badge(a.status)}</td><td>${score(a.score, a.max_score)}</td><td class="small">${fmt.full(a.submitted_at)}</td></tr>`)}</tbody></table></div>`;
  page.innerHTML = html`<div class="page-head"><div><h1>التصحيح</h1><p>التسليمات اللي فيها أسئلة مقالية أو ملفات مستنياك.</p></div></div>
    <section style="margin-bottom:24px">${d.length ? table(d) : empty("مفيش تسليمات مستنية تصحيح 🎉")}</section>
    <h2 style="margin-bottom:10px">آخر المحاولات</h2>${all.length ? table(all) : empty("مفيش")}`;
  page.addEventListener("click", e => { const tr = e.target.closest("tr[data-id]"); if (tr) go(`/attempts/${tr.dataset.id}`); });
}, { title: "التصحيح", roles: T_ROLES });
