from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.core.runtime_paths import ensure_runtime_folders
from app.db.session import session_scope
from app.services.backup_standard_service import (
    BackupStandardServiceError,
    validate_latest_backup_against_standard,
)
from app.services.database_migration_service import (
    DatabaseMigrationServiceError,
    get_database_migration_status,
)
from app.services.license_clock_service import (
    LicenseClockServiceError,
    check_license_clock_rollback,
)
from app.services.license_service import (
    LICENSE_STATUS_ACTIVE,
    LICENSE_STATUS_EXPIRING_SOON,
    LicenseServiceError,
    check_license,
)
from app.services.system_health_service import run_system_health_check
from app.services.version_compatibility_service import (
    DatabaseVersionCompatibilityError,
    get_database_version_compatibility_status,
)


RELEASE_READINESS_STATUS_OK = "OK"
RELEASE_READINESS_STATUS_WARN = "WARN"
RELEASE_READINESS_STATUS_FAIL = "FAIL"

RELEASE_READINESS_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReleaseReadinessServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseReadinessCheck:
    category: str
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class ReleaseReadinessReport:
    generated_at: str
    overall_status: str
    ok_count: int
    warn_count: int
    fail_count: int
    checks: list[ReleaseReadinessCheck]

    @property
    def is_ready_for_customer(self) -> bool:
        return self.fail_count == 0

    @property
    def summary_message(self) -> str:
        if self.overall_status == RELEASE_READINESS_STATUS_OK:
            return "FTM müşteri kurulumu için hazır görünüyor."

        if self.overall_status == RELEASE_READINESS_STATUS_WARN:
            return (
                "FTM müşteri kurulumu için genel olarak hazır görünüyor; "
                "ancak dikkat edilmesi gereken uyarılar var."
            )

        return (
            "FTM müşteri kurulumu için hazır değil. "
            "Başarısız kontroller düzeltilmeden release yapılmamalı."
        )


def run_release_readiness_check() -> ReleaseReadinessReport:
    checks: list[ReleaseReadinessCheck] = []

    _run_check_safely(
        checks=checks,
        check_function=_check_runtime_paths,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_database_migration,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_database_version_compatibility,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_license_status,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_license_clock,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_system_health,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_latest_backup_standard,
    )

    _run_check_safely(
        checks=checks,
        check_function=_check_restore_test_log,
    )

    ok_count = len(
        [
            check
            for check in checks
            if check.status == RELEASE_READINESS_STATUS_OK
        ]
    )

    warn_count = len(
        [
            check
            for check in checks
            if check.status == RELEASE_READINESS_STATUS_WARN
        ]
    )

    fail_count = len(
        [
            check
            for check in checks
            if check.status == RELEASE_READINESS_STATUS_FAIL
        ]
    )

    overall_status = _calculate_overall_status(checks)

    return ReleaseReadinessReport(
        generated_at=datetime.now().strftime(RELEASE_READINESS_DATE_FORMAT),
        overall_status=overall_status,
        ok_count=ok_count,
        warn_count=warn_count,
        fail_count=fail_count,
        checks=checks,
    )


def build_release_readiness_report_text(report: ReleaseReadinessReport) -> str:
    lines = [
        "FTM RELEASE / MÜŞTERİ KURULUM ÖNCESİ KONTROL RAPORU",
        "=" * 64,
        f"Rapor zamanı : {report.generated_at}",
        f"Genel durum  : {report.overall_status}",
        f"OK           : {report.ok_count}",
        f"WARN         : {report.warn_count}",
        f"FAIL         : {report.fail_count}",
        "",
        report.summary_message,
        "",
        "KONTROLLER",
        "-" * 64,
    ]

    for check in report.checks:
        lines.append(
            f"[{check.status}] {check.category} / {check.name}: {check.message}"
        )

    lines.append("")
    lines.append("RELEASE KARARI")
    lines.append("-" * 64)

    if report.is_ready_for_customer:
        lines.append(
            "Bloke eden hata yok. Uyarılar varsa kontrol edilerek müşteri kurulumu yapılabilir."
        )
    else:
        lines.append(
            "Release yapılmamalı. FAIL durumundaki kontroller düzeltilmeli."
        )

    return "\n".join(lines)


def get_release_readiness_summary_lines() -> list[str]:
    report = run_release_readiness_check()

    return build_release_readiness_report_text(report).splitlines()


def _run_check_safely(
    *,
    checks: list[ReleaseReadinessCheck],
    check_function: Callable[[], ReleaseReadinessCheck],
) -> None:
    try:
        checks.append(check_function())

    except Exception as exc:
        checks.append(
            ReleaseReadinessCheck(
                category="Beklenmeyen Hata",
                name=check_function.__name__,
                status=RELEASE_READINESS_STATUS_FAIL,
                message=f"Kontrol çalıştırılırken beklenmeyen hata oluştu: {exc}",
            )
        )


