#!/bin/sh
# تشغيل السيرفر. لو RUN_CRON=1 (الافتراضي) بنشغّل مهام الحصص كل 5 دقايق في الخلفية في نفس الحاوية
# (تذكير الحصص، إنهاء الاشتراكات، توليد الحصص) — كده مش محتاج خدمة cron منفصلة على Railway.
if [ "${RUN_CRON:-1}" = "1" ]; then
  ( while true; do python manage.py tutoring_cron || true; sleep 300; done ) &
fi
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
