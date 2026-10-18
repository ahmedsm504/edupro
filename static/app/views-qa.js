import { $, $$, api, avatar, busy, confirmBox, empty, fmt, formData, go, html, list, raw, route, showErrors, state, toast } from "./core.js";

const me = () => state.user;
const isStaff = () => ["admin", "supervisor"].includes(me().role);

// ============================================================ Q&A list
route("/qa", async (page, _p, q) => {
  const def = me().role === "teacher" ? "for_me" : "latest";
  const tab = q.tab || def;
  const subjects = await api("subjects/");
  const query = { page_size: 30, subject: q.subject, search: q.search };
  if (tab !== "latest") query.tab = tab;
  const d = await api("qa/questions/", { query });
  const T = (k, l) => html`<button class="${tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`;
  page.innerHTML = html`<div class="page-head"><div><h1>الأسئلة والأجوبة</h1>
      <p>${me().role === "teacher" ? "جاوب على أسئلة الطلاب في موادك — إجاباتك بتظهر في جوجل وعلى بروفايلك." : "اسأل أي سؤال والمدرسين المتخصصين يردوا عليك."}</p></div>
    <div class="row wrap"><a class="btn ghost" href="/questions/" target="_blank">الصفحة العامة</a><a class="btn" href="#/qa/ask">اسأل سؤال</a></div></div>
    <div class="tabs">${me().role === "teacher" ? T("for_me", "أسئلة في موادي") : ""}${T("latest", "الأحدث")}${T("unanswered", "من غير إجابة")}${T("popular", "الأكثر تصويتاً")}${T("mine", "أسئلتي")}</div>
    <form id="f" class="row wrap" style="margin-bottom:14px"><select class="input" name="subject" style="width:auto"><option value="">كل المواد</option>
      ${subjects.map(s => html`<option value="${s.id}" ${String(q.subject) === String(s.id) ? "selected" : ""}>${s.name}</option>`)}</select>
      <input class="input" name="search" value="${q.search || ""}" placeholder="ابحث في الأسئلة" style="width:220px"><button class="btn ghost">بحث</button></form>
    ${list(d).length ? html`<div class="panel" style="padding:0">${list(d).map(qRow)}</div>` : empty(tab === "for_me" ? "مفيش أسئلة جديدة في موادك 🎉" : "مفيش أسئلة هنا", raw('<p><a class="btn" href="#/qa/ask">اسأل سؤال</a></p>'))}`;
  page.querySelector(".tabs").onclick = e => { const t = e.target.dataset.tab; if (t) go(`/qa?tab=${t}`); };
  $("#f").addEventListener("submit", e => { e.preventDefault(); const f = formData(e.target); go(`/qa?tab=${tab}&subject=${f.subject}&search=${encodeURIComponent(f.search)}`); });
}, { title: "الأسئلة والأجوبة" });

const qRow = x => html`<a class="qa-row" href="#/qa/${x.slug}">
  <div class="qa-stats"><div><b>${x.score}</b>تصويت</div><div class="${x.has_accepted_answer ? "ok" : x.answers_count ? "has" : ""}"><b>${x.answers_count}</b>${x.has_accepted_answer ? "✓ إجابة" : "إجابة"}</div></div>
  <div style="min-width:0"><b dir="auto">${x.title}</b>${x.excerpt ? html`<div class="small muted" dir="auto">${x.excerpt}</div>` : ""}
    <div class="row wrap small muted" style="margin-top:4px"><span class="tag">${x.subject.name}</span><span>${x.author.full_name}</span><span>${fmt.ago(x.created_at)}</span>
    ${x.moderation === "pending" ? html`<span class="badge b-yellow">مستني مراجعة</span>` : ""}${x.moderation === "rejected" ? html`<span class="badge b-red">مرفوض</span>` : ""}</div></div></a>`;

