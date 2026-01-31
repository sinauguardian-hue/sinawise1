from __future__ import annotations

import os

import firebase_admin
from firebase_admin import credentials, messaging


def init_firebase() -> None:
    """
    Inisialisasi Firebase Admin SDK dari service account JSON.
    Pastikan env var GOOGLE_APPLICATION_CREDENTIALS mengarah ke file JSON.
    """
    if firebase_admin._apps:
        return

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS belum diset.")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)


def send_to_topic(
    topic: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    notification: bool = True,
    android_priority: str = "high",
    sound: str | None = None,
) -> str:
    """
    Kirim push notification ke FCM topic (mis. 'sinabung').
    Return message_id jika sukses.
    """
    init_firebase()

    notif = None
    if notification:
        notif = messaging.Notification(
            title=title,
            body=body,
        )

    msg = messaging.Message(
        topic=topic,
        notification=notif,
        data=data or {},
        android=messaging.AndroidConfig(
            priority=android_priority,
            notification=messaging.AndroidNotification(
                sound=sound,
            )
            if sound
            else None,
        ),
    )
    return messaging.send(msg)
