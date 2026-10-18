"""
إرسال Push عن طريق Firebase Cloud Messaging HTTP v1.
محتاج: FCM_PROJECT_ID + FCM_SERVICE_ACCOUNT_FILE (ملف JSON من Firebase) + pip install google-auth
لو مش متظبط بيتجاهل بهدوء (الإشعار بيتسجل في الداتابيز وبيوصل بالـ WebSocket عادي).
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
_creds = None


def _access_token():
    global _creds
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    if _creds is None:
        scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
        if settings.FCM_SERVICE_ACCOUNT_JSON:  # محتوى ملف الـ JSON نفسه في متغير (Railway ومفيش ملفات)
            import json
            _creds = service_account.Credentials.from_service_account_info(json.loads(settings.FCM_SERVICE_ACCOUNT_JSON), scopes=scopes)
        else:
            _creds = service_account.Credentials.from_service_account_file(settings.FCM_SERVICE_ACCOUNT_FILE, scopes=scopes)
    if not _creds.valid:
        _creds.refresh(Request())
    return _creds.token


def send_push(tokens, title, body, data=None):
    if not (settings.FCM_PROJECT_ID and (settings.FCM_SERVICE_ACCOUNT_FILE or settings.FCM_SERVICE_ACCOUNT_JSON)) or not tokens:
        return []
    try:
        token = _access_token()
    except Exception as e:  # google-auth مش متسطب أو الملف غلط
        logger.warning("FCM disabled: %s", e)
        return []
    url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"
    invalid = []
    str_data = {k: str(v) for k, v in (data or {}).items()}
    for t in tokens:
        payload = {"message": {
            "token": t,
            "notification": {"title": title, "body": body},
            "data": str_data,
            "android": {"priority": "high", "notification": {"sound": "default", "channel_id": "default"}},
            "apns": {"payload": {"aps": {"sound": "default"}}},
        }}
        try:
            r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if r.status_code == 404 or "UNREGISTERED" in r.text:
                invalid.append(t)
        except requests.RequestException as e:
            logger.warning("FCM send failed: %s", e)
    return invalid