// ============================================================ Ask
route("/qa/ask", async (page, _p, q) => {
  const subjects = await api("subjects/");
  const mySubject = me().profile?.grade ? null : null;
  void mySubject;
  page.innerHTML = html`<div class="page-head"><div><h1>اسأل سؤال</h1><p>كل ما سؤالك يكون أوضح، الإجابة هتيجي أسرع وأحسن.</p></div></div>
    <div class="cols"><form class="panel stack" id="ask">
      <div class="field"><label for="t">السؤال في جملة واحدة واضحة</label><input class="input" id="t" name="title" required minlength="12" maxlength="200" dir="auto" placeholder="مثلاً: إزاي أحسب المقاومة المكافئة لمقاومات على التوازي؟"></div>
      <div class="form-grid"><div class="field"><label>المادة</label><select class="input" name="subject" required>${subjects.map(s => html`<option value="${s.id}" ${String(q.subject) === String(s.id) ? "selected" : ""}>${s.name}</option>`)}</select></div>
        <div class="field"><label>وسوم (اختياري، افصل بفاصلة)</label><input class="input" name="tags" placeholder="ثانوية عامة, كهربية"></div></div>
      <div class="field"><label>التفاصيل: جربت إيه؟ ووقفت فين؟</label><textarea class="input" name="body" rows="7" dir="auto" placeholder="اكتب المسألة كاملة والخطوات اللي عملتها…"></textarea></div>
      <div class="field"><label>صورة (اختياري)</label><input type="file" name="image" accept="image/*"></div>
      <div><button class="btn lg">انشر السؤال</button></div></form>
      <aside class="panel"><h2>نصايح</h2><ul class="small" style="padding-inline-start:18px;line-height:2"><li>عنوان واضح بيجيب إجابات أسرع</li><li>اكتب المسألة كاملة مش "حد يحلها"</li>
        <li>لو فيه معادلة اكتبها أو صوّرها</li><li><b>متكتبش أرقام تليفون أو لينكات</b> — السؤال هيتوقف للمراجعة</li></ul></aside></div>`;
  $("#ask").addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    if (!fd.get("image")?.size) fd.delete("image");
    const tags = (fd.get("tags") || "").split(/[,،]/).map(x => x.trim()).filter(Boolean);
    fd.delete("tags"); tags.forEach(t => fd.append("tags", t));
    await busy(e.submitter, async () => {
      try {
        const r = await api("qa/questions/", { method: "POST", form: fd });
        toast(r.moderation === "pending" ? "السؤال فيه بيانات تواصل — هيتنشر بعد المراجعة" : "اتنشر سؤالك ✅", r.moderation === "pending" ? "bad" : "good");
        go(`/qa/${r.slug}`);
      } catch (err) { showErrors(e.target, err); }
    });
  });
}, { title: "اسأل سؤال" });

