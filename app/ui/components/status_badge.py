from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def create_health_badge(status: str) -> QLabel:
    health_badge = QLabel()

    cleaned_status = (status or "").strip().upper()

    if cleaned_status == "OK":
        health_badge.setObjectName("HealthOk")
        health_badge.setText("Sistem Sağlığı: OK")
    elif cleaned_status == "WARN":
        health_badge.setObjectName("HealthWarn")
        health_badge.setText("Sistem Sağlığı: WARN")
    else:
        health_badge.setObjectName("HealthFail")
        health_badge.setText("Sistem Sağlığı: FAIL")

    health_badge.setAlignment(Qt.AlignCenter)
    health_badge.setMinimumWidth(170)

    return health_badge


def create_user_badge(username: Any, role: Any) -> QLabel:
    username_text = str(username or "-")

    if hasattr(role, "value"):
        role_text = str(role.value)
    else:
        role_text = str(role or "-")

    user_badge = QLabel(f"Oturum: {username_text} / {role_text}")
    user_badge.setObjectName("UserBadge")
    user_badge.setAlignment(Qt.AlignCenter)
    user_badge.setMinimumWidth(190)

    return user_badge