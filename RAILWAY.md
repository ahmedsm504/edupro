# رفع EduPro على Railway

المشروع جاهز لـ Railway: فيه `Dockerfile` و `railway.json` (السيرفر) و `railway.cron.json` (المهام كل 5 دقايق).
لما المشروع يشتغل على Railway بيظبط لوحده: `DEBUG=False`، والدومين في `ALLOWED_HOSTS` و `CSRF_TRUSTED_ORIGINS` و `SITE_URL`،
وملفات CSS/JS بتتقدّم بـ whitenoise، وصور `/media/` بتتقدّم من Django، والـ migrations بتتعمل قبل كل نشر.

## 1) ارفع الكود على GitHub (repo خاص)

```bash
cd edupro
git init
git add .
git commit -m "EduPro"
git branch -M main
git remote add origin https://github.com/<اسمك>/edupro.git
git push -u origin main
```
`.gitignore` بيمنع رفع قاعدة البيانات المحلية والصور والفيديوهات و `.env`.

## 2) اعمل المشروع على Railway

1. **New Project → Deploy from GitHub repo** واختار الـ repo. هيبني من الـ `Dockerfile` لوحده.
2. في نفس المشروع: **+ New → Database → PostgreSQL**، وبعدها **+ New → Database → Redis**.
3. افتح خدمة السيرفر (اسمها زي الـ repo) ← **Variables** وضيف:

| المتغير | القيمة |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `SECRET_KEY` | نص عشوائي طويل (50 حرف أو أكتر) |
| `MEDIA_ROOT` | `/data/media` |
| `PRIVATE_MEDIA_ROOT` | `/data/private` |
| `SITE_NAME` | اسم المنصة (اختياري) |

4. **Volume** (عشان الصور والفيديوهات المرفوعة ما تتمسحش مع كل نشر): كليك يمين على خدمة السيرفر ← **Attach Volume** ← Mount path = `/data`.
5. **Settings → Networking → Generate Domain** ← هياخد دومين زي `edupro-production.up.railway.app`.
6. استنى النشر يخلص (الـ healthcheck على `/api/v1/health/` لازم يبقى أخضر).

## 3) أول حساب أدمن

نزّل Railway CLI مرة واحدة:
```bash
npm i -g @railway/cli
railway login
railway link          # اختار المشروع وخدمة السيرفر
railway ssh           # بيفتح terminal جوه السيرفر
python manage.py createsuperuser
```
للتجربة بس (بيمسح كل البيانات!): `python manage.py seed_demo --reset` جوه نفس الـ `railway ssh`.

## 4) خدمة المهام كل 5 دقايق (تذكير الحصص وإنهاء الاشتراكات)

1. **+ New → GitHub Repo** ← نفس الـ repo مرة تانية.
2. في الخدمة الجديدة ← **Settings** ← خانة ملف الإعدادات (Config-as-code / Railway config file) ← اكتب `railway.cron.json`.
   (لو مش لاقيها: حط Start Command = `python manage.py tutoring_cron` و Cron Schedule = `*/5 * * * *` وشيل الـ Healthcheck Path.)
3. **Variables**: نفس `DATABASE_URL` و `REDIS_URL` و `SECRET_KEY` بتوع السيرفر. مش محتاجة Volume ولا دومين.

## 5) دومين خاص بيك (اختياري)

**Settings → Networking → Custom Domain** وضيف الـ CNAME اللي Railway بيديهولك عند شركة الدومين.
بعدها ضيف المتغير `SITE_URL=https://دومينك.com` (الدومين بيتضاف لوحده لـ ALLOWED_HOSTS و CSRF).

## 6) قبل ما تفتح للطلاب

| الحاجة | المتغيرات |
|---|---|
| الحصص اللايف (من غير قفل الـ 5 دقايق) | `JITSI_JAAS_APP_ID` + `JITSI_JAAS_KID` + `JITSI_JAAS_PRIVATE_KEY` (نص المفتاح نفسه، والسطور بـ `\n`) |
| الدفع | `PAYMOB_SECRET_KEY` + `PAYMOB_PUBLIC_KEY` + `PAYMOB_HMAC_SECRET` + `PAYMOB_INTEGRATION_IDS`، وفي لوحة Paymob: callback = `https://دومينك/api/v1/payments/paymob/webhook/` |
| إشعارات الموبايل | `FCM_PROJECT_ID` + `FCM_SERVICE_ACCOUNT_JSON` (محتوى ملف الـ JSON كله) |
| التطبيق | `CORS_ALLOWED_ORIGINS` (لو Flutter Web على دومين تاني)، `APP_MIN_VERSION_*`، روابط المتاجر، `ANDROID_PACKAGE` و `ANDROID_SHA256_FINGERPRINTS` و `IOS_APP_ID` للـ deep links |

## ملاحظات

- **الفيديوهات المرفوعة** بتتخزن على الـ Volume، ومساحته محدودة حسب باقتك على Railway. لو هيبقى فيه فيديوهات كتير،
  الأوفر إن المدرسين يستخدموا روابط يوتيوب «غير مدرجة» أو Bunny Stream، والرفع المباشر يفضل للفيديوهات القليلة.
- **Backup**: Railway بيعمل backups لقاعدة البيانات والـ Volume حسب الباقة — فعّلها من إعدادات كل واحد.
- **اللوج**: من تبويب **Deployments → View Logs** في خدمة السيرفر.
- كل `git push` على `main` بينشر نسخة جديدة لوحده، والـ migrations بتتعمل قبل ما النسخة الجديدة تشتغل.