// ============================================================ Question detail
route("/qa/:slug", async (page, { slug }) => {
  const load = async () => {
    const x = await api(`qa/questions/${slug}/`);
    const mine = x.author.id === me().id;
    const voteBox = (kind, id, score, my, own) => html`<div class="vote-col">
      <button class="vbtn ${my === 1 ? "on" : ""}" data-vote="${kind}" data-id="${id}" data-v="${my === 1 ? 0 : 1}" ${own ? "disabled" : ""} aria-label="مفيد">▲</button>
      <b>${score}</b><button class="vbtn ${my === -1 ? "on" : ""}" data-vote="${kind}" data-id="${id}" data-v="${my === -1 ? 0 : -1}" ${own ? "disabled" : ""} aria-label="مش مفيد">▼</button></div>`;
    page.innerHTML = html`<div class="page-head"><div style="min-width:0"><h1 dir="auto" style="font-size:24px">${x.title}</h1>
        <p class="row wrap small"><span class="tag">${x.subject.name}</span>${x.tags.map(t => html`<span class="tag">#${t.name}</span>`)}<span>${x.author.full_name}</span><span>${fmt.full(x.created_at)}</span><span>${x.views_count} مشاهدة</span>
        ${x.moderation === "pending" ? html`<span class="badge b-yellow">مستني مراجعة — مش ظاهر للناس</span>` : ""}</p></div>
      <div class="row wrap"><a class="btn ghost" href="/questions/${x.slug}/" target="_blank">الصفحة العامة</a>
        ${mine && !x.answers_count ? html`<button class="btn danger" id="del">حذف</button>` : ""}${isStaff() ? html`<button class="btn ghost" id="close">${x.is_closed ? "فتح السؤال" : "قفل السؤال"}</button>` : ""}</div></div>
      ${isStaff() && x.flag_reasons?.length ? html`<div class="panel" style="background:var(--chalk-soft);border-color:#EED38A;margin-bottom:14px">سبب التعليق: ${x.flag_reasons.join("، ")}</div>` : ""}
      <div class="panel qa-q">${voteBox("q", x.slug, x.score, x.my_vote, mine)}<div class="qa-body">${raw(x.body_html || '<p class="muted">مفيش تفاصيل</p>')}${x.image ? html`<img src="${x.image}" alt="" style="max-width:420px;border-radius:10px">` : ""}</div></div>
      <h2 style="margin:22px 0 10px">${x.answers.length} إجابة</h2>
      <div class="stack">${x.answers.map(a => html`<div class="panel qa-q ${a.is_accepted ? "qa-accepted" : ""}" id="a${a.id}">${voteBox("a", a.id, a.score, a.my_vote, a.author.id === me().id)}
        <div class="qa-body">${a.is_accepted ? html`<span class="badge b-green" style="margin-bottom:8px">✓ أفضل إجابة</span>` : ""}
          ${a.moderation === "pending" ? html`<span class="badge b-yellow">مستني مراجعة</span>` : ""}
          ${raw(a.body_html)}${a.image ? html`<img src="${a.image}" alt="" style="max-width:420px;border-radius:10px">` : ""}
          <div class="row between wrap small" style="margin-top:10px"><div class="row">${avatar(a.author)}<div><b>${a.author.full_name}</b>${a.author.is_verified_teacher ? html` <span class="badge b-green">مدرس معتمد</span>` : ""}
            <div class="muted">${fmt.full(a.created_at)}</div></div></div>
            <div class="row">${x.can_accept && a.moderation === "approved" ? html`<button class="btn ${a.is_accepted ? "ghost" : ""} sm" data-accept="${a.id}">${a.is_accepted ? "إلغاء الاختيار" : "✓ أفضل إجابة"}</button>` : ""}
              ${a.author.id === me().id || isStaff() ? html`<button class="btn danger sm" data-del-ans="${a.id}">حذف</button>` : ""}</div></div></div></div>`)}</div>
      ${x.answers.length ? "" : empty("لسه محدش جاوب", "المدرسين المتخصصين اتبلغوا بالسؤال")}
      ${x.is_closed ? html`<div class="panel" style="margin-top:18px">السؤال ده مقفول.</div>` : html`<form class="panel stack" id="ans" style="margin-top:18px"><h2>${me().role === "teacher" ? "إجابتك كمدرس" : "إجابتك"}</h2>
        <textarea class="input" name="body" rows="6" minlength="20" required dir="auto" placeholder="اشرح الإجابة خطوة بخطوة… (المعادلات تتكتب عادي، والكود بين ثلاث علامات \`\`\`)"></textarea>
        <div class="row wrap"><input type="file" name="image" accept="image/*"><button class="btn" style="margin-inline-start:auto">انشر الإجابة</button></div></form>`}`;
    $("#ans")?.addEventListener("submit", async e => {
      e.preventDefault();
      const fd = new FormData(e.target); if (!fd.get("image")?.size) fd.delete("image");
      await busy(e.submitter, async () => {
        try { const a = await api(`qa/questions/${slug}/answers/`, { method: "POST", form: fd }); toast(a.moderation === "pending" ? "الإجابة فيها بيانات تواصل — هتتنشر بعد المراجعة" : "اتنشرت إجابتك ✅", a.moderation === "pending" ? "bad" : "good"); load(); }
        catch (err) { showErrors(e.target, err); }
      });
    });
    $("#del")?.addEventListener("click", async () => { if (await confirmBox("تحذف السؤال؟", "حذف")) { await api(`qa/questions/${slug}/`, { method: "DELETE" }); go("/qa?tab=mine"); } });
    $("#close")?.addEventListener("click", async () => { await api(`qa/questions/${slug}/close/`, { method: "POST" }); load(); });
  };
  page.addEventListener("click", async e => {
    const v = e.target.closest("[data-vote]"), ac = e.target.closest("[data-accept]"), da = e.target.closest("[data-del-ans]");
    if (v) busy(v, async () => {
      const url = v.dataset.vote === "q" ? `qa/questions/${v.dataset.id}/vote/` : `qa/answers/${v.dataset.id}/vote/`;
      await api(url, { method: "POST", body: { value: Number(v.dataset.v) } }); load();
    });
    if (ac) busy(ac, async () => { await api(`qa/answers/${ac.dataset.accept}/accept/`, { method: "POST" }); toast("تم", "good"); load(); });
    if (da && await confirmBox("تحذف الإجابة؟", "حذف")) { await api(`qa/answers/${da.dataset.delAns}/`, { method: "DELETE" }); load(); }
  });
  await load();
}, { title: "السؤال" });

// ============================================================ Moderation (staff)
route("/qa-moderation", async page => {
  const load = async () => {
    const d = await api("qa/moderation/");
    const item = (kind, o, title, text) => html`<div class="panel"><div class="row between wrap"><div class="row">${avatar(o.author)}<div><b>${o.author.full_name}</b>
        <div class="small muted">${kind === "question" ? "سؤال" : "إجابة على: " + o.question.title} · ${fmt.full(o.created_at)}</div></div></div>
        <span class="badge b-yellow">${(o.flag_reasons || []).join("، ")}</span></div>
      ${title ? html`<h3 style="margin:10px 0 4px" dir="auto">${title}</h3>` : ""}<div class="msg flag" style="max-width:none;margin-top:8px">${text}</div>
      <div class="row" style="margin-top:12px"><button class="btn sm" data-mod="${kind}" data-id="${o.id}" data-a="approve">نشر</button><button class="btn danger sm" data-mod="${kind}" data-id="${o.id}" data-a="reject">رفض</button>
        <a class="btn ghost sm" href="#/qa/${kind === "question" ? o.slug : o.question.slug}">فتح</a></div></div>`;
    page.innerHTML = html`<div class="page-head"><div><h1>مراجعة الأسئلة والأجوبة</h1><p>مشاركات فيها أرقام تليفون أو لينكات أو كلمات زي واتساب — مش ظاهرة للناس لحد ما تراجعها.</p></div></div>
      ${d.questions.length + d.answers.length ? html`<div class="stack">${d.questions.map(o => item("question", o, o.title, o.body))}${d.answers.map(o => item("answer", o, "", o.body))}</div>` : empty("مفيش حاجة مستنية مراجعة 👌")}`;
  };
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-mod]"); if (!b) return;
    busy(b, async () => { await api("qa/moderation/", { method: "POST", body: { kind: b.dataset.mod, id: Number(b.dataset.id), action: b.dataset.a } }); toast("تم", "good"); load(); });
  });
  await load();
}, { title: "مراجعة الأسئلة", roles: ["admin", "supervisor"] });

// ============================================================ Blog (teacher writes, staff publishes)
const ART_STATUS = { draft: ["مسودة", ""], pending_review: ["قيد المراجعة", "b-yellow"], published: ["منشور", "b-green"], rejected: ["محتاج تعديل", "b-red"] };
const artBadge = s => { const [t, c] = ART_STATUS[s] || [s, ""]; return html`<span class="badge ${c}">${t}</span>`; };

route("/articles", async (page, _p, q) => {
  const d = await api("blog/manage/articles/", { query: { status: q.status, page_size: 100 } });
  const T = (k, l) => html`<button class="${(q.status || "") === k ? "on" : ""}" data-s="${k}">${l}</button>`;
  page.innerHTML = html`<div class="page-head"><div><h1>${isStaff() ? "إدارة المدونة" : "مقالاتي"}</h1>
      <p>${isStaff() ? "راجع مقالات المدرسين وانشرها، أو اكتب مقال جديد." : "اكتب مقال في مادتك — بعد مراجعة الإدارة بيتنشر باسمك وبيظهر على بروفايلك وفي جوجل."}</p></div>
    <div class="row"><a class="btn ghost" href="/blog/" target="_blank">المدونة</a><a class="btn" href="#/articles/new">مقال جديد</a></div></div>
    <div class="tabs">${T("", "الكل")}${T("pending_review", "قيد المراجعة")}${T("published", "منشور")}${T("draft", "مسودة")}${T("rejected", "محتاج تعديل")}</div>
    ${list(d).length ? html`<div class="table-wrap"><table class="t"><thead><tr><th>المقال</th>${isStaff() ? html`<th>الكاتب</th>` : ""}<th>الحالة</th><th>الكلمات</th><th>القراءات</th><th>آخر تعديل</th></tr></thead><tbody>
      ${list(d).map(a => html`<tr class="click" data-id="${a.id}"><td><b>${a.title}</b></td>${isStaff() ? html`<td>${a.author?.full_name || "—"}</td>` : ""}<td>${artBadge(a.status)}</td>
        <td>${a.word_count}</td><td>${a.views_count}</td><td class="small">${fmt.full(a.updated_at)}</td></tr>`)}</tbody></table></div>` : empty("مفيش مقالات هنا", raw('<p><a class="btn" href="#/articles/new">اكتب أول مقال</a></p>'))}`;
  page.querySelector(".tabs").onclick = e => { if (e.target.dataset.s !== undefined) go(`/articles?status=${e.target.dataset.s}`); };
  page.querySelector("tbody")?.addEventListener("click", e => { const tr = e.target.closest("tr"); if (tr) go(`/articles/${tr.dataset.id}`); });
}, { title: "المدونة", roles: ["teacher", "admin", "supervisor"] });

route("/articles/:id", async (page, { id }) => {
  const isNew = id === "new";
  const [a, cats, subjects] = await Promise.all([isNew ? null : api(`blog/manage/articles/${id}/`), api("blog/categories/"), api("subjects/")]);
  const faq = a?.faq || [];
  page.innerHTML = html`<div class="page-head"><div><h1>${isNew ? "مقال جديد" : a.title}</h1>${a ? html`<p class="row wrap">${artBadge(a.status)}<span>${a.word_count} كلمة · ${a.reading_minutes} دقايق قراءة</span>
      ${a.status === "published" ? html`<a href="/blog/${a.slug}/" target="_blank">شوف المقال ↗</a>` : ""}</p>` : ""}</div>
    <div class="row wrap">${a && !isStaff() && ["draft", "rejected"].includes(a.status) ? html`<button class="btn chalk" id="submit">ابعته للمراجعة</button>` : ""}
      ${a && isStaff() && a.status !== "published" ? html`<button class="btn" data-mod="publish">نشر</button>` : ""}
      ${a && isStaff() && a.status === "pending_review" ? html`<button class="btn danger" data-mod="reject">رفض</button>` : ""}
      ${a && isStaff() && a.status === "published" ? html`<button class="btn ghost" data-mod="unpublish">إلغاء النشر</button>` : ""}</div></div>
    ${a?.rejection_reason ? html`<div class="panel" style="background:var(--red-soft);border-color:#F0C7C2;margin-bottom:14px">ملاحظات الإدارة: ${a.rejection_reason}</div>` : ""}
    <form id="art" class="cols">
      <div class="stack">
        <div class="panel stack"><div class="field"><label>العنوان (H1) — حط فيه الكلمة المفتاحية</label><input class="input" name="title" required value="${a?.title || ""}"></div>
          <div class="field"><label>المحتوى — استخدم «عنوان» للفقرات الرئيسية عشان الفهرس يتعمل تلقائي</label>
            <div class="rte-bar" role="toolbar">${[["h2", "عنوان"], ["h3", "عنوان فرعي"], ["p", "فقرة"], ["b", "عريض"], ["ul", "قائمة"], ["quote", "اقتباس"], ["link", "لينك"]].map(([k, l]) => html`<button type="button" class="btn ghost sm" data-fmt="${k}">${l}</button>`)}</div>
            <div class="rte input" id="body" contenteditable="true" dir="rtl">${raw(a?.body || "<p>اكتب المقدمة هنا…</p>")}</div>
            <div class="small muted" id="wc"></div></div>
          <div class="field"><label>الملخص (بيظهر في القوائم وجوجل لو الوصف فاضي)</label><textarea class="input" name="excerpt" rows="2" maxlength="300">${a?.excerpt || ""}</textarea></div></div>
        <div class="panel"><div class="panel-head"><h2>أسئلة شائعة (بتظهر في نتايج جوجل)</h2><button type="button" class="btn ghost sm" id="addfaq">+ سؤال</button></div><div id="faqs" class="stack">
          ${faq.map(f => faqRow(f.q, f.a))}</div></div>
      </div>
      <aside class="stack">
        <div class="panel stack"><div class="field"><label>التصنيف</label><select class="input" name="category"><option value="">—</option>${cats.map(c => html`<option value="${c.id}" ${a?.category?.id === c.id ? "selected" : ""}>${c.name}</option>`)}</select></div>
          <div class="field"><label>المادة</label><select class="input" name="subject"><option value="">—</option>${subjects.map(s => html`<option value="${s.id}" ${a?.subject?.id === s.id ? "selected" : ""}>${s.name}</option>`)}</select></div>
          <div class="field"><label>وسوم (افصل بفاصلة)</label><input class="input" name="tags" value="${(a?.tags || []).map(t => t.name).join("، ")}"></div>
          <div class="field"><label>صورة الغلاف</label><input type="file" name="cover" accept="image/*">${a?.cover ? html`<img src="${a.cover}" alt="" style="border-radius:8px;margin-top:6px">` : ""}</div>
          <div class="field"><label>وصف الصورة (alt)</label><input class="input" name="cover_alt" value="${a?.cover_alt || ""}"></div></div>
        <div class="panel stack"><h2>السيو</h2>
          <div class="field"><label>الكلمة المفتاحية</label><input class="input" name="focus_keyword" value="${a?.focus_keyword || ""}" placeholder="مثلاً: مذاكرة رياضيات ثالثة ثانوي"></div>
          <div class="field"><label>عنوان جوجل (60 حرف) <span class="muted" id="mtc"></span></label><input class="input" name="meta_title" maxlength="160" value="${a?.meta_title || ""}"></div>
          <div class="field"><label>وصف جوجل (155 حرف) <span class="muted" id="mdc"></span></label><textarea class="input" name="meta_description" rows="3" maxlength="300">${a?.meta_description || ""}</textarea></div>
          <div class="serp"><div class="serp-url">${location.host}/blog/…</div><div class="serp-t" id="st"></div><div class="serp-d" id="sd"></div></div>
          <ul class="seo-check" id="chk"></ul>
          ${isStaff() ? html`<label class="row"><input type="checkbox" name="is_featured" ${a?.is_featured ? "checked" : ""}> مقال مميز</label>` : ""}</div>
        <button class="btn lg">${isNew ? "حفظ كمسودة" : "حفظ التعديلات"}</button>
      </aside></form>`;
  const f = $("#art"), body = $("#body");
  const check = () => {
    const text = body.innerText.trim(), words = text ? text.split(/\s+/).length : 0;
    const kw = f.focus_keyword.value.trim(), title = f.title.value, mt = f.meta_title.value || title, md = f.meta_description.value || f.excerpt.value;
    $("#wc").textContent = `${words} كلمة · ${Math.max(1, Math.ceil(words / 200))} دقايق قراءة`;
    $("#mtc").textContent = `${mt.length}/60`; $("#mdc").textContent = `${md.length}/155`;
    $("#st").textContent = mt.slice(0, 62) + (mt.length > 62 ? "…" : ""); $("#sd").textContent = md.slice(0, 158) + (md.length > 158 ? "…" : "");
    const h2 = body.querySelectorAll("h2").length;
    const items = [
      [words >= 600, `طول المقال ${words} كلمة (الأفضل 600+)`],
      [!!kw && title.includes(kw), "الكلمة المفتاحية في العنوان"],
      [!!kw && text.slice(0, 300).includes(kw), "الكلمة المفتاحية في أول فقرة"],
      [h2 >= 2, `${h2} عناوين رئيسية (H2) — الأفضل 2+`],
      [md.length >= 70 && md.length <= 160, "وصف جوجل بين 70 و160 حرف"],
      [mt.length <= 60, "عنوان جوجل 60 حرف أو أقل"],
      [$$("#faqs .faq-row").length > 0, "فيه أسئلة شائعة (FAQ)"],
      [body.querySelectorAll("a").length > 0, "فيه لينك داخلي واحد على الأقل"],
    ];
    $("#chk").innerHTML = items.map(([ok, t]) => html`<li class="${ok ? "ok" : ""}">${ok ? "✓" : "○"} ${t}</li>`.s).join("");
  };
  f.addEventListener("input", check); body.addEventListener("input", check); check();
  $(".rte-bar").addEventListener("click", e => {
    const k = e.target.dataset.fmt; if (!k) return;
    body.focus();
    if (["h2", "h3", "p"].includes(k)) document.execCommand("formatBlock", false, k);
    if (k === "quote") document.execCommand("formatBlock", false, "blockquote");
    if (k === "b") document.execCommand("bold");
    if (k === "ul") document.execCommand("insertUnorderedList");
    if (k === "link") { const u = prompt("اللينك (مثلاً /subjects/math/ أو https://…)"); if (u) document.execCommand("createLink", false, u); }
    check();
  });
  $("#addfaq").onclick = () => { $("#faqs").insertAdjacentHTML("beforeend", faqRow("", "").s); check(); };
  $("#faqs").addEventListener("click", e => { if (e.target.closest("[data-rmfaq]")) { e.target.closest(".faq-row").remove(); check(); } });
  f.addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData();
    for (const k of ["title", "excerpt", "category", "subject", "cover_alt", "focus_keyword", "meta_title", "meta_description"]) fd.append(k, f[k].value);
    fd.append("body", body.innerHTML);
    if (isStaff()) fd.append("is_featured", f.is_featured.checked ? "true" : "false");
    f.tags.value.split(/[,،]/).map(x => x.trim()).filter(Boolean).forEach(t => fd.append("tag_names", t));
    if (f.cover.files[0]) fd.append("cover", f.cover.files[0]);
    await busy(e.submitter, async () => {
      try {
        // الـ FAQ JSON بيتبعت في طلب JSON منفصل بعد الحفظ
        const saved = await api(isNew ? "blog/manage/articles/" : `blog/manage/articles/${id}/`, { method: isNew ? "POST" : "PATCH", form: fd });
        const faqs = $$("#faqs .faq-row").map(r => ({ q: r.querySelector("[name=q]").value.trim(), a: r.querySelector("[name=a]").value.trim() })).filter(x => x.q && x.a);
        await api(`blog/manage/articles/${saved.id}/`, { method: "PATCH", body: { faq: faqs } });
        toast("اتحفظ ✅", "good");
        if (isNew) go(`/articles/${saved.id}`); else location.reload();
      } catch (err) { showErrors(f, err); }
    });
  });
  $("#submit")?.addEventListener("click", e => busy(e.target, async () => { await api(`blog/manage/articles/${id}/submit/`, { method: "POST" }); toast("اتبعت للمراجعة", "good"); location.reload(); }));
  page.addEventListener("click", e => {
    const b = e.target.closest("[data-mod]"); if (!b) return;
    const reason = b.dataset.mod === "reject" ? (prompt("ملاحظات للكاتب؟") ?? "") : "";
    busy(b, async () => { await api(`blog/manage/articles/${id}/moderate/`, { method: "POST", body: { action: b.dataset.mod, reason } }); toast("تم", "good"); location.reload(); });
  });
}, { title: "محرر المقال", roles: ["teacher", "admin", "supervisor"] });

const faqRow = (q, a) => html`<div class="faq-row stack" style="border:1px solid var(--line);border-radius:10px;padding:10px">
  <div class="row"><input class="input" name="q" placeholder="السؤال" value="${q}"><button type="button" class="btn danger sm" data-rmfaq>×</button></div>
  <textarea class="input" name="a" rows="2" placeholder="الإجابة">${a}</textarea></div>`;
