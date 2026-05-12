from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Table, TableStyle

from app.db.session import session_scope
from app.models.credit_facility import BankAccountCreditLimit
from app.reports.report_pdf_base import (
    FtmPdfReportBuilder,
    FtmReportMeta,
    FtmSummaryCard,
)
from app.services.credit_facility_service import (
    CreditFacilityServiceError,
    calculate_credit_limit_period_report,
    get_credit_limit_debt_summary,
)


TRANSACTION_TYPE_TEXTS = {
    "USAGE": "Limit Kullanımı",
    "PAYMENT": "Limit Ödemesi",
    "INTEREST": "Faiz Tahakkuku",
    "FEE": "Masraf",
    "ADJUSTMENT": "Düzeltme",
}


TRANSACTION_STATUS_TEXTS = {
    "ACTIVE": "Aktif",
    "CANCELLED": "İptal",
}


REPORT_ROW_STYLE_BY_TYPE = {
    "USAGE": "RISK",
    "PAYMENT": "SUCCESS",
    "INTEREST": "WARNING",
    "FEE": "WARNING",
    "ADJUSTMENT": "MUTED",
}


class CreditLimitPeriodPdfReportError(ValueError):
    pass


def _decimal_or_zero(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _rate_or_zero(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    if value is None:
        return Decimal("0.000000")

    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.000000")


def _format_decimal_tr(value: Any) -> str:
    amount = _decimal_or_zero(value)
    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    if normalized_currency_code == "TRY":
        return f"{_format_decimal_tr(value)} TL"

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def _format_rate_tr(value: Any) -> str:
    amount = _rate_or_zero(value)
    formatted = f"{amount:,.6f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    formatted = formatted.rstrip("0").rstrip(",")
    return formatted or "0"


def _format_date_tr(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")

    if value is None:
        return "-"

    return str(value)


def _safe_text(value: Any, default: str = "-") -> str:
    text = str(value or "").strip()
    return text if text else default


def _shorten_text(value: Any, max_length: int) -> str:
    text = _safe_text(value)

    if len(text) <= max_length:
        return text

    return text[: max(0, max_length - 3)].rstrip() + "..."


def _transaction_type_text(value: Any) -> str:
    normalized_value = str(value or "").strip().upper()
    return TRANSACTION_TYPE_TEXTS.get(normalized_value, normalized_value or "-")


def _transaction_status_text(value: Any) -> str:
    normalized_value = str(value or "").strip().upper()
    return TRANSACTION_STATUS_TEXTS.get(normalized_value, normalized_value or "-")


def _period_text(period_start: date, period_end: date) -> str:
    return f"{_format_date_tr(period_start)} - {_format_date_tr(period_end)}"


def _current_user_text(created_by: Any) -> str:
    text = str(created_by or "").strip()
    return text or "FTM Kullanıcısı"


def _credit_limit_header_text(credit_limit: BankAccountCreditLimit) -> tuple[str, str, str, str, str, str]:
    bank_account = credit_limit.bank_account
    bank_name = "-"
    account_name = "-"

    if bank_account is not None:
        account_name = bank_account.account_name or "-"

        if getattr(bank_account, "bank", None) is not None:
            bank_name = bank_account.bank.name or "-"

    limit_name = credit_limit.limit_name or "-"
    limit_type = credit_limit.limit_type.value if credit_limit.limit_type else "-"
    currency_code = credit_limit.currency_code.value if credit_limit.currency_code else "TRY"
    full_name = f"{bank_name} / {account_name} / {limit_name}"

    return bank_name, account_name, limit_name, limit_type, currency_code, full_name


def _summary_dict(report_data: dict[str, Any], key: str) -> dict[str, Any]:
    value = report_data.get(key)
    if isinstance(value, dict):
        return value
    return {}


def _report_summary_value(report_data: dict[str, Any], key: str) -> Decimal:
    return _decimal_or_zero(report_data.get(key))


def _nested_summary_value(
    report_data: dict[str, Any],
    summary_key: str,
    value_key: str,
    fallback_key: str | None = None,
) -> Decimal:
    summary = _summary_dict(report_data, summary_key)

    if value_key in summary:
        return _decimal_or_zero(summary.get(value_key))

    if fallback_key is not None:
        return _report_summary_value(report_data, fallback_key)

    return Decimal("0.00")


def _nested_first_value(
    report_data: dict[str, Any],
    summary_key: str,
    value_keys: list[str],
    fallback: Decimal | None = None,
) -> Decimal:
    summary = _summary_dict(report_data, summary_key)

    for value_key in value_keys:
        if value_key in summary:
            return _decimal_or_zero(summary.get(value_key))

    if fallback is not None:
        return fallback

    return Decimal("0.00")


def _daily_rows(report_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = report_data.get("daily_rows") or []

    if not isinstance(raw_rows, list):
        return []

    return [row for row in raw_rows if isinstance(row, dict)]


def _movement_rows(report_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = report_data.get("movement_rows") or []

    if not isinstance(raw_rows, list):
        return []

    return [row for row in raw_rows if isinstance(row, dict)]


def _active_daily_rows(report_data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in _daily_rows(report_data):
        interest_basis_debt = _decimal_or_zero(row.get("interest_basis_debt"))
        daily_interest = _decimal_or_zero(row.get("daily_interest"))

        if interest_basis_debt > Decimal("0.00") or daily_interest > Decimal("0.00"):
            rows.append(row)

    return rows


def _active_day_count(report_data: dict[str, Any]) -> int:
    return len(_active_daily_rows(report_data))


def _movement_count_by_type(report_data: dict[str, Any], transaction_type: str) -> int:
    normalized_type = str(transaction_type or "").strip().upper()
    return sum(
        1
        for row in _movement_rows(report_data)
        if str(row.get("transaction_type") or "").strip().upper() == normalized_type
    )


def _max_interest_basis_debt(report_data: dict[str, Any]) -> Decimal:
    debts = [
        _decimal_or_zero(row.get("interest_basis_debt"))
        for row in _daily_rows(report_data)
    ]

    if not debts:
        return Decimal("0.00")

    return max(debts).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _average_interest_basis_debt(report_data: dict[str, Any]) -> Decimal:
    rows = _daily_rows(report_data)

    if not rows:
        return Decimal("0.00")

    total = sum(
        (_decimal_or_zero(row.get("interest_basis_debt")) for row in rows),
        Decimal("0.00"),
    )

    return (total / Decimal(str(len(rows)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _ending_interest_basis_debt(report_data: dict[str, Any]) -> Decimal:
    return _report_summary_value(report_data, "ending_interest_basis_debt")


def _booked_principal_debt(report_data: dict[str, Any]) -> Decimal:
    return _nested_summary_value(
        report_data,
        "_booked_summary",
        "booked_principal_debt",
        fallback_key="ending_interest_basis_debt",
    )


def _booked_interest_debt(report_data: dict[str, Any]) -> Decimal:
    return _nested_first_value(
        report_data,
        "_booked_summary",
        [
            "booked_interest_debt",
            "interest_debt",
            "remaining_interest_debt",
            "booked_interest_amount",
        ],
    )


def _booked_fee_debt(report_data: dict[str, Any]) -> Decimal:
    return _nested_first_value(
        report_data,
        "_booked_summary",
        [
            "booked_fee_debt",
            "fee_debt",
            "remaining_fee_debt",
            "booked_fee_amount",
        ],
    )


def _booked_interest_fee_debt(report_data: dict[str, Any]) -> Decimal:
    explicit_value = _nested_first_value(
        report_data,
        "_booked_summary",
        [
            "booked_interest_fee_debt",
            "booked_fee_interest_debt",
            "interest_fee_debt",
            "booked_non_principal_debt",
        ],
    )

    if explicit_value > Decimal("0.00"):
        return explicit_value

    return _booked_interest_debt(report_data) + _booked_fee_debt(report_data)


def _booked_total_debt(report_data: dict[str, Any]) -> Decimal:
    explicit_value = _nested_summary_value(
        report_data,
        "_booked_summary",
        "booked_total_debt",
        fallback_key="ending_interest_basis_debt",
    )

    calculated_value = _booked_principal_debt(report_data) + _booked_interest_fee_debt(report_data)

    return max(explicit_value, calculated_value)


def _booked_available_limit(report_data: dict[str, Any]) -> Decimal:
    limit_amount = _report_summary_value(report_data, "limit_amount")
    fallback = max(limit_amount - _booked_principal_debt(report_data), Decimal("0.00"))

    value = _nested_summary_value(
        report_data,
        "_booked_summary",
        "booked_available_limit",
    )

    return value if value > Decimal("0.00") else fallback


def _value_date_available_limit(report_data: dict[str, Any]) -> Decimal:
    limit_amount = _report_summary_value(report_data, "limit_amount")
    fallback = max(limit_amount - _ending_interest_basis_debt(report_data), Decimal("0.00"))

    value = _nested_summary_value(
        report_data,
        "_value_date_summary",
        "available_limit",
    )

    return value if value > Decimal("0.00") else fallback


def _calculated_interest(report_data: dict[str, Any]) -> Decimal:
    return _report_summary_value(report_data, "calculated_interest_total")


def _unbooked_calculated_interest(report_data: dict[str, Any]) -> Decimal:
    calculated_interest = _calculated_interest(report_data)
    booked_interest = _booked_interest_debt(report_data)

    return max(calculated_interest - booked_interest, Decimal("0.00"))


def _bank_load(report_data: dict[str, Any]) -> Decimal:
    return _booked_interest_fee_debt(report_data) + _unbooked_calculated_interest(report_data)


def _next_period_carry_total(report_data: dict[str, Any]) -> Decimal:
    return _booked_principal_debt(report_data) + _bank_load(report_data)


def _value_date_gap(report_data: dict[str, Any]) -> Decimal:
    return _ending_interest_basis_debt(report_data) - _booked_principal_debt(report_data)


def _summary_cards(report_data: dict[str, Any], currency_code: str) -> list[FtmSummaryCard]:
    payable_principal = _booked_principal_debt(report_data)
    bank_load = _bank_load(report_data)
    next_period_carry = _next_period_carry_total(report_data)

    return [
        FtmSummaryCard(
            title="Toplam Limit",
            value=_format_currency_amount(report_data.get("limit_amount"), currency_code),
            hint="Tanımlı kullanılabilir limit",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Dönem Kullanımı",
            value=_format_currency_amount(report_data.get("period_usage_total"), currency_code),
            hint=f"{_movement_count_by_type(report_data, 'USAGE')} kullanım hareketi",
            card_type="risk" if _report_summary_value(report_data, "period_usage_total") > Decimal("0.00") else "normal",
        ),
        FtmSummaryCard(
            title="Dönem Ödemesi",
            value=_format_currency_amount(report_data.get("period_payment_total"), currency_code),
            hint="T+1 valörle faize etki eder",
            card_type="success" if _report_summary_value(report_data, "period_payment_total") > Decimal("0.00") else "normal",
        ),
        FtmSummaryCard(
            title="Ana Para Durumu",
            value=_format_currency_amount(payable_principal, currency_code),
            hint="Dönem sonu ödenebilir ana para",
            card_type="risk" if payable_principal > Decimal("0.00") else "success",
        ),
        FtmSummaryCard(
            title="Banka Yükü",
            value=_format_currency_amount(bank_load, currency_code),
            hint=(
                f"Faiz: {_format_currency_amount(_calculated_interest(report_data), currency_code)} | "
                f"Masraf: {_format_currency_amount(_booked_fee_debt(report_data), currency_code)}"
            ),
            card_type="warning" if bank_load > Decimal("0.00") else "success",
        ),
        FtmSummaryCard(
            title="Sonraki Döneme Devir",
            value=_format_currency_amount(next_period_carry, currency_code),
            hint="Yeni dönemde takip edilecek borç etkisi",
            card_type="risk" if next_period_carry > Decimal("0.00") else "success",
        ),
    ]


def _executive_commentary(report_data: dict[str, Any], currency_code: str) -> str:
    usage_total = _report_summary_value(report_data, "period_usage_total")
    payment_total = _report_summary_value(report_data, "period_payment_total")
    payable_principal = _booked_principal_debt(report_data)
    calculated_interest = _calculated_interest(report_data)
    fee_debt = _booked_fee_debt(report_data)
    bank_load = _bank_load(report_data)
    next_period_carry = _next_period_carry_total(report_data)
    active_days = _active_day_count(report_data)

    if usage_total <= Decimal("0.00") and payment_total <= Decimal("0.00"):
        return (
            "Bu dönemde limit kullanım veya ödeme hareketi bulunmamaktadır. "
            "Sonraki döneme devreden borç etkisi yoktur."
        )

    principal_sentence = (
        "Ana para dönem sonunda kapanmıştır."
        if payable_principal <= Decimal("0.00")
        else f"Dönem sonunda {_format_currency_amount(payable_principal, currency_code)} ana para sonraki döneme taşınmaktadır."
    )

    return (
        f"Bu dönemde {_format_currency_amount(usage_total, currency_code)} limit kullanılmış, "
        f"{_format_currency_amount(payment_total, currency_code)} ödeme yapılmıştır. "
        f"{principal_sentence} "
        f"Banka yükü {_format_currency_amount(bank_load, currency_code)} seviyesindedir "
        f"(faiz {_format_currency_amount(calculated_interest, currency_code)}, masraf {_format_currency_amount(fee_debt, currency_code)}). "
        f"Limit {active_days} gün faiz üretmiştir. "
        f"Sonraki döneme devreden toplam etki {_format_currency_amount(next_period_carry, currency_code)} olarak izlenmelidir."
    )


def _devir_rows(report_data: dict[str, Any], currency_code: str) -> list[list[str]]:
    return [
        [
            "Ana Para",
            _format_currency_amount(_booked_principal_debt(report_data), currency_code),
            "Kapanmamış ana para yeni dönemde faiz üretmeye devam eder.",
        ],
        [
            "Kayıtlı Faiz / Masraf",
            _format_currency_amount(_booked_interest_fee_debt(report_data), currency_code),
            "Kaydedilmiş banka yüküdür; otomatik olarak faizin faizini üretmez.",
        ],
        [
            "Kaydedilmemiş Faiz",
            _format_currency_amount(_unbooked_calculated_interest(report_data), currency_code),
            "Resmi borç olması için Faizi Kaydet işlemi gerekir.",
        ],
        [
            "Sonraki Döneme Devir",
            _format_currency_amount(_next_period_carry_total(report_data), currency_code),
            "Yeni dönemde takip edilecek toplam borç etkisi.",
        ],
    ]


def _management_findings(report_data: dict[str, Any], currency_code: str) -> tuple[list[list[str]], list[str]]:
    active_days = _active_day_count(report_data)
    calculated_interest = _calculated_interest(report_data)
    valour_gap = _value_date_gap(report_data)
    payable_principal = _booked_principal_debt(report_data)

    rows = [
        [
            "Valör Kuralı",
            "T+1 ödeme valörü",
            "Kullanım aynı gün, ödeme ertesi gün faiz hesabına etki eder.",
        ],
        [
            "Aktif Kullanım Günü",
            f"{active_days} gün",
            "Faize esas borcun sıfırdan büyük olduğu gün sayısıdır.",
        ],
        [
            "En Yüksek Faize Esas Borç",
            _format_currency_amount(_max_interest_basis_debt(report_data), currency_code),
            "Dönem içinde bankanın faiz hesaplayacağı en yüksek günlük bakiye seviyesidir.",
        ],
        [
            "Hesaplanan Faiz",
            _format_currency_amount(calculated_interest, currency_code),
            "Faizi Kaydet yapılmadan resmi borca dönüşmez.",
        ],
        [
            "Ödenebilir Ana Para",
            _format_currency_amount(payable_principal, currency_code),
            "Kayıtlı kullanım ve ödeme sonrası kapatılabilecek ana para borcudur.",
        ],
    ]

    row_styles = [
        "MUTED",
        "WARNING" if active_days > 0 else "MUTED",
        "WARNING",
        "WARNING" if calculated_interest > Decimal("0.00") else "MUTED",
        "RISK" if payable_principal > Decimal("0.00") else "SUCCESS",
    ]

    if valour_gap != Decimal("0.00"):
        rows.append(
            [
                "Valör Farkı",
                _format_currency_amount(valour_gap, currency_code),
                "Faize esas borç ile ödenebilir ana para arasındaki dönem sonu farktır.",
            ]
        )
        row_styles.append("WARNING")

    return rows, row_styles


def _daily_interest_and_movement_table_rows(report_data: dict[str, Any], currency_code: str) -> tuple[list[list[str]], list[str]]:
    table_rows: list[list[str]] = []
    row_styles: list[str] = []

    movements_by_transaction_date: dict[date, list[dict[str, Any]]] = {}

    for movement in _movement_rows(report_data):
        transaction_date = movement.get("transaction_date")

        if isinstance(transaction_date, date):
            movements_by_transaction_date.setdefault(transaction_date, []).append(movement)

    for movement_list in movements_by_transaction_date.values():
        movement_list.sort(
            key=lambda item: (
                item.get("effective_date") or date.min,
                int(item.get("id") or 0),
            )
        )

    for daily_row in _daily_rows(report_data):
        current_day = daily_row.get("date")

        if isinstance(current_day, date):
            for movement in movements_by_transaction_date.get(current_day, []):
                transaction_type = str(movement.get("transaction_type") or "").strip().upper()
                status = str(movement.get("status") or "").strip().upper()
                reference_no = _safe_text(movement.get("reference_no"), "-")
                description = _safe_text(movement.get("description"), "-")
                principal_amount = _decimal_or_zero(movement.get("principal_amount"))
                interest_amount = _decimal_or_zero(movement.get("interest_amount"))
                fee_amount = _decimal_or_zero(movement.get("fee_amount"))
                distribution_parts: list[str] = []

                if principal_amount > Decimal("0.00"):
                    distribution_parts.append(f"Ana: {_format_currency_amount(principal_amount, currency_code)}")
                if interest_amount > Decimal("0.00"):
                    distribution_parts.append(f"Faiz: {_format_currency_amount(interest_amount, currency_code)}")
                if fee_amount > Decimal("0.00"):
                    distribution_parts.append(f"Masraf: {_format_currency_amount(fee_amount, currency_code)}")

                movement_note_parts: list[str] = []

                if transaction_type == "USAGE":
                    movement_note_parts.append("Kullanım aynı gün faize girer")
                elif transaction_type == "PAYMENT":
                    movement_note_parts.append("Ödeme önce masraf/faiz, sonra ana parayı kapatır")
                    movement_note_parts.append("Ana para T+1 valörle düşer")
                elif transaction_type == "INTEREST":
                    movement_note_parts.append("Faiz borca kaydedildi")
                elif transaction_type == "FEE":
                    movement_note_parts.append("Masraf borca kaydedildi")

                movement_note_parts.append(f"Durum: {_transaction_status_text(status)}")

                if reference_no != "-":
                    movement_note_parts.append(f"Ref: {reference_no}")

                if description != "-":
                    movement_note_parts.append(description)

                table_rows.append(
                    [
                        _format_date_tr(movement.get("transaction_date")),
                        "Hareket",
                        _transaction_type_text(transaction_type),
                        _format_currency_amount(movement.get("amount"), movement.get("currency_code") or currency_code),
                        " | ".join(distribution_parts) if distribution_parts else "-",
                        _format_date_tr(movement.get("effective_date")),
                        "-",
                        "-",
                        _shorten_text(" | ".join(movement_note_parts), 72),
                    ]
                )
                row_styles.append(REPORT_ROW_STYLE_BY_TYPE.get(transaction_type, "NORMAL"))

        interest_basis_debt = _decimal_or_zero(daily_row.get("interest_basis_debt"))
        daily_interest = _decimal_or_zero(daily_row.get("daily_interest"))

        if daily_interest > Decimal("0.00"):
            daily_note = "Gün sonu bakiye üzerinden faiz oluştu."
            daily_row_style = "WARNING"
        elif interest_basis_debt > Decimal("0.00"):
            daily_note = "Faize esas borç var; faiz yuvarlama nedeniyle sıfır görünebilir."
            daily_row_style = "WARNING"
        else:
            daily_note = "Faize esas borç yok."
            daily_row_style = "MUTED"

        table_rows.append(
            [
                _format_date_tr(daily_row.get("date")),
                "Gün Sonu",
                "Günlük Faiz",
                "-",
                "-",
                "-",
                _format_currency_amount(interest_basis_debt, daily_row.get("currency_code") or currency_code),
                _format_currency_amount(daily_interest, daily_row.get("currency_code") or currency_code),
                daily_note,
            ]
        )
        row_styles.append(daily_row_style)

    if not table_rows:
        table_rows.append(
            [
                "-",
                "Gün Sonu",
                "Günlük Faiz",
                "-",
                "-",
                "-",
                _format_currency_amount(0, currency_code),
                _format_currency_amount(0, currency_code),
                "Seçili dönem için hareket veya faiz dökümü bulunamadı.",
            ]
        )
        row_styles.append("MUTED")

    return table_rows, row_styles


def _build_management_totals(report_data: dict[str, Any], currency_code: str) -> list[tuple[str, str]]:
    return [
        ("Dönem Kullanımı", _format_currency_amount(report_data.get("period_usage_total"), currency_code)),
        ("Dönem Ödemesi", _format_currency_amount(report_data.get("period_payment_total"), currency_code)),
        ("Ödenebilir Ana Para", _format_currency_amount(_booked_principal_debt(report_data), currency_code)),
        ("Hesaplanan Faiz", _format_currency_amount(_calculated_interest(report_data), currency_code)),
        ("Kaydedilmiş Faiz / Masraf", _format_currency_amount(_booked_interest_fee_debt(report_data), currency_code)),
        ("Sonraki Döneme Devir", _format_currency_amount(_next_period_carry_total(report_data), currency_code)),
        ("Kullanılabilir Limit", _format_currency_amount(_booked_available_limit(report_data), currency_code)),
        ("En Yüksek Faize Esas Borç", _format_currency_amount(_max_interest_basis_debt(report_data), currency_code)),
        ("Ortalama Faize Esas Borç", _format_currency_amount(_average_interest_basis_debt(report_data), currency_code)),
    ]


def _logo_path() -> Path | None:
    app_dir = Path(__file__).resolve().parents[1]
    candidates = [
        app_dir / "assets" / "branding" / "ftm_report_logo.png",
        app_dir / "assets" / "branding" / "ftm_app_icon.png",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _build_first_page_identity(
    *,
    builder: FtmPdfReportBuilder,
    full_name: str,
    report_period: str,
    currency_code: str,
) -> Table:
    logo_file = _logo_path()

    if logo_file is not None:
        logo_cell: Any = Image(str(logo_file), width=34 * mm, height=12 * mm)
    else:
        logo_cell = builder.paragraph("FTM", "title")

    text_cell = Table(
        [
            [builder.paragraph("Yönetici Özeti", "section")],
            [
                builder.paragraph(
                    f"Limit Hesabı: {full_name} | Dönem: {report_period} | Para Birimi: {currency_code}",
                    "subtitle",
                )
            ],
        ],
        colWidths=[builder._content_width() - 42 * mm],
    )
    text_cell.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    table = Table(
        [[logo_cell, text_cell]],
        colWidths=[40 * mm, builder._content_width() - 40 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbe3ef")),
            ]
        )
    )

    return table


def create_credit_limit_period_pdf_report(
    *,
    output_path: str | Path,
    credit_limit_id: int,
    period_start: date,
    period_end: date,
    created_by: Any = None,
) -> str:
    """
    Seçili kredili / limitli mevduat hesabı için yönetici sunumuna uygun PDF raporu üretir.

    Bu fonksiyon veritabanında herhangi bir faiz kaydı oluşturmaz. Yalnızca mevcut limit
    hareketlerini okur, T+1 ödeme valörüyle günlük faiz hesabını üretir ve PDF çıktısı oluşturur.
    """

    if period_end < period_start:
        raise CreditLimitPeriodPdfReportError(
            "Dönem bitiş tarihi başlangıç tarihinden eski olamaz."
        )

    with session_scope() as session:
        credit_limit = session.get(BankAccountCreditLimit, int(credit_limit_id))

        if credit_limit is None:
            raise CreditLimitPeriodPdfReportError(
                f"Kredili / limitli hesap bulunamadı. ID: {credit_limit_id}"
            )

        bank_name, account_name, limit_name, limit_type, currency_code, full_name = _credit_limit_header_text(credit_limit)

        try:
            report_data = calculate_credit_limit_period_report(
                session,
                credit_limit_id=int(credit_limit_id),
                period_start=period_start,
                period_end=period_end,
            )
            report_data["_value_date_summary"] = get_credit_limit_debt_summary(
                session,
                credit_limit_id=int(credit_limit_id),
                as_of_date=period_end,
                apply_value_dates=True,
            )
            report_data["_booked_summary"] = get_credit_limit_debt_summary(
                session,
                credit_limit_id=int(credit_limit_id),
                as_of_date=period_end,
                apply_value_dates=False,
            )
        except CreditFacilityServiceError as exc:
            raise CreditLimitPeriodPdfReportError(str(exc)) from exc

    report_period = _period_text(period_start, period_end)
    created_by_text = _current_user_text(created_by)

    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Kredili / Limitli Mevduat Dönem Raporu",
            report_period=report_period,
            created_by=created_by_text,
            created_at=datetime.now(),
        ),
    )

    elements: list[Any] = []

    elements.append(
        _build_first_page_identity(
            builder=builder,
            full_name=full_name,
            report_period=report_period,
            currency_code=currency_code,
        )
    )
    elements.append(builder.spacer(4))
    elements.append(
        builder.paragraph(
            f"Banka: {bank_name} | Hesap: {account_name} | Tür: {limit_type} | Limit Adı: {limit_name} | Faiz Oranı: % {_format_rate_tr(report_data.get('monthly_interest_rate'))}",
            "subtitle",
        )
    )
    elements.append(builder.spacer(4))
    elements.append(builder.build_summary_cards(_summary_cards(report_data, currency_code), columns=3))
    elements.append(builder.spacer(5))

    elements.append(
        KeepTogether(
            [
                builder.section_title("Kısa Değerlendirme"),
                builder.paragraph(_executive_commentary(report_data, currency_code), "normal"),
                builder.spacer(5),
                builder.build_data_table(
                    headers=["Konu", "Tutar", "Açıklama"],
                    rows=_devir_rows(report_data, currency_code),
                    col_widths=[48, 50, 148],
                    numeric_columns=set(),
                    center_columns={1},
                    row_statuses=["MUTED", "WARNING", "WARNING", "RISK"],
                ),
                builder.spacer(3),
                builder.paragraph(
                    "Özet: Ana para borcu yeni dönemde faiz üretmeye devam eder. Faiz ve masraf ayrı takip edilir; otomatik olarak faizin faizini üretmez.",
                    "small",
                ),
            ]
        )
    )

    elements.append(builder.page_break())

    findings_rows, findings_row_styles = _management_findings(report_data, currency_code)
    elements.append(builder.section_title("Kontrol Toplamları"))
    elements.append(
        builder.paragraph(
            "Bu sayfa, yönetici özetindeki rakamların kontrol amaçlı dökümüdür.",
            "small",
        )
    )
    elements.append(builder.spacer(3))
    elements.append(
        builder.build_data_table(
            headers=["Konu", "Değer", "Not"],
            rows=findings_rows,
            col_widths=[45, 48, 160],
            numeric_columns=set(),
            center_columns={1},
            row_statuses=findings_row_styles,
        )
    )
    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Kontrol Özeti",
            totals=_build_management_totals(report_data, currency_code),
        )
    )

    elements.append(builder.page_break())

    combined_rows, combined_row_styles = _daily_interest_and_movement_table_rows(report_data, currency_code)
    elements.append(builder.section_title("Günlük Faiz Dökümü - Tam Liste"))
    elements.append(
        builder.paragraph(
            "Kullanımlar, ödemeler, masraf/faiz kayıtları ve günlük faiz hesabı tek listede gösterilir. Ödeme satırında işlem tarihi ile faize etki tarihi ayrı izlenir.",
            "small",
        )
    )
    elements.append(builder.spacer(3))
    elements.append(
        builder.build_data_table(
            headers=[
                "Tarih",
                "Kayıt",
                "Tür",
                "Tutar",
                "Dağılım",
                "Faize Etki",
                "Faize Esas Borç",
                "Günlük Faiz",
                "Açıklama",
            ],
            rows=combined_rows,
            col_widths=[19, 22, 29, 29, 39, 23, 33, 28, 58],
            numeric_columns={3, 6, 7},
            center_columns={0, 1, 2, 5},
            row_statuses=combined_row_styles,
        )
    )

    return builder.build(elements)


__all__ = [
    "CreditLimitPeriodPdfReportError",
    "create_credit_limit_period_pdf_report",
]
