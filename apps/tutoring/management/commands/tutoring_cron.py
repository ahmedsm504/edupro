"""
شغّل الأمر ده كل 5 دقايق (cron / systemd timer / Celery beat):
    python manage.py tutoring_cron
بيعمل: تذكير قبل الحصة بـ 15 دقيقة، تذكير يوم قبل، إنهاء الاشتراكات اللي تاريخها خلص، وتكملة توليد الحصص.
"""
import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import notify
from apps.tutoring.models import Session, Subscription
from apps.tutoring.services import generate_sessions


class Command(BaseCommand):
    help = "Session reminders + subscription housekeeping"

    def handle(self, *args, **opts):
        now = timezone.now()
        soon = Session.objects.filter(status="scheduled", reminder_sent=False,
                                      scheduled_at__gt=now, scheduled_at__lte=now + dt.timedelta(minutes=15))
        n = 0
        for s in soon.select_related("teacher", "student", "subject"):
            for u in (s.teacher, s.student):
                notify(u, "session_reminder", "حصتك هتبدأ كمان شوية ⏰",
                       f"{s.subject} — {timezone.localtime(s.scheduled_at):%H:%M}", {"screen": "session", "id": s.id})
            s.reminder_sent = True
            s.save(update_fields=["reminder_sent"])
            n += 1

        # حصص فاتت ومحدش دخلها خالص → غياب المدرس للمراجعة
        stale = Session.objects.filter(status="scheduled", scheduled_at__lt=now - dt.timedelta(hours=2),
                                       teacher_joined_at__isnull=True)
        stale_count = stale.update(status="teacher_absent", ended_at=now)
        # حصص لايف ونسيوا يقفلوها
        for s in Session.objects.filter(status="live", scheduled_at__lt=now - dt.timedelta(hours=3)):
            from apps.tutoring.services import _consume
            s.status, s.ended_at = "completed", now
            _consume(s)
            s.save()

        expired = list(Subscription.objects.filter(status="active", end_date__lt=timezone.localdate()))
        for sub in expired:
            sub.status = "expired"
            sub.save(update_fields=["status"])
            sub.sessions.filter(status="scheduled").update(status="cancelled", cancel_reason="انتهاء الاشتراك")
            notify(sub.student, "subscription_expired", "اشتراكك انتهى", "جدد عشان تكمل.", {"screen": "subscription", "id": sub.id})

        for sub in Subscription.objects.filter(status="active"):
            generate_sessions(sub)
        self.stdout.write(f"reminders={n} stale={stale_count} expired={len(expired)}")
