import { $, $$, api, avatar, badge, busy, confirmBox, empty, fmt, formData, go, html, list, modal, raw, ROLE_AR, route, showErrors,
  state, toast, WEEKDAYS } from "./core.js";

const STAFF = ["admin", "supervisor"];
const ADMIN = ["admin"];

// ============================================================ Teacher approvals
route("/approvals", async page => {
  const d = list(await api("admin/users/", { query: { role: "teacher", teacher_profile__approval_status: "pending", page_size: 100 } }));
  const sups = list(await api("admin/users/", { query: { role: "supervisor", page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>اعتماد المدرسين</h1><p>${d.length} طلب انضمام مستني المراجعة.</p></div></div>
    ${d.length ? html`<div class="grid g2">${d.map(u => html`<div class="card"><div class="row">${avatar(u, "lg")}<div><b>${u.full_name}</b>
      <div class="small muted">${u.phone} · سجّل ${fmt.short(u.date_joined)}</div></div></div>
      <div><b>${u.profile.headline}</b><p class="small">${u.profile.bio}</p><div class="row wrap">${u.profile.subjects.map(s => html`<span class="tag">${s.name}</span>`)}</div></div>
      <div class="row wrap" style="align-items:flex-end"><div class="field" style="flex:1"><label>المشرف</label><select class="input" data-sup="${u.id}">
        ${sups.map(s => html`<option value="${s.id}">${s.full_name}</option>`)}</select></div>
        <button class="btn" data-review="approve" data-id="${u.id}">اعتماد</button><button class="btn danger" data-review="reject" data-id="${u.id}">رفض</button></div></div>`)}</div>` : empty("مفيش طلبات جديدة")}`;
  page.addEventListener("click", async e => {
    const b = e.target.closest("[data-review]"); if (!b) return;
    let reason = "";
    if (b.dataset.review === "reject") { reason = prompt("سبب الرفض؟") ?? ""; }
    busy(b, async () => {
      await api(`admin/users/${b.dataset.id}/teacher-review/`, { method: "POST", body: { action: b.dataset.review, reason, supervisor: Number($(`[data-sup="${b.dataset.id}"]`).value) } });
      toast(b.dataset.review === "approve" ? "تم الاعتماد" : "تم الرفض", "good"); location.reload();
    });
  });
}, { title: "اعتماد المدرسين", roles: ADMIN });

// ============================================================ Users
route("/users", async (page, _p, q) => {
  const d = await api("admin/users/", { query: { role: q.role, search: q.search, page: q.page, page_size: 50 } });
  const rows = list(d);
  page.innerHTML = html`<div class="page-head"><div><h1>المستخدمين</h1><p>${fmt.num(d.count)} مستخدم</p></div>
    <div class="row wrap"><form id="f" class="row"><select class="input" name="role" style="width:auto"><option value="">كل الأدوار</option>
      ${Object.entries(ROLE_AR).map(([k, v]) => html`<option value="${k}" ${q.role === k ? "selected" : ""}>${v}</option>`)}</select>
      <input class="input" name="search" placeholder="اسم أو موبايل" value="${q.search || ""}" style="width:180px"><button class="btn ghost">بحث</button></form>
      <button class="btn" id="new">مستخدم جديد</button></div></div>
    <div class="table-wrap"><table class="t"><thead><tr><th>الاسم</th><th>اسم الدخول</th><th>الدور</th><th>الموبايل</th><th>الحالة</th><th>آخر دخول</th><th></th></tr></thead><tbody>
      ${rows.map(u => html`<tr><td><div class="row">${avatar(u)}<b>${u.full_name}</b></div></td><td dir="ltr" style="text-align:end">${u.username}</td><td>${ROLE_AR[u.role]}
        ${u.role === "teacher" && u.profile ? badge(u.profile.approval_status) : ""}</td><td dir="ltr" style="text-align:end">${u.phone}</td>
        <td>${u.is_active ? html`<span class="badge b-green">نشط</span>` : html`<span class="badge b-red">موقوف</span>`}</td><td class="small">${u.last_login ? fmt.ago(u.last_login) : "—"}</td>
        <td>${u.is_active && u.id !== state.user.id ? html`<button class="btn danger sm" data-off="${u.id}">إيقاف</button>` : !u.is_active ? html`<button class="btn ghost sm" data-on="${u.id}">تفعيل</button>` : ""}</td></tr>`)}</tbody></table></div>
    ${d.next || d.previous ? html`<div class="row" style="justify-content:center;margin-top:14px">${d.previous ? html`<a class="btn ghost sm" href="#/users?role=${q.role || ""}&page=${Number(q.page || 1) - 1}">السابق</a>` : ""}
      ${d.next ? html`<a class="btn ghost sm" href="#/users?role=${q.role || ""}&page=${Number(q.page || 1) + 1}">التالي</a>` : ""}</div>` : ""}`;
  $("#f").addEventListener("submit", e => { e.preventDefault(); const f = formData(e.target); go(`/users?role=${f.role}&search=${encodeURIComponent(f.search)}`); });
  page.addEventListener("click", async e => {
    const off = e.target.closest("[data-off]"), on = e.target.closest("[data-on]");
    if (off && await confirmBox("إيقاف المستخدم ده؟ مش هيقدر يدخل.", "إيقاف")) { await api(`admin/users/${off.dataset.off}/`, { method: "DELETE" }); location.reload(); }
    if (on) { await api(`admin/users/${on.dataset.on}/`, { method: "PATCH", body: { is_active: true } }); location.reload(); }
  });
  $("#new").onclick = () => modal("مستخدم جديد", html`<form class="stack"><div class="form-grid">
      <div class="field"><label>الاسم</label><input class="input" name="full_name" required></div>
      <div class="field"><label>الموبايل</label><input class="input" name="phone" dir="ltr" required></div>
      <div class="field"><label>الدور</label><select class="input" name="role">${Object.entries(ROLE_AR).map(([k, v]) => html`<option value="${k}">${v}</option>`)}</select></div>
      <div class="field"><label>كلمة السر</label><input class="input" name="password" value="admin12345" dir="ltr"></div></div><button class="btn">إنشاء</button></form>`, {
    onMount: (b, close) => b.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault(); try { await api("admin/users/", { method: "POST", body: formData(e.target) }); close(); toast("اتعمل المستخدم — يدخل برقم الموبايل", "good"); location.reload(); } catch (err) { showErrors(e.target, err); }
    }),
  });
}, { title: "المستخدمين", roles: STAFF });

// ============================================================ Assign teacher + weekly slots
route("/assign", async (page, _p, q) => {
  const pending = list(await api("subscriptions/", { query: { status: "pending_assignment", page_size: 100 } }));
  let sel = q.sub ? await api(`subscriptions/${q.sub}/`) : pending[0];
  const draw = async () => {
    let form = empty("مفيش اشتراكات مستنية تعيين 🎉");
    if (sel) {
      const teachers = list(await api("teachers/", { query: { subjects: sel.subject.id, page_size: 50 } }));
      const tid = sel.teacher?.id || sel.preferred_teacher || teachers[0]?.user_id;
      form = html`<form class="panel" id="af"><div class="panel-head"><h2>${sel.student.full_name} — ${sel.subject.name}</h2>${badge(sel.status)}</div>
        <p class="small muted">${sel.package.name} · ${sel.package.sessions_count} حصة × ${sel.package.session_duration} دقيقة${sel.preferred_times ? ` · المواعيد المفضلة: ${sel.preferred_times}` : ""}</p>
        <div class="field"><label>المدرس</label><select class="input" name="teacher" id="tsel">${teachers.map(t => html`<option value="${t.user_id}" ${t.user_id === tid ? "selected" : ""}>${t.full_name} (★ ${t.rating_avg})</option>`)}</select></div>
        <div class="small muted" id="avail" style="margin:8px 0 14px"></div>
        <div class="field"><label>المواعيد الأسبوعية الثابتة</label><div id="slots" class="stack"></div>
          <button type="button" class="btn ghost sm" id="addslot" style="justify-self:start;margin-top:6px">+ ميعاد</button></div>
        <div class="field" style="margin-top:12px"><label>تاريخ البداية</label><input class="input" type="date" name="start_date" value="${new Date().toISOString().slice(0, 10)}" style="max-width:200px"></div>
        <button class="btn lg" style="margin-top:16px">تفعيل الاشتراك وتوليد الحصص</button></form>`;
    }
    page.innerHTML = html`<div class="page-head"><div><h1>تعيين مدرسين</h1><p>اختار المدرس والمواعيد الثابتة، والسيستم يولّد الحصص ويبلّغ الطالب والمدرس.</p></div></div>
      <div class="cols"><div>${form}</div><aside class="panel"><div class="panel-head"><h2>مستنية تعيين</h2><span class="badge b-yellow">${pending.length}</span></div>
        ${pending.map(s => html`<button class="btn ghost block" style="justify-content:space-between;margin-bottom:6px" data-sub="${s.id}"><span>${s.student.full_name}</span><span class="small muted">${s.subject.name}</span></button>`)}
        ${pending.length ? "" : empty("خلصانين")}</aside></div>`;
    if (!sel) return;
    const slotRow = (wd = 0, t = "18:00") => html`<div class="row"><select class="input" name="wd" style="width:140px">${WEEKDAYS.map((d, i) => html`<option value="${i}" ${i === wd ? "selected" : ""}>${d}</option>`)}</select>
      <input class="input" type="time" name="st" value="${t}" style="width:140px"><button type="button" class="btn danger sm" data-rm>×</button></div>`;
    const initial = sel.slots.length ? sel.slots.map(x => [x.weekday, x.start_time.slice(0, 5)]) : [[5, "18:00"], [1, "18:00"]].slice(0, Math.max(1, Math.round(sel.package.sessions_count / 4)));
    $("#slots").innerHTML = initial.map(([w, t]) => slotRow(w, t).s).join("");
    $("#addslot").onclick = () => $("#slots").insertAdjacentHTML("beforeend", slotRow().s);
    $("#slots").onclick = e => { if (e.target.closest("[data-rm]")) e.target.closest(".row").remove(); };
    const showAvail = async () => {
      const av = await api("availability/", { query: { teacher: $("#tsel").value } });
      $("#avail").textContent = av.length ? "متاح: " + av.map(a => `${WEEKDAYS[a.weekday]} ${a.start_time.slice(0, 5)}–${a.end_time.slice(0, 5)}`).join(" · ") : "المدرس مسجلش مواعيد متاحة";
    };
    $("#tsel").onchange = showAvail; showAvail();
    $("#af").addEventListener("submit", async e => {
      e.preventDefault();
      const wds = $$("[name=wd]", e.target).map(x => Number(x.value)), sts = $$("[name=st]", e.target).map(x => x.value);
      const body = { teacher: Number(e.target.teacher.value), start_date: e.target.start_date.value, slots: wds.map((w, i) => ({ weekday: w, start_time: sts[i] })) };
      await busy(e.submitter, async () => {
        try { const r = await api(`subscriptions/${sel.id}/assign/`, { method: "POST", body }); toast(`اتفعل الاشتراك — الحصة الجاية ${r.next_session ? fmt.full(r.next_session) : ""}`, "good"); go(`/subscriptions/${sel.id}`); }
        catch (err) { showErrors(e.target, err); }
      });
    });
  };
  page.addEventListener("click", async e => { const b = e.target.closest("[data-sub]"); if (b) { sel = await api(`subscriptions/${b.dataset.sub}/`); draw(); } });
  await draw();
}, { title: "تعيين مدرسين", roles: STAFF });

// ============================================================ Trials
route("/trials", async page => {
  const d = list(await api("trials/", { query: { page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>الحصص التجريبية</h1><p>حدد المدرس والميعاد، والحصة بتظهر في جدول الطالب والمدرس.</p></div></div>
    ${d.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>الطالب</th><th>المادة</th><th>المواعيد المفضلة</th><th>الحالة</th><th>الحصة</th><th></th></tr></thead><tbody>
      ${d.map(t => html`<tr><td>${t.student.full_name}</td><td>${t.subject_info.name}</td><td class="small">${t.preferred_times || "—"}${t.notes ? html`<div class="muted">${t.notes}</div>` : ""}</td><td>${badge(t.status)}</td>
        <td class="small">${t.session ? html`<a href="#/sessions/${t.session.id}">${fmt.full(t.session.scheduled_at)} — ${t.session.teacher.full_name}</a>` : "—"}</td>
        <td>${t.status === "pending" ? html`<button class="btn sm" data-sched="${t.id}" data-subj="${t.subject}" data-pt="${t.preferred_teacher || ""}">حدد الميعاد</button>` : ""}</td></tr>`)}</tbody></table></div>` : empty("مفيش طلبات")}`;
  page.addEventListener("click", async e => {
    const b = e.target.closest("[data-sched]"); if (!b) return;
    const teachers = list(await api("teachers/", { query: { subjects: b.dataset.subj } }));
    const tomorrow = new Date(Date.now() + 864e5); tomorrow.setHours(14, 0, 0, 0);
    const local = new Date(tomorrow - tomorrow.getTimezoneOffset() * 6e4).toISOString().slice(0, 16);
    modal("تحديد الحصة التجريبية", html`<form class="stack"><div class="field"><label>المدرس</label><select class="input" name="teacher">
      ${teachers.map(t => html`<option value="${t.user_id}" ${String(t.user_id) === b.dataset.pt ? "selected" : ""}>${t.full_name}</option>`)}</select></div>
      <div class="form-grid"><div class="field"><label>الميعاد</label><input class="input" type="datetime-local" name="at" value="${local}" required></div>
      <div class="field"><label>المدة (دقيقة)</label><input class="input" type="number" name="duration" value="30"></div></div><button class="btn">تأكيد</button></form>`, {
      onMount: (m, close) => m.querySelector("form").addEventListener("submit", async ev => {
        ev.preventDefault(); const f = formData(ev.target);
        try { await api(`trials/${b.dataset.sched}/schedule/`, { method: "POST", body: { teacher: Number(f.teacher), duration: Number(f.duration), scheduled_at: new Date(f.at).toISOString() } }); close(); toast("اتحددت الحصة", "good"); location.reload(); }
        catch (err) { showErrors(ev.target, err); }
      }),
    });
  });
}, { title: "الحصص التجريبية", roles: STAFF });

// ============================================================ Reschedule requests
route("/reschedules", async page => {
  const d = list(await api("reschedule-requests/", { query: { page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>طلبات تغيير المواعيد</h1></div></div>
    ${d.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>الحصة</th><th>صاحب الطلب</th><th>الميعاد الحالي</th><th>المقترح</th><th>السبب</th><th>الحالة</th><th></th></tr></thead><tbody>
      ${d.map(r => html`<tr><td><a href="#/sessions/${r.session}">${r.session_info.subject.name} · ${r.session_info.teacher.full_name} ← ${r.session_info.student.full_name}</a></td><td>${r.requested_by.full_name}</td>
        <td class="small">${fmt.full(r.session_info.scheduled_at)}</td><td class="small"><b>${fmt.full(r.proposed_time)}</b></td><td class="small">${r.reason}</td><td>${badge(r.status)}</td>
        <td>${r.status === "pending" ? html`<div class="row"><button class="btn sm" data-a="approve" data-id="${r.id}">موافقة</button><button class="btn danger sm" data-a="reject" data-id="${r.id}">رفض</button></div>` : ""}</td></tr>`)}</tbody></table></div>` : empty("مفيش طلبات")}`;
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-a]"); if (!b) return;
    busy(b, async () => { await api(`reschedule-requests/${b.dataset.id}/${b.dataset.a}/`, { method: "POST" }); toast("تم", "good"); location.reload(); });
  });
}, { title: "تغيير المواعيد", roles: STAFF });

// ============================================================ Violations
route("/violations", async (page, _p, q) => {
  const reviewed = q.all ? "" : "false";
  const d = list(await api("admin/violations/", { query: { reviewed, page_size: 100 } }));
  page.innerHTML = html`<div class="page-head"><div><h1>محاولات التواصل خارج المنصة</h1><p>رسائل فيها أرقام أو لينكات أو كلمات زي واتساب. اتخفت عن الطرف التاني تلقائياً.</p></div>
    <a class="btn ghost" href="#/violations${q.all ? "" : "?all=1"}">${q.all ? "اللي لسه متراجعتش" : "عرض الكل"}</a></div>
    ${d.length ? html`<div class="stack">${d.map(v => html`<div class="panel"><div class="row between"><div class="row">${avatar(v.user)}<div><b>${v.user.full_name}</b> <span class="badge">${ROLE_AR[v.user.role]}</span>
      <div class="small muted">${fmt.full(v.created_at)} · ${v.reasons.join("، ")}</div></div></div>${v.reviewed ? html`<span class="badge b-green">اتراجعت</span>` : ""}</div>
      <div class="msg flag" style="max-width:none;margin-top:12px">${v.original_text}<div class="orig">وصلت للطرف التاني كده: ${v.message.text}</div></div>
      ${v.reviewed ? (v.action_taken ? html`<p class="small">الإجراء: ${v.action_taken}</p>` : "") : html`<form class="row wrap" data-v="${v.id}" style="margin-top:12px"><input class="input" name="action_taken" placeholder="الإجراء (تنبيه، خصم، إيقاف…)" style="flex:1">
        <button class="btn">تمت المراجعة</button><a class="btn ghost" href="#/oversight?c=${v.message.conversation}">افتح المحادثة</a></form>`}</div>`)}</div>` : empty("مفيش مخالفات جديدة 👌")}`;
  page.addEventListener("submit", async e => {
    e.preventDefault(); const f = e.target.closest("[data-v]");
    await api(`admin/violations/${f.dataset.v}/`, { method: "PATCH", body: { reviewed: true, action_taken: f.action_taken.value } }); toast("اتسجلت المراجعة", "good"); location.reload();
  });
}, { title: "المخالفات", roles: STAFF });

// ============================================================ Teacher hours report
route("/reports", async (page, _p, q) => {
  const month = q.month || new Date().toISOString().slice(0, 7);
  const d = await api("admin/reports/teacher-hours/", { query: { month } });
  const tot = d.rows.reduce((a, r) => a + r.paid_hours, 0);
  page.innerHTML = html`<div class="page-head"><div><h1>ساعات المدرسين</h1><p>الحصص اللي تمت + غياب الطالب بتتحسب للمدرس. الإجمالي ${fmt.num(tot.toFixed(1))} ساعة.</p></div>
    <input class="input" type="month" id="m" value="${month}" style="width:auto"></div>
    ${d.rows.length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>المدرس</th><th>تمت</th><th>غياب طالب</th><th>غياب مدرس</th><th>ملغاة</th><th>ساعات مستحقة</th></tr></thead><tbody>
      ${d.rows.map(r => html`<tr><td><b>${r.teacher__full_name}</b></td><td>${r.completed}</td><td>${r.student_absent}</td><td>${r.teacher_absent ? html`<span class="badge b-red">${r.teacher_absent}</span>` : 0}</td>
        <td>${r.cancelled}</td><td><b>${r.paid_hours}</b></td></tr>`)}</tbody></table></div>` : empty("مفيش حصص في الشهر ده")}`;
  $("#m").onchange = e => go(`/reports?month=${e.target.value}`);
}, { title: "ساعات المدرسين", roles: STAFF });

// ============================================================ Orders
route("/orders", async (page, _p, q) => {
  const d = await api("payments/orders/", { query: { status: q.status, page_size: 100 } });
  const rows = list(d);
  page.innerHTML = html`<div class="page-head"><div><h1>الطلبات والمدفوعات</h1><p>${fmt.num(d.count)} طلب</p></div>
    <select class="input" id="st" style="width:auto"><option value="">كل الحالات</option>${["pending", "paid", "failed", "refunded"].map(s => html`<option value="${s}" ${q.status === s ? "selected" : ""}>${badge(s).s.replace(/<[^>]+>/g, "")}</option>`)}</select></div>
    <div class="table-wrap"><table class="t"><thead><tr><th>#</th><th>الطلب</th><th>النوع</th><th>المبلغ</th><th>الطريقة</th><th>الحالة</th><th>التاريخ</th><th></th></tr></thead><tbody>
      ${rows.map(o => html`<tr><td>${o.id}</td><td>${o.title}</td><td>${o.kind === "course" ? "كورس" : "اشتراك"}</td><td><b>${fmt.money(o.total, o.currency)}</b>${Number(o.discount) ? html`<div class="small muted">خصم ${fmt.money(o.discount)}</div>` : ""}</td>
        <td>${{ paymob: "أونلاين", manual: "يدوي", free: "مجاني" }[o.method]}</td><td>${badge(o.status)}</td><td class="small">${fmt.full(o.paid_at || o.created_at)}</td>
        <td>${o.status === "pending" && state.user.role === "admin" ? html`<button class="btn sm" data-paid="${o.id}">تأكيد دفع يدوي</button>` : ""}</td></tr>`)}</tbody></table></div>`;
  $("#st").onchange = e => go(`/orders?status=${e.target.value}`);
  page.addEventListener("click", async e => {
    const b = e.target.closest("[data-paid]");
    if (b && await confirmBox("تأكيد إن الطلب ده اتدفع؟ هيتفعل الاشتراك/الكورس.", "تأكيد")) busy(b, async () => { await api(`payments/orders/${b.dataset.paid}/mark-paid/`, { method: "POST" }); location.reload(); });
  });
}, { title: "الطلبات", roles: STAFF });

// ============================================================ Coupons
route("/coupons", async page => {
  const d = list(await api("admin/coupons/"));
  page.innerHTML = html`<div class="page-head"><div><h1>أكواد الخصم</h1></div><button class="btn" id="new">كود جديد</button></div>
    <div class="table-wrap"><table class="t"><thead><tr><th>الكود</th><th>الخصم</th><th>على</th><th>الاستخدام</th><th>الحالة</th><th></th></tr></thead><tbody>
      ${d.map(c => html`<tr><td><span class="code">${c.code}</span></td><td>${c.percent_off ? `${c.percent_off}٪` : fmt.money(c.amount_off)}</td>
        <td>${{ all: "الكل", subscription: "الاشتراكات", course: "الكورسات" }[c.applies_to]}</td><td>${c.used_count}${c.max_uses ? ` / ${c.max_uses}` : ""}</td>
        <td>${c.is_active ? html`<span class="badge b-green">شغال</span>` : html`<span class="badge">متوقف</span>`}</td>
        <td><button class="btn ghost sm" data-toggle="${c.id}" data-on="${c.is_active}">${c.is_active ? "إيقاف" : "تشغيل"}</button></td></tr>`)}</tbody></table></div>`;
  page.addEventListener("click", async e => {
    const b = e.target.closest("[data-toggle]");
    if (b) { await api(`admin/coupons/${b.dataset.toggle}/`, { method: "PATCH", body: { is_active: b.dataset.on !== "true" } }); location.reload(); }
  });
  $("#new").onclick = () => modal("كود خصم جديد", html`<form class="stack"><div class="form-grid">
    <div class="field"><label>الكود</label><input class="input" name="code" dir="ltr" required></div>
    <div class="field"><label>نسبة الخصم ٪</label><input class="input" type="number" name="percent_off" min="1" max="100"></div>
    <div class="field"><label>أو مبلغ ثابت</label><input class="input" type="number" name="amount_off"></div>
    <div class="field"><label>على</label><select class="input" name="applies_to"><option value="all">الكل</option><option value="subscription">الاشتراكات</option><option value="course">الكورسات</option></select></div>
    <div class="field"><label>أقصى عدد استخدام</label><input class="input" type="number" name="max_uses"></div></div><button class="btn">إنشاء</button></form>`, {
    onMount: (m, close) => m.querySelector("form").addEventListener("submit", async e => {
      e.preventDefault(); const f = Object.fromEntries(Object.entries(formData(e.target)).filter(([, v]) => v !== ""));
      try { await api("admin/coupons/", { method: "POST", body: f }); close(); location.reload(); } catch (err) { showErrors(e.target, err); }
    }),
  });
}, { title: "أكواد الخصم", roles: ADMIN });

// ============================================================ Course review


void raw;