def _check_runtime_paths() -> ReleaseReadinessCheck:
    runtime_paths = ensure_runtime_folders()

    required_folders = [
        runtime_paths.root_folder,
        runtime_paths.data_folder,
        runtime_paths.config_folder,
        runtime_paths.backups_folder,
        runtime_paths.exports_folder,
        runtime_paths.logs_folder,
    ]

    missing_folders = [
        folder
        for folder in required_folders
        if not folder.exists() or not folder.is_dir()
    ]

    if missing_folders:
        return ReleaseReadinessCheck(
            category="Runtime",
            name="Runtime klasörleri",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=(
                "Eksik runtime klasörü var: "
                + ", ".join(str(folder) for folder in missing_folders)
            ),
        )

    return ReleaseReadinessCheck(
        category="Runtime",
        name="Runtime klasörleri",
        status=RELEASE_READINESS_STATUS_OK,
        message=f"Runtime klasörleri hazır: {runtime_paths.root_folder}",
    )


def _check_database_migration() -> ReleaseReadinessCheck:
    try:
        migration_status = get_database_migration_status()

    except DatabaseMigrationServiceError as exc:
        return ReleaseReadinessCheck(
            category="Veritabanı",
            name="Migration durumu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=str(exc),
        )

    if migration_status.is_up_to_date:
        return ReleaseReadinessCheck(
            category="Veritabanı",
            name="Migration durumu",
            status=RELEASE_READINESS_STATUS_OK,
            message=(
                f"Migration güncel. "
                f"DB schema: v{migration_status.current_user_version}, "
                f"beklenen: v{migration_status.expected_schema_version}"
            ),
        )

    return ReleaseReadinessCheck(
        category="Veritabanı",
        name="Migration durumu",
        status=RELEASE_READINESS_STATUS_FAIL,
        message=(
            "Migration güncel değil. "
            f"Bekleyen migration: {', '.join(migration_status.pending_migration_ids) or '-'}"
        ),
    )


def _check_database_version_compatibility() -> ReleaseReadinessCheck:
    try:
        compatibility_status = get_database_version_compatibility_status()

    except DatabaseVersionCompatibilityError as exc:
        return ReleaseReadinessCheck(
            category="Veritabanı",
            name="Uygulama / DB sürüm uyumu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=exc.user_message,
        )

    if compatibility_status.is_compatible:
        return ReleaseReadinessCheck(
            category="Veritabanı",
            name="Uygulama / DB sürüm uyumu",
            status=RELEASE_READINESS_STATUS_OK,
            message=compatibility_status.summary_text,
        )

    return ReleaseReadinessCheck(
        category="Veritabanı",
        name="Uygulama / DB sürüm uyumu",
        status=RELEASE_READINESS_STATUS_FAIL,
        message="; ".join(compatibility_status.blocking_reasons),
    )


def _check_license_status() -> ReleaseReadinessCheck:
    try:
        license_result = check_license()

    except LicenseServiceError as exc:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Lisans durumu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=str(exc),
        )

    except Exception as exc:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Lisans durumu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=f"Lisans kontrolü çalıştırılamadı: {exc}",
        )

    status = str(license_result.status or "")

    if status == LICENSE_STATUS_ACTIVE and license_result.is_valid:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Lisans durumu",
            status=RELEASE_READINESS_STATUS_OK,
            message=license_result.message,
        )

    if status == LICENSE_STATUS_EXPIRING_SOON and license_result.is_valid:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Lisans durumu",
            status=RELEASE_READINESS_STATUS_WARN,
            message=(
                f"{license_result.message} "
                "Release öncesi lisans süresi kontrol edilmeli."
            ),
        )

    return ReleaseReadinessCheck(
        category="Lisans",
        name="Lisans durumu",
        status=RELEASE_READINESS_STATUS_FAIL,
        message=license_result.message,
    )


def _check_license_clock() -> ReleaseReadinessCheck:
    try:
        clock_result = check_license_clock_rollback()

    except LicenseClockServiceError as exc:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Saat geri alma kontrolü",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=str(exc),
        )

    if clock_result.rollback_detected:
        return ReleaseReadinessCheck(
            category="Lisans",
            name="Saat geri alma kontrolü",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=clock_result.message,
        )

    return ReleaseReadinessCheck(
        category="Lisans",
        name="Saat geri alma kontrolü",
        status=RELEASE_READINESS_STATUS_OK,
        message=clock_result.message,
    )


