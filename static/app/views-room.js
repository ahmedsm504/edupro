// ================= غرفة الحصة اللايف جوه الموقع (Jitsi مدمج) =================
// قبل الميعاد: صالة انتظار فيها عداد + اختبار كاميرا ومايك + واجب الحصة اللي فاتت
// وقت الحصة: الفيديو جوه الصفحة + ساعة الحصة + حالة الطرف التاني + ملاحظات المدرس (بتتنقل للتقرير)
// بعد الحصة: المدرس يكتب التقرير، والطالب يقيّم الحصة
import { $, $$, api, avatar, busy, confirmBox, fail, fmt, go, html, ico, onEvent, route, state, toast } from "./core.js";

const me = () => state.user;
const notesKey = id => `ep_room_notes_${id}`;
const lsGet = k => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch {} };
const two = n => String(Math.max(0, Math.floor(n))).padStart(2, "0");
const ISSUES = [["audio", "الصوت"], ["video", "الصورة"], ["connection", "النت/الاتصال"], ["late", "المدرس اتأخر"], ["unclear", "الشرح مش واضح"], ["short", "الحصة اتقصرت"]];

function loadScript(src) {
  return new Promise((res, rej) => {
    if (window.JitsiMeetExternalAPI) return res();
    const s = document.createElement("script"); s.src = src; s.async = true;
    s.onload = () => res(); s.onerror = () => rej(new Error("مقدرناش نحمّل الفيديو — اتأكد من النت"));
    document.head.append(s);
  });
}

