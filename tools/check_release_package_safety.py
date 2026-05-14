from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


TOOL_VERSION = "1.0.1"

FAIL_FILE_GLOBS = (
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.ftmlic",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.env",
)

FAIL_EXACT_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.test",
    "license.json",
    "license.json.bak",
    "license_clock_state.json",
    "device_identity.json",
    "app_settings.json",
    "app_setup.json",
    "backup_mail_settings.json",
    "ftm_local.db",
    "ftm_license_ed25519_private.pem",
    "ftm_license_ed25519_private_encrypted.pem",
    "license_generation_log.jsonl",
}

FAIL_EXACT_FOLDER_NAMES = {
    ".git",
    ".github",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "keys",
    "tools",
    "source",
    "sources",
    "logs",
    "backups",
    "exports",
    "pilot_packages",
    "release_packages",
}

FAIL_NAME_CONTAINS = (
    "licence_maker",
    "license_maker",
    "ftm_license_maker",
    "encrypt_license_private_key",
    "create_signed_license",
    "private_key",
    "ed25519_private",
)

FAIL_CONTENT_SIGNATURES = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"ftm_license_ed25519_private",
    b"FTM_LICENSE_ADMIN",
    b"FTM_PRIVATE_KEYS",
)

WARN_FILE_GLOBS = (
    "*.log",
    "*.jsonl",
    "*.bak",
    "*.tmp",
    "*.pyc",
    "*.pyo",
)

WARN_EXACT_FOLDER_NAMES = {
    "build",
    "dist",
    "tmp",
    "temp",
}

BINARY_CONTENT_SCAN_SKIP_EXTENSIONS = {
    ".dll",
    ".exe",
    ".pyd",
    ".so",
    ".dylib",
    ".bin",
    ".dat",
    ".pak",
    ".rcc",
    ".lib",
    ".obj",
    ".a",
    ".msi",
    ".cab",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".ico",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".cur",
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    ".pdf",
    ".xlsx",
    ".xls",
    ".docx",
    ".pptx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wav",
}

DEFAULT_MAX_CONTENT_SCAN_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class Finding:
    severity: str
    reason: str
    path: str


class ReleaseSafetyError(RuntimeError):
    pass


def _normalize_name(value: str) -> str:
    return str(value or "").strip().lower()


def _is_hidden_or_system_noise(path: Path) -> bool:
    name = _normalize_name(path.name)

    if name in {"thumbs.db", "desktop.ini"}:
        return True

    return False


def _relative_display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _matches_any_glob(file_name: str, patterns: tuple[str, ...]) -> str | None:
    lowered_name = _normalize_name(file_name)

    for pattern in patterns:
        if fnmatch.fnmatch(lowered_name, _normalize_name(pattern)):
            return pattern

    return None


def _contains_forbidden_name(file_name: str) -> str | None:
    lowered_name = _normalize_name(file_name)

    for marker in FAIL_NAME_CONTAINS:
        if marker in lowered_name:
            return marker

    return None


def _should_scan_file_content(path: Path) -> bool:
    """
    İçerik imza taraması sadece metin/config/script benzeri dosyalarda yapılmalıdır.

    PySide6 / Qt DLL dosyaları gibi binary dosyaların içinde OpenSSL/TLS parser sabitleri
    bulunabilir. Örneğin "-----BEGIN PRIVATE KEY-----" metni bir DLL içinde sadece
    sertifika/private-key ayrıştırma sabiti olarak geçebilir. Bu gerçek private key
    sızıntısı değildir ve false positive üretir.

    Dosya adı, uzantı ve klasör bazlı hassas dosya kontrolleri tüm dosyalar için
    zaten ayrıca çalışmaya devam eder.
    """

    suffix = _normalize_name(path.suffix)

    if suffix in BINARY_CONTENT_SCAN_SKIP_EXTENSIONS:
        return False

    return True


def _read_limited_bytes(path: Path, max_bytes: int) -> bytes:
    try:
        file_size = path.stat().st_size
    except OSError:
        return b""

    if file_size <= 0:
        return b""

    read_size = min(file_size, max_bytes)

    try:
        with path.open("rb") as file:
            return file.read(read_size)
    except OSError:
        return b""


def _content_signature_match(path: Path, max_bytes: int) -> bytes | None:
    data = _read_limited_bytes(path, max_bytes)

    if not data:
        return None

    for signature in FAIL_CONTENT_SIGNATURES:
        if signature in data:
            return signature

    return None


def _scan_folder(
    *,
    target_path: Path,
    max_content_scan_bytes: int,
    scan_content: bool,
) -> list[Finding]:
    findings: list[Finding] = []
    target_path = target_path.resolve()

    for current_path in sorted(target_path.rglob("*")):
        if _is_hidden_or_system_noise(current_path):
            continue

        relative_path = _relative_display_path(current_path, target_path)
        lowered_name = _normalize_name(current_path.name)

        if current_path.is_dir():
            if lowered_name in FAIL_EXACT_FOLDER_NAMES:
                findings.append(
                    Finding(
                        severity="FAIL",
                        reason=f"Yasaklı klasör bulundu: {current_path.name}",
                        path=relative_path,
                    )
                )
                continue

            if lowered_name in WARN_EXACT_FOLDER_NAMES:
                findings.append(
                    Finding(
                        severity="WARN",
                        reason=f"Dağıtım paketinde olmaması önerilen klasör: {current_path.name}",
                        path=relative_path,
                    )
                )

            continue

        if not current_path.is_file():
            continue

        if lowered_name in FAIL_EXACT_FILE_NAMES:
            findings.append(
                Finding(
                    severity="FAIL",
                    reason=f"Yasaklı dosya adı bulundu: {current_path.name}",
                    path=relative_path,
                )
            )

        fail_glob = _matches_any_glob(current_path.name, FAIL_FILE_GLOBS)

        if fail_glob is not None:
            findings.append(
                Finding(
                    severity="FAIL",
                    reason=f"Yasaklı dosya deseni bulundu: {fail_glob}",
                    path=relative_path,
                )
            )

        forbidden_marker = _contains_forbidden_name(current_path.name)

        if forbidden_marker is not None:
            findings.append(
                Finding(
                    severity="FAIL",
                    reason=f"Yasaklı lisans/private key aracı izine benziyor: {forbidden_marker}",
                    path=relative_path,
                )
            )

        warn_glob = _matches_any_glob(current_path.name, WARN_FILE_GLOBS)

        if warn_glob is not None:
            findings.append(
                Finding(
                    severity="WARN",
                    reason=f"Dağıtım paketinde olmaması önerilen dosya deseni: {warn_glob}",
                    path=relative_path,
                )
            )

        if scan_content and _should_scan_file_content(current_path):
            signature = _content_signature_match(current_path, max_content_scan_bytes)

            if signature is not None:
                findings.append(
                    Finding(
                        severity="FAIL",
                        reason=(
                            "Dosya içeriğinde hassas private key / lisans yönetim izi bulundu: "
                            + signature.decode("utf-8", errors="replace")
                        ),
                        path=relative_path,
                    )
                )

    return findings


def _print_header(target_path: Path) -> None:
    print("")
    print("FTM RELEASE PACKAGE SAFETY CHECK")
    print("-" * 80)
    print(f"Tool version : {TOOL_VERSION}")
    print(f"Target path  : {target_path}")
    print(f"Checked at   : {datetime.now().isoformat(timespec='seconds')}")
    print("-" * 80)


def _print_findings(findings: list[Finding]) -> None:
    fail_findings = [finding for finding in findings if finding.severity == "FAIL"]
    warn_findings = [finding for finding in findings if finding.severity == "WARN"]

    if fail_findings:
        print("")
        print("FAIL BULGULARI")
        print("-" * 80)

        for index, finding in enumerate(fail_findings, start=1):
            print(f"{index}. {finding.reason}")
            print(f"   Yol: {finding.path}")

    if warn_findings:
        print("")
        print("WARN BULGULARI")
        print("-" * 80)

        for index, finding in enumerate(warn_findings, start=1):
            print(f"{index}. {finding.reason}")
            print(f"   Yol: {finding.path}")

    if not findings:
        print("")
        print("BULGU YOK")
        print("-" * 80)