def _check_system_health() -> ReleaseReadinessCheck:
    with session_scope() as session:
        health_report = run_system_health_check(session)

    overall_status = str(
        getattr(
            health_report,
            "overall_status",
            RELEASE_READINESS_STATUS_FAIL,
        )
        or RELEASE_READINESS_STATUS_FAIL
    ).upper()

    passed_count = int(getattr(health_report, "passed_count", 0) or 0)
    warning_count = int(getattr(health_report, "warning_count", 0) or 0)
    failed_count = int(getattr(health_report, "failed_count", 0) or 0)

    if overall_status == RELEASE_READINESS_STATUS_OK:
        status = RELEASE_READINESS_STATUS_OK
    elif overall_status == RELEASE_READINESS_STATUS_WARN:
        status = RELEASE_READINESS_STATUS_WARN
    else:
        status = RELEASE_READINESS_STATUS_FAIL

    return ReleaseReadinessCheck(
        category="Sistem",
        name="Genel sistem sağlığı",
        status=status,
        message=(
            f"Sistem sağlık durumu: {overall_status} | "
            f"OK: {passed_count}, WARN: {warning_count}, FAIL: {failed_count}"
        ),
    )


def _check_latest_backup_standard() -> ReleaseReadinessCheck:
    try:
        backup_result = validate_latest_backup_against_standard()

    except BackupStandardServiceError as exc:
        return ReleaseReadinessCheck(
            category="Yedekleme",
            name="Son yedek standardı",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=str(exc),
        )

    except Exception as exc:
        return ReleaseReadinessCheck(
            category="Yedekleme",
            name="Son yedek standardı",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=f"Son yedek doğrulanamadı: {exc}",
        )

    if backup_result.success:
        return ReleaseReadinessCheck(
            category="Yedekleme",
            name="Son yedek standardı",
            status=RELEASE_READINESS_STATUS_OK,
            message=(
                f"{backup_result.summary_message} "
                f"Dosya: {backup_result.backup_file}"
            ),
        )

    return ReleaseReadinessCheck(
        category="Yedekleme",
        name="Son yedek standardı",
        status=RELEASE_READINESS_STATUS_FAIL,
        message=backup_result.summary_message,
    )


def _check_restore_test_log() -> ReleaseReadinessCheck:
    runtime_paths = ensure_runtime_folders()
    restore_test_log_file = runtime_paths.logs_folder / "restore_test_log.txt"

    if not restore_test_log_file.exists():
        return ReleaseReadinessCheck(
            category="Restore",
            name="Restore test logu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message=f"Restore test log dosyası bulunamadı: {restore_test_log_file}",
        )

    last_line = _read_last_non_empty_line(restore_test_log_file)

    if not last_line:
        return ReleaseReadinessCheck(
            category="Restore",
            name="Restore test logu",
            status=RELEASE_READINESS_STATUS_FAIL,
            message="Restore test log dosyası boş.",
        )

    if "restore test başarılı" in last_line.lower() or "restore test basarili" in last_line.lower():
        return ReleaseReadinessCheck(
            category="Restore",
            name="Restore test logu",
            status=RELEASE_READINESS_STATUS_OK,
            message=last_line,
        )

    return ReleaseReadinessCheck(
        category="Restore",
        name="Restore test logu",
        status=RELEASE_READINESS_STATUS_WARN,
        message=(
            "Restore test logu bulundu ancak son satır başarı ifadesi içermiyor: "
            f"{last_line}"
        ),
    )


def _read_last_non_empty_line(file_path: Path) -> str:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()

    except UnicodeDecodeError:
        lines = file_path.read_text(encoding="cp1254", errors="replace").splitlines()

    except OSError:
        return ""

    for line in reversed(lines):
        clean_line = line.strip()

        if clean_line:
            return clean_line

    return ""


def _calculate_overall_status(checks: list[ReleaseReadinessCheck]) -> str:
    if any(check.status == RELEASE_READINESS_STATUS_FAIL for check in checks):
        return RELEASE_READINESS_STATUS_FAIL

    if any(check.status == RELEASE_READINESS_STATUS_WARN for check in checks):
        return RELEASE_READINESS_STATUS_WARN

    return RELEASE_READINESS_STATUS_OK


__all__ = [
    "RELEASE_READINESS_STATUS_OK",
    "RELEASE_READINESS_STATUS_WARN",
    "RELEASE_READINESS_STATUS_FAIL",
    "RELEASE_READINESS_DATE_FORMAT",
    "ReleaseReadinessServiceError",
    "ReleaseReadinessCheck",
    "ReleaseReadinessReport",
    "run_release_readiness_check",
    "build_release_readiness_report_text",
    "get_release_readiness_summary_lines",
]