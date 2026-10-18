#!/bin/sh
# تشغيل السيرفر. لو RUN_CRON=1 (الافتراضي) بنشغّل مهام الحصص كل 5 دقايق في الخلفية في نفس الحاوية
# (تذكير الحصص، إنهاء الاشتراكات، توليد الحصص) — كده مش محتاج خدمة cron منفصلة على Railway.
# الـ migrations قبل ما السيرفر يشتغل (آمنة لو اتعملت قبل كده — بتعدّي اللي اتطبق)
python manage.py migrate --noinput
python manage.py ensure_admin || true
python manage.py seed_showcase --if-empty || true
python manage.py sync_curricula || true

if [ "${RUN_CRON:-1}" = "1" ]; then
  ( while true; do python manage.py tutoring_cron || true; sleep 300; done ) &
fi
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