route("/room/:id", async (page, { id }) => {
  let s, offset = 0, jitsi = null, join = null, tick = null, media = null, audioCtx = null, inCall = false, otherHere = false;
  const now = () => Date.now() + offset;
  const disposeMedia = () => { media?.getTracks().forEach(t => t.stop()); media = null; try { audioCtx?.close(); } catch {} audioCtx = null; };
  const disposeCall = () => { try { jitsi?.dispose(); } catch {} jitsi = null; inCall = false; };
  const cleanup = () => { clearInterval(tick); disposeMedia(); disposeCall(); offWs?.(); document.body.classList.remove("in-room"); };

  const load = async () => {
    s = await api(`sessions/${id}/`);
    offset = Date.parse(s.server_time) - Date.now();
  };
  await load();
  const u = me();
  const isTeacher = u.id === s.teacher.id, isStudent = u.id === s.student.id;
  const other = isTeacher ? s.student : s.teacher;
  otherHere = isTeacher ? !!s.student_joined_at : !!s.teacher_joined_at;

  const head = () => html`<div class="crumbs"><a href="#/sessions">${isTeacher ? "جدولي" : "حصصي"}</a>${ico("arrowNext", 14)}<a href="#/sessions/${s.id}">${s.subject.name}</a>${ico("arrowNext", 14)}<span>غرفة الحصة</span></div>`;

  function render() {
    clearInterval(tick);
    if (["cancelled", "student_absent", "teacher_absent"].includes(s.status)) return renderClosed();
    if (s.status === "completed") return renderEnded();
    if (inCall) return;
    renderLobby();
  }

  // ---------------- Lobby ----------------
  function renderLobby() {
    const opens = Date.parse(s.join_opens_at), starts = Date.parse(s.scheduled_at);
    page.innerHTML = html`${head()}
      <div class="room"><div class="room-stage"><div class="lobby"><div class="inner">
        <div class="row" style="justify-content:center;gap:14px;margin-bottom:14px">${avatar(other, "lg")}<div style="text-align:start"><div class="small" style="color:#AFC9C2">${isTeacher ? "الطالب" : "المدرس"}</div>
          <b style="font-size:18px;color:#fff">${other.full_name}</b><div><span class="presence ${otherHere ? "on" : ""}" id="pres" style="color:${otherHere ? "#8BE0BE" : "#AFC9C2"}"><i></i><span>${otherHere ? "دخل الغرفة" : "لسه مدخلش"}</span></span></div></div></div>
        <h2>${s.subject.name}${s.title ? ` — ${s.title}` : ""}</h2>
        <p>${fmt.date(s.scheduled_at)} · ${fmt.time(s.scheduled_at)} إلى ${fmt.time(s.ends_at)} · ${fmt.num(s.duration)} دقيقة</p>
        <div id="cd"></div>
        <div class="selftest" id="selftest"><video id="selfv" muted playsinline autoplay></video><div><b style="color:#fff">اختبر الكاميرا والمايك قبل ما تدخل</b>
          <ul id="checks" style="margin-top:8px"><li>${ico("camera", 16)} الكاميرا: لسه متجربتش</li><li>${ico("mic", 16)} المايك: لسه متجربش</li></ul>
          <div class="meter"><i id="lvl"></i></div>
          <button class="btn ghost sm" id="test" style="margin-top:10px;background:transparent;color:#fff;border-color:rgba(255,255,255,.3)">${ico("camera", 15)} جرّب دلوقتي</button></div></div>
        <div class="row" style="justify-content:center"><button class="btn now lg" id="join" disabled>${ico("video")} ادخل الحصة</button></div>
        <p class="small" id="jhint" style="margin-top:10px"></p>
      </div></div></div>
      <aside class="room-side">${sidePanels(false)}</aside></div>`;
    wireSide();
    const cd = $("#cd", page), btn = $("#join", page), hint = $("#jhint", page);
    const upd = () => {
      const t = now();
      const left = (starts - t) / 1000;
      if (t < opens) {
        btn.disabled = true;
        hint.textContent = `زرار الدخول هيشتغل قبل الميعاد بـ ${fmt.num(state.config?.session_join_early_minutes || 10)} دقايق.`;
      } else {
        btn.disabled = false;
        hint.textContent = s.status === "live" ? (isTeacher ? "الحصة شغالة — ادخل." : "المدرس فتح الحصة وفي انتظارك 👋") : isTeacher ? "إنت اللي هتفتح الحصة — الطالب هيوصله إشعار." : "تقدر تدخل دلوقتي، والمدرس هيفتح الحصة.";
      }
      cd.innerHTML = left > 0 ? html`<div class="countdown" aria-live="polite">
          ${left >= 86400 ? html`<div><b>${fmt.num(Math.floor(left / 86400))}</b><span>يوم</span></div>` : ""}
          <div><b>${two((left % 86400) / 3600)}</b><span>ساعة</span></div><div><b>${two((left % 3600) / 60)}</b><span>دقيقة</span></div><div><b>${two(left % 60)}</b><span>ثانية</span></div></div>`.s
        : html`<div class="countdown"><div style="min-width:auto;padding:10px 18px"><b style="font-size:20px">${s.status === "live" ? "الحصة شغالة دلوقتي" : "ميعاد الحصة جه"}</b></div></div>`.s;
    };
    upd(); tick = setInterval(upd, 1000);
    btn.onclick = () => busy(btn, enterCall);
    $("#test", page).onclick = selfTest;
  }

  async function selfTest() {
    const checks = $("#checks", page);
    try {
      disposeMedia();
      media = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      $("#selfv", page).srcObject = media;
      const AC = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AC(); const an = audioCtx.createAnalyser(); an.fftSize = 512;
      audioCtx.createMediaStreamSource(media).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount); let heard = false;
      const loop = () => {
        if (!audioCtx || !$("#lvl", page)) return;
        an.getByteTimeDomainData(buf);
        let peak = 0; for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
        $("#lvl", page).style.width = Math.min(100, peak * 1.6) + "%";
        if (peak > 12 && !heard) { heard = true; checks.children[1].className = "ok"; checks.children[1].innerHTML = `${ico("check", 16).s} المايك شغال — سامعينك`; }
        requestAnimationFrame(loop);
      };
      loop();
      checks.children[0].className = "ok"; checks.children[0].innerHTML = `${ico("check", 16).s} الكاميرا شغالة`;
      checks.children[1].innerHTML = `${ico("mic", 16).s} اتكلم عشان نجرب المايك…`;
    } catch (e) {
      checks.children[0].className = "bad";
      checks.children[0].innerHTML = `${ico("x", 16).s} ${e.name === "NotAllowedError" ? "المتصفح مانع الكاميرا/المايك — اسمح بيهم من علامة القفل جنب العنوان" : "مفيش كاميرا أو مايك متوصلين"}`;
    }
  }

  // ---------------- In call ----------------
  async function enterCall() {
    join = await api(`sessions/${id}/join/`, { method: "POST" });
    disposeMedia();
    await load();
    inCall = true;
    document.body.classList.add("in-room");
    page.innerHTML = html`${head()}
      <div class="room-bar"><div class="rt"><b>${s.subject.name}</b> <span class="muted">مع ${other.full_name}</span>
          <div><span class="presence ${otherHere ? "on" : ""}" id="pres"><i></i><span>${otherHere ? `${isTeacher ? "الطالب" : "المدرس"} في الغرفة` : `مستنيين ${isTeacher ? "الطالب" : "المدرس"}…`}</span></span></div></div>
        <span class="clock" id="clock" title="وقت الحصة">${ico("clock", 16)}<span id="clk">--:--</span></span>
        <button class="btn ghost icon" id="fs" aria-label="ملء الشاشة" title="ملء الشاشة">${ico("fullscreen")}</button>
        <a class="btn ghost" href="${join.url}" target="_blank" rel="noopener" title="لو الفيديو مش شغال هنا">${ico("external", 16)} تاب جديد</a>
        ${isTeacher ? html`<button class="btn solid-danger" id="endbtn">${ico("phoneOff", 16)} إنهاء الحصة</button>` : html`<button class="btn danger" id="leave">${ico("logout", 16)} خروج</button>`}</div>
      ${join.provider === "jitsi_public" ? html`<div class="callout warn" style="margin-bottom:12px">${ico("info")}<div>ده سيرفر التجربة العام (meet.jit.si): الحصة المدمجة بتقفل بعد 5 دقايق وممكن يطلب منك تسجيل دخول. في التشغيل الفعلي بنفعّل JaaS أو سيرفر خاص ومش هيبقى فيه الكلام ده.</div></div>` : ""}
      <div class="room"><div class="room-stage" id="jitsi"><div class="lobby"><div><div class="spinner" style="border-color:rgba(255,255,255,.2);border-top-color:var(--chalk)"></div><p>بنوصلك بالحصة…</p></div></div></div>
        <aside class="room-side">${sidePanels(true)}</aside></div>`;
    wireSide();
    $("#fs", page).onclick = () => $("#jitsi", page).requestFullscreen?.();
    $("#endbtn", page)?.addEventListener("click", e => endSession(e.target));
    $("#leave", page)?.addEventListener("click", () => { disposeCall(); document.body.classList.remove("in-room"); renderLeft(); });
    clockLoop();
    try {
      await loadScript(join.external_api_url);
      const box = $("#jitsi", page); box.innerHTML = "";
      jitsi = new window.JitsiMeetExternalAPI(join.domain, {
        roomName: join.room, parentNode: box, jwt: join.jwt || undefined, width: "100%", height: "100%", lang: "ar",
        userInfo: { displayName: join.display_name, email: me().email || undefined },
        configOverwrite: { ...join.config_overrides, prejoinPageEnabled: false, prejoinConfig: { enabled: false }, disableDeepLinking: true },
        interfaceConfigOverwrite: { SHOW_JITSI_WATERMARK: false, SHOW_WATERMARK_FOR_GUESTS: false, MOBILE_APP_PROMO: false, SHOW_CHROME_EXTENSION_BANNER: false },
      });
      jitsi.addListener("participantJoined", () => setPresence(true));
      jitsi.addListener("participantLeft", () => setPresence(false));
      jitsi.addListener("readyToClose", () => { disposeCall(); document.body.classList.remove("in-room"); s.status === "completed" ? renderEnded() : renderLeft(); });
    } catch (e) {
      $("#jitsi", page).innerHTML = html`<div class="lobby"><div class="inner"><h2>الفيديو مش راضي يفتح هنا</h2><p>${e.message}</p>
        <a class="btn now lg" href="${join.url}" target="_blank" rel="noopener">${ico("external")} افتح الحصة في تاب جديد</a></div></div>`.s;
    }
  }

  function clockLoop() {
    const startT = Date.parse(s.started_at || s.scheduled_at), endT = Date.parse(s.ends_at);
    const upd = () => {
      const el = $("#clk", page); if (!el) return;
      const t = now(), left = (endT - t) / 1000, gone = Math.max(0, (t - startT) / 1000);
      const clock = $("#clock", page);
      clock.classList.toggle("warn", left > 0 && left <= 300);
      clock.classList.toggle("over", left <= 0);
      el.textContent = left > 0 ? `${two(gone / 60)}:${two(gone % 60)} · فاضل ${fmt.num(Math.ceil(left / 60))} د` : `الوقت خلص +${fmt.num(Math.ceil(-left / 60))} د`;
    };
    upd(); tick = setInterval(upd, 1000);
  }

  function setPresence(on) {
    otherHere = on;
    const p = $("#pres", page); if (!p) return;
    p.classList.toggle("on", on);
    p.querySelector("span").textContent = inCall ? (on ? `${isTeacher ? "الطالب" : "المدرس"} في الغرفة` : `${isTeacher ? "الطالب" : "المدرس"} خرج من الغرفة`) : (on ? "دخل الغرفة" : "لسه مدخلش");
    if (!inCall) p.style.color = on ? "#8BE0BE" : "#AFC9C2";
  }

  async function endSession(btn) {
    if (!(await confirmBox("تنهي الحصة للطرفين؟ بعدها هتكتب التقرير — ملاحظاتك هتتنقل فيه.", "إنهاء الحصة"))) return;
    await busy(btn, async () => {
      await api(`sessions/${id}/end/`, { method: "POST" });
      disposeCall(); document.body.classList.remove("in-room");
      toast("الحصة خلصت ✅ اكتب التقرير", "good");
      go(`/sessions/${id}?report=1`);
    });
  }

  // ---------------- Side panels ----------------
  function sidePanels(live) {
    const hw = s.previous_homework;
    const notes = isTeacher ? html`<div class="panel"><div class="panel-head" style="margin-bottom:8px"><h3 class="row" style="gap:6px">${ico("note", 17)} ملاحظاتك عن الحصة</h3><span class="small muted" id="nsaved"></span></div>
        <textarea class="input" id="rnotes" placeholder="اللي اتشرح، نقط ضعف الطالب، الواجب… بتتحفظ لوحدها وهتلاقيها في التقرير">${lsGet(notesKey(id))}</textarea></div>` : "";
    return html`${notes}
      <div class="panel"><h3 class="row" style="gap:6px;margin-bottom:8px">${ico("clipboard", 17)} واجب الحصة اللي فاتت</h3>
        ${hw ? html`<p style="margin:0">${hw.homework}</p><div class="small muted">${fmt.date(hw.date)}</div>` : html`<p class="muted small" style="margin:0">مفيش واجب متسجل.</p>`}</div>
      ${!live ? html`<div class="panel"><h3 class="row" style="gap:6px;margin-bottom:8px">${ico("info", 17)} قبل ما تبدأ</h3>
        <ul class="small muted" style="margin:0;padding-inline-start:18px;line-height:1.9"><li>استخدم سماعة عشان الصوت يبقى أوضح.</li><li>اقعد في مكان هادي ونوره كويس.</li>
          <li>لو النت ضعيف اقفل الكاميرا وسيب الصوت.</li>${isStudent ? html`<li>جهّز الكشكول والواجب.</li>` : html`<li>تقدر تشارك شاشتك أو تفتح السبورة من جوه الحصة.</li>`}</ul></div>` : ""}
      <div class="panel"><div class="row" style="gap:10px">${avatar(other)}<div style="flex:1;min-width:0"><b>${other.full_name}</b><div class="small muted">${isTeacher ? "الطالب" : "المدرس"}</div></div>
        <button class="btn ghost sm" id="chat">${ico("chat", 15)} راسله</button></div></div>`;
  }
  function wireSide() {
    const t = $("#rnotes", page);
    if (t) { let timer; t.oninput = () => { clearTimeout(timer); timer = setTimeout(() => { lsSet(notesKey(id), t.value); $("#nsaved", page).textContent = "اتحفظت"; }, 500); }; }
    $("#chat", page)?.addEventListener("click", e => busy(e.target, async () => {
      const c = await api("chat/conversations/start/", { method: "POST", body: { user_id: other.id } });
      if (inCall) window.open(`/app/#/chat?c=${c.id}`, "_blank"); else go(`/chat?c=${c.id}`);
    }));
  }

  // ---------------- After ----------------
  function renderLeft() {
    page.innerHTML = html`${head()}<div class="panel" style="text-align:center;padding:40px 20px"><div class="empty" style="padding:0">
      <div class="ei">${ico("logout", 26)}</div><b>خرجت من الحصة</b><p>الحصة لسه شغالة — تقدر ترجع في أي وقت لحد ما المدرس ينهيها.</p></div>
      <div class="row" style="justify-content:center"><button class="btn now lg" id="back">${ico("video")} ارجع للحصة</button><a class="btn ghost lg" href="#/sessions">${ico("calendar")} حصصي</a></div></div>`;
    $("#back", page).onclick = e => busy(e.target, enterCall);
  }

  function renderClosed() {
    page.innerHTML = html`${head()}<div class="panel">${html`<div class="empty"><div class="ei">${ico("x", 26)}</div><b>الحصة دي ${s.status === "cancelled" ? "اتلغت" : "اتسجل فيها غياب"}</b>
      ${s.cancel_reason ? html`<p>${s.cancel_reason}</p>` : ""}<p><a class="btn ghost" href="#/sessions/${s.id}">تفاصيل الحصة</a></p></div>`}</div>`;
  }

  function renderEnded() {
    const fb = s.feedback;
    let rating = fb?.rating || 0;
    page.innerHTML = html`${head()}<div class="panel" style="max-width:640px;margin:0 auto;text-align:center;padding:32px 24px">
      <div class="ei" style="width:64px;height:64px;border-radius:50%;background:var(--green-soft);color:var(--green-2);display:grid;place-items:center;margin:0 auto 12px">${ico("checkCircle", 32)}</div>
      <h2>الحصة خلصت</h2><p class="muted">${s.subject.name} مع ${other.full_name} · ${fmt.time(s.started_at)} إلى ${fmt.time(s.ended_at)}</p>
      ${isTeacher ? html`<a class="btn lg" href="#/sessions/${s.id}?report=1">${ico("pen")} ${s.has_report ? "شوف التقرير" : "اكتب تقرير الحصة"}</a>` : ""}
      ${isStudent ? html`<div class="sep"></div><h3 style="margin-bottom:10px">${fb ? "شكراً على تقييمك 🙏" : "إيه رأيك في الحصة؟"}</h3>
        <form id="fb" class="stack lg"><div class="stars-in" role="radiogroup" aria-label="التقييم">${[1, 2, 3, 4, 5].map(n => html`<button type="button" data-r="${n}" class="${n <= rating ? "on" : ""}" aria-label="${n} من 5">${ico("star", 34)}</button>`)}</div>
          <div class="chipset">${ISSUES.map(([k, l]) => html`<label><input type="checkbox" name="issues" value="${k}" ${fb?.issues?.includes(k) ? "checked" : ""}>${l}</label>`)}</div>
          <textarea class="input" name="comment" placeholder="أي حاجة تحب تقولها؟ (اختياري — بتوصل للإدارة بس)">${fb?.comment || ""}</textarea>
          <div class="row" style="justify-content:center"><button class="btn lg">${fb ? "تحديث التقييم" : "ابعت التقييم"}</button></div></form>
        ${s.report ? html`<div class="sep"></div><a class="btn ghost" href="#/sessions/${s.id}">${ico("clipboard", 16)} تقرير المدرس جاهز — شوفه</a>` : html`<p class="small muted" style="margin-top:14px">تقرير الحصة هيوصلك إشعار بيه أول ما المدرس يكتبه.</p>`}` : ""}
      <div class="row" style="justify-content:center;margin-top:16px"><a class="btn ghost" href="#/sessions">${ico("calendar", 16)} ${isTeacher ? "جدولي" : "حصصي"}</a></div></div>`;
    const f = $("#fb", page);
    if (f) {
      f.querySelector(".stars-in").onclick = e => { const b = e.target.closest("[data-r]"); if (!b) return; rating = Number(b.dataset.r); $$(".stars-in button", f).forEach(x => x.classList.toggle("on", Number(x.dataset.r) <= rating)); };
      f.onsubmit = async e => {
        e.preventDefault();
        if (!rating) return toast("اختار عدد النجوم", "bad");
        await busy(e.submitter, async () => {
          await api(`sessions/${id}/feedback/`, { method: "POST", body: { rating, comment: f.comment.value, issues: $$("input[name=issues]:checked", f).map(x => x.value) } });
          toast("شكراً! تقييمك وصل 🙏", "good"); await load(); renderEnded();
        });
      };
    }
  }

  // ---------------- realtime ----------------
  const offWs = onEvent(async (ev, d) => {
    if (String(d?.session_id) !== String(id)) return;
    if (ev === "session.presence") { setPresence(true); if (!inCall && d.who === "teacher") { await load(); toast("المدرس فتح الحصة — ادخل دلوقتي 👋", "good"); renderLobby(); } }
    if (ev === "session.updated") {
      await load();
      if (s.status === "completed" && inCall && isStudent) { disposeCall(); document.body.classList.remove("in-room"); toast("المدرس أنهى الحصة"); renderEnded(); }
      else if (!inCall) render();
    }
  });

  render();
  return cleanup;
}, { title: "غرفة الحصة" });

void fail;