def _write_json_report(
    *,
    report_file: Path,
    target_path: Path,
    findings: list[Finding],
) -> None:
    payload = {
        "tool": "check_release_package_safety.py",
        "tool_version": TOOL_VERSION,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "target_path": str(target_path),
        "fail_count": sum(1 for finding in findings if finding.severity == "FAIL"),
        "warn_count": sum(1 for finding in findings if finding.severity == "WARN"),
        "findings": [asdict(finding) for finding in findings],
    }

    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def check_release_package(
    *,
    target_path: Path,
    scan_content: bool,
    max_content_scan_bytes: int,
) -> list[Finding]:
    target_path = target_path.expanduser().resolve()

    if not target_path.exists():
        raise ReleaseSafetyError(f"Kontrol edilecek yol bulunamadı: {target_path}")

    if not target_path.is_dir():
        raise ReleaseSafetyError(f"Kontrol edilecek yol klasör olmalıdır: {target_path}")

    return _scan_folder(
        target_path=target_path,
        scan_content=scan_content,
        max_content_scan_bytes=max_content_scan_bytes,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_release_package_safety.py",
        description=(
            "FTM müşteri release paketini hassas dosya sızıntısı açısından kontrol eder."
        ),
    )

    parser.add_argument(
        "--path",
        required=True,
        help="Kontrol edilecek müşteri release / kurulum paketi klasörü.",
    )

    parser.add_argument(
        "--json-report",
        default="",
        help="İsteğe bağlı JSON rapor dosyası yolu.",
    )

    parser.add_argument(
        "--no-content-scan",
        action="store_true",
        help="Dosya içeriği imza taramasını kapatır. Normal kullanımda önerilmez.",
    )

    parser.add_argument(
        "--max-content-scan-mb",
        type=int,
        default=25,
        help="Her dosyada içerik taraması için okunacak maksimum MB. Varsayılan: 25",
    )

    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="WARN bulgularını da başarısızlık sayar.",
    )

    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    target_path = Path(str(args.path)).expanduser().resolve()
    max_content_scan_mb = max(1, int(args.max_content_scan_mb or 25))
    max_content_scan_bytes = max_content_scan_mb * 1024 * 1024
    scan_content = not bool(args.no_content_scan)

    try:
        _print_header(target_path)

        findings = check_release_package(
            target_path=target_path,
            scan_content=scan_content,
            max_content_scan_bytes=max_content_scan_bytes,
        )

        _print_findings(findings)

        json_report_text = str(args.json_report or "").strip()

        if json_report_text:
            report_file = Path(json_report_text).expanduser().resolve()
            _write_json_report(
                report_file=report_file,
                target_path=target_path,
                findings=findings,
            )
            print("")
            print(f"JSON rapor yazıldı: {report_file}")

        fail_count = sum(1 for finding in findings if finding.severity == "FAIL")
        warn_count = sum(1 for finding in findings if finding.severity == "WARN")

        print("")
        print("ÖZET")
        print("-" * 80)
        print(f"FAIL: {fail_count}")
        print(f"WARN: {warn_count}")

        if fail_count > 0:
            print("")
            print("SONUÇ: FAIL - Müşteri paketinde hassas veya yasaklı dosya bulundu.")
            print("Bu paket müşteriye götürülmemelidir.")
            return 1

        if warn_count > 0 and bool(args.fail_on_warn):
            print("")
            print("SONUÇ: FAIL - WARN bulguları fail-on-warn nedeniyle başarısız sayıldı.")
            return 1

        if warn_count > 0:
            print("")
            print("SONUÇ: OK WITH WARNINGS - Kritik hassas dosya bulunmadı, ancak temizlik önerileri var.")
            return 0

        print("")
        print("SONUÇ: OK - Müşteri paketi güvenli görünüyor.")
        return 0

    except ReleaseSafetyError as exc:
        print("")
        print("SONUÇ: ERROR")
        print("-" * 80)
        print(str(exc))
        return 2
    except KeyboardInterrupt:
        print("")
        print("İşlem kullanıcı tarafından iptal edildi.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())