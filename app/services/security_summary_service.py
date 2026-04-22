from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


@dataclass(frozen=True)
class SecuritySummary:
    generated_at: datetime
    period_hours: int
    login_success_count: int
    login_failed_count: int
    permission_denied_count: int
    recent_permission_denied_rows: list[dict[str, Any]]
    last_backup_log_line: str
    last_restore_test_log_line: str


def _safe_text(value: Any) -> str:
    if value is None:
        return "-"

    return str(value)


def _read_last_non_empty_line(file_path: Path) -> str:
    if not file_path.exists():
        return "Log dosyası bulunamadı."

    if not file_path.is_file():
        return "Log yolu dosya değil."

    lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line in reversed(lines):
        cleaned_line = line.strip()

        if cleaned_line:
            return cleaned_line

    return "Log dosyası boş."


def _get_logs_folder() -> Path:
    return settings.log_folder


def _count_audit_action(
    session: Session,
    *,
    action: str,
    period_hours: int,
) -> int:
    statement = text(
        """
        SELECT COUNT(*) AS count_value
        FROM audit_logs
        WHERE action = :action
          AND created_at >= NOW() - (:period_hours * INTERVAL '1 hour')
        """
    )

    result = session.execute(
        statement,
        {
            "action": action,
            "period_hours": period_hours,
        },
    ).scalar_one()

    return int(result or 0)


def _get_recent_permission_denied_rows(
    session: Session,
    *,
    period_hours: int,
    limit: int,
) -> list[dict[str, Any]]:
    statement = text(
        """
        SELECT
            id,
            created_at,
            entity_type,
            entity_id,
            description,
            new_values
        FROM audit_logs
        WHERE action = 'PERMISSION_DENIED'
          AND created_at >= NOW() - (:period_hours * INTERVAL '1 hour')
        ORDER BY id DESC
        LIMIT :limit
        """
    )

    rows = session.execute(
        statement,
        {
            "period_hours": period_hours,
            "limit": limit,
        },
    ).mappings().all()

    result: list[dict[str, Any]] = []

    for row in rows:
        new_values = row.get("new_values") or {}

        if isinstance(new_values, dict):
            username = new_values.get("username", "-")
            role = new_values.get("role", "-")
            required_permission = new_values.get("required_permission", "-")
            attempted_action = new_values.get("attempted_action", "-")
        else:
            username = "-"
            role = "-"
            required_permission = "-"
            attempted_action = "-"

        result.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "entity_type": row.get("entity_type"),
                "entity_id": row.get("entity_id"),
                "username": username,
                "role": role,
                "required_permission": required_permission,
                "attempted_action": attempted_action,
                "description": row.get("description"),
            }
        )

    return result


def get_security_summary(
    session: Session,
    *,
    period_hours: int = 24,
    permission_denied_limit: int = 10,
) -> SecuritySummary:
    if period_hours <= 0:
        period_hours = 24

    if permission_denied_limit <= 0:
        permission_denied_limit = 10

    logs_folder = _get_logs_folder()

    login_success_count = _count_audit_action(
        session,
        action="LOGIN_SUCCESS",
        period_hours=period_hours,
    )

    login_failed_count = _count_audit_action(
        session,
        action="LOGIN_FAILED",
        period_hours=period_hours,
    )

    permission_denied_count = _count_audit_action(
        session,
        action="PERMISSION_DENIED",
        period_hours=period_hours,
    )

    recent_permission_denied_rows = _get_recent_permission_denied_rows(
        session,
        period_hours=period_hours,
        limit=permission_denied_limit,
    )

    last_backup_log_line = _read_last_non_empty_line(
        logs_folder / "backup_log.txt"
    )

    last_restore_test_log_line = _read_last_non_empty_line(
        logs_folder / "restore_test_log.txt"
    )

    return SecuritySummary(
        generated_at=datetime.now(),
        period_hours=period_hours,
        login_success_count=login_success_count,
        login_failed_count=login_failed_count,
        permission_denied_count=permission_denied_count,
        recent_permission_denied_rows=recent_permission_denied_rows,
        last_backup_log_line=last_backup_log_line,
        last_restore_test_log_line=last_restore_test_log_line,
    )


def build_security_summary_text(summary: SecuritySummary) -> str:
    lines: list[str] = []

    lines.append("FTM GÜVENLİK ÖZET RAPORU")
    lines.append("=" * 80)
    lines.append(f"Rapor zamanı          : {summary.generated_at}")
    lines.append(f"Rapor dönemi          : Son {summary.period_hours} saat")
    lines.append("")
    lines.append("GİRİŞ / YETKİ ÖZETİ")
    lines.append("-" * 80)
    lines.append(f"Başarılı giriş sayısı : {summary.login_success_count}")
    lines.append(f"Başarısız giriş sayısı: {summary.login_failed_count}")
    lines.append(f"Yetkisiz işlem sayısı : {summary.permission_denied_count}")
    lines.append("")
    lines.append("YEDEKLEME DURUMU")
    lines.append("-" * 80)
    lines.append(f"Son yedekleme kaydı   : {summary.last_backup_log_line}")
    lines.append(f"Son restore test kaydı: {summary.last_restore_test_log_line}")
    lines.append("")
    lines.append("SON YETKİSİZ İŞLEM DENEMELERİ")
    lines.append("-" * 80)

    if not summary.recent_permission_denied_rows:
        lines.append("Son dönemde yetkisiz işlem denemesi yok.")
    else:
        for row in summary.recent_permission_denied_rows:
            lines.append(f"Log ID        : {_safe_text(row.get('id'))}")
            lines.append(f"Tarih         : {_safe_text(row.get('created_at'))}")
            lines.append(f"Kullanıcı     : {_safe_text(row.get('username'))}")
            lines.append(f"Rol           : {_safe_text(row.get('role'))}")
            lines.append(f"Gereken yetki : {_safe_text(row.get('required_permission'))}")
            lines.append(f"Denenen işlem : {_safe_text(row.get('attempted_action'))}")
            lines.append(f"Entity        : {_safe_text(row.get('entity_type'))} / {_safe_text(row.get('entity_id'))}")
            lines.append(f"Açıklama      : {_safe_text(row.get('description'))}")
            lines.append("-" * 80)

    lines.append("")
    lines.append("Bu rapor FTM güvenlik sistemi tarafından oluşturulmuştur.")

    return "\n".join(lines)