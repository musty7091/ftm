from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from reportlab.platypus import KeepTogether

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
)


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


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


def _credit_limit_header_text(credit_limit: BankAccountCreditLimit) -> tuple[str, str, str, str]:
    bank_account = credit_limit.bank_account
    bank_name = "-"
    account_name = "-"

    if bank_account is not None:
        account_name = bank_account.account_name or "-"

        if getattr(bank_account, "bank", None) is not None:
            bank_name = bank_account.bank.name or "-"

    limit_name = credit_limit.limit_name or "-"
    currency_code = credit_limit.currency_code.value if credit_limit.currency_code else "TRY"
    full_name = f"{bank_name} / {account_name} / {limit_name}"

    return bank_name, account_name, limit_name, currency_code, full_name


def _report_summary_value(report_data: dict[str, Any], key: str) -> Decimal:
    return _decimal_or_zero(report_data.get(key))


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


def _summary_cards(report_data: dict[str, Any], currency_code: str) -> list[FtmSummaryCard]:
    ending_principal = _report_summary_value(report_data, "ending_interest_basis_debt")
    calculated_interest = _report_summary_value(report_data, "calculated_interest_total")
    total_period_debt = ending_principal + calculated_interest
    available_limit = _report_summary_value(report_data, "limit_amount") - ending_principal

    if available_limit < Decimal("0.00"):
        available_limit = Decimal("0.00")

    return [
        FtmSummaryCard(
            title="Toplam Limit",
            value=_format_currency_amount(report_data.get("limit_amount"), currency_code),
            hint="Tanımlı limit tutarı",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Dönem Kullanımı",
            value=_format_currency_amount(report_data.get("period_usage_total"), currency_code),
            hint="Dönem içi limit kullanımları",
            card_type="risk" if _report_summary_value(report_data, "period_usage_total") > Decimal("0.00") else "normal",
        ),
        FtmSummaryCard(
            title="Dönem Ödemesi",
            value=_format_currency_amount(report_data.get("period_payment_total"), currency_code),
            hint="Ödemeler T+1 valörle dikkate alınır",
            card_type="success" if _report_summary_value(report_data, "period_payment_total") > Decimal("0.00") else "normal",
        ),
        FtmSummaryCard(
            title="Dönem Sonu Ana Para",
            value=_format_currency_amount(ending_principal, currency_code),
            hint="Faize esas kalan ana para borcu",
            card_type="risk" if ending_principal > Decimal("0.00") else "success",
        ),
        FtmSummaryCard(
            title="Hesaplanan Faiz",
            value=_format_currency_amount(calculated_interest, currency_code),
            hint=f"Aylık oran: % {_format_rate_tr(report_data.get('monthly_interest_rate'))}",
            card_type="warning" if calculated_interest > Decimal("0.00") else "normal",
        ),
        FtmSummaryCard(
            title="Toplam Dönem Borcu",
            value=_format_currency_amount(total_period_debt, currency_code),
            hint="Ana para + hesaplanan faiz",
            card_type="risk" if total_period_debt > Decimal("0.00") else "success",
        ),
        FtmSummaryCard(
            title="Aktif Kullanım Günü",
            value=f"{_active_day_count(report_data)} gün",
            hint="Faize esas borcun sıfırdan büyük olduğu gün sayısı",
            card_type="warning" if _active_day_count(report_data) > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Kullanılabilir Limit",
            value=_format_currency_amount(available_limit, currency_code),
            hint="Limit - dönem sonu ana para",
            card_type="success" if available_limit > Decimal("0.00") else "risk",
        ),
    ]


def _executive_commentary(report_data: dict[str, Any], currency_code: str) -> str:
    usage_total = _report_summary_value(report_data, "period_usage_total")
    payment_total = _report_summary_value(report_data, "period_payment_total")
    ending_principal = _report_summary_value(report_data, "ending_interest_basis_debt")
    calculated_interest = _report_summary_value(report_data, "calculated_interest_total")
    active_days = _active_day_count(report_data)
    max_debt = _max_interest_basis_debt(report_data)

    if usage_total <= Decimal("0.00") and payment_total <= Decimal("0.00"):
        return (
            "Seçili dönemde limit hareketi bulunmamaktadır. Bu nedenle günlük faiz hesabı dönem boyunca sıfır borç üzerinden ilerlemiştir."
        )

    sentences = [
        f"Dönem içinde {_format_currency_amount(usage_total, currency_code)} limit kullanımı ve {_format_currency_amount(payment_total, currency_code)} limit ödemesi kaydedilmiştir.",
        f"Ödeme hareketleri banka valör mantığına uygun olarak ertesi gün faize etki eder; bu nedenle aynı gün kullanılıp kapatılan tutarlar için en az 1 günlük faiz oluşabilir.",
        f"Bu dönemde faize esas borç {active_days} gün boyunca sıfırın üzerinde kalmış, en yüksek faize esas borç {_format_currency_amount(max_debt, currency_code)} seviyesine ulaşmıştır.",
        f"Dönem sonunda ana para borcu {_format_currency_amount(ending_principal, currency_code)}, hesaplanan faiz ise {_format_currency_amount(calculated_interest, currency_code)} olarak hesaplanmıştır.",
    ]

    return " ".join(sentences)


def _movements_table_rows(report_data: dict[str, Any], currency_code: str) -> tuple[list[list[str]], list[str]]:
    table_rows: list[list[str]] = []
    row_styles: list[str] = []

    rows = sorted(
        _movement_rows(report_data),
        key=lambda item: (
            item.get("transaction_date") or date.min,
            item.get("effective_date") or date.min,
            int(item.get("id") or 0),
        ),
    )

    for row in rows:
        transaction_type = str(row.get("transaction_type") or "").strip().upper()
        status = str(row.get("status") or "").strip().upper()

        table_rows.append(
            [
                _format_date_tr(row.get("transaction_date")),
                _format_date_tr(row.get("effective_date")),
                _transaction_type_text(transaction_type),
                _format_currency_amount(row.get("amount"), row.get("currency_code") or currency_code),
                _transaction_status_text(status),
                _shorten_text(row.get("reference_no"), 18),
                _shorten_text(row.get("description"), 58),
            ]
        )
        row_styles.append(REPORT_ROW_STYLE_BY_TYPE.get(transaction_type, "NORMAL"))

    if not table_rows:
        table_rows.append(["-", "-", "Hareket yok", "0,00", "-", "-", "Seçili dönemde hareket bulunamadı."])
        row_styles.append("MUTED")

    return table_rows, row_styles


def _daily_interest_table_rows(report_data: dict[str, Any], currency_code: str) -> tuple[list[list[str]], list[str]]:
    table_rows: list[list[str]] = []
    row_styles: list[str] = []

    for row in _daily_rows(report_data):
        interest_basis_debt = _decimal_or_zero(row.get("interest_basis_debt"))
        daily_interest = _decimal_or_zero(row.get("daily_interest"))

        table_rows.append(
            [
                _format_date_tr(row.get("date")),
                _format_currency_amount(interest_basis_debt, row.get("currency_code") or currency_code),
                _format_currency_amount(daily_interest, row.get("currency_code") or currency_code),
            ]
        )
        row_styles.append("WARNING" if daily_interest > Decimal("0.00") else "MUTED")

    if not table_rows:
        table_rows.append(["-", _format_currency_amount(0, currency_code), _format_currency_amount(0, currency_code)])
        row_styles.append("MUTED")

    return table_rows, row_styles


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
                movement_note_parts = [f"Durum: {_transaction_status_text(status)}"]

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
            daily_note = "Faiz oluştu. Günlük hesap, faize etki etmiş hareketlerden sonra hesaplandı."
            daily_row_style = "WARNING"
        elif interest_basis_debt > Decimal("0.00"):
            daily_note = "Faize esas borç var; günlük faiz tutarı yuvarlama nedeniyle sıfır görünebilir."
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
                _format_currency_amount(0, currency_code),
                _format_currency_amount(0, currency_code),
                "Seçili dönem için hareket veya faiz dökümü bulunamadı.",
            ]
        )
        row_styles.append("MUTED")

    return table_rows, row_styles


def _daily_interest_focus_rows(report_data: dict[str, Any], currency_code: str) -> tuple[list[list[str]], list[str]]:
    focus_rows = _active_daily_rows(report_data)

    if not focus_rows:
        return [
            ["-", _format_currency_amount(0, currency_code), _format_currency_amount(0, currency_code)]
        ], ["MUTED"]

    table_rows: list[list[str]] = []
    row_styles: list[str] = []

    for row in focus_rows:
        daily_interest = _decimal_or_zero(row.get("daily_interest"))
        table_rows.append(
            [
                _format_date_tr(row.get("date")),
                _format_currency_amount(row.get("interest_basis_debt"), row.get("currency_code") or currency_code),
                _format_currency_amount(daily_interest, row.get("currency_code") or currency_code),
            ]
        )
        row_styles.append("WARNING" if daily_interest > Decimal("0.00") else "MUTED")

    return table_rows, row_styles


def _build_management_totals(report_data: dict[str, Any], currency_code: str) -> list[tuple[str, str]]:
    ending_principal = _report_summary_value(report_data, "ending_interest_basis_debt")
    calculated_interest = _report_summary_value(report_data, "calculated_interest_total")
    total_period_debt = ending_principal + calculated_interest

    return [
        ("Dönem Başı Borç", _format_currency_amount(report_data.get("opening_interest_basis_debt"), currency_code)),
        ("Dönem Kullanımı", _format_currency_amount(report_data.get("period_usage_total"), currency_code)),
        ("Dönem Ödemesi", _format_currency_amount(report_data.get("period_payment_total"), currency_code)),
        ("Dönem Sonu Ana Para", _format_currency_amount(ending_principal, currency_code)),
        ("Hesaplanan Faiz", _format_currency_amount(calculated_interest, currency_code)),
        ("Toplam Dönem Borcu", _format_currency_amount(total_period_debt, currency_code)),
        ("En Yüksek Faize Esas Borç", _format_currency_amount(_max_interest_basis_debt(report_data), currency_code)),
        ("Ortalama Faize Esas Borç", _format_currency_amount(_average_interest_basis_debt(report_data), currency_code)),
    ]


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

        bank_name, account_name, limit_name, currency_code, full_name = _credit_limit_header_text(credit_limit)

        try:
            report_data = calculate_credit_limit_period_report(
                session,
                credit_limit_id=int(credit_limit_id),
                period_start=period_start,
                period_end=period_end,
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

    elements.append(builder.section_title("Yönetici Özeti"))
    elements.append(
        builder.paragraph(
            f"Limit Hesabı: {full_name} | Banka: {bank_name} | Hesap: {account_name} | Limit Tipi: {limit_name}",
            "subtitle",
        )
    )
    elements.append(builder.spacer(4))
    elements.append(builder.build_summary_cards(_summary_cards(report_data, currency_code), columns=4))
    elements.append(builder.spacer(5))

    elements.append(
        KeepTogether(
            [
                builder.section_title("Finansal Değerlendirme"),
                builder.paragraph(_executive_commentary(report_data, currency_code), "normal"),
                builder.spacer(4),
                builder.build_total_table(
                    title="Yönetici Kontrol Toplamları",
                    totals=_build_management_totals(report_data, currency_code),
                ),
            ]
        )
    )

    elements.append(builder.spacer(5))
    elements.append(
        builder.paragraph(
            "Valör notu: Limit kullanımı aynı gün faize girer. Limit ödemesi banka uygulamasına uygun olarak ertesi gün borçtan düşer. Bu nedenle aynı gün kullanılıp kapatılan limitlerde dahi en az 1 günlük faiz oluşabilir.",
            "small",
        )
    )

    elements.append(builder.page_break())

    combined_rows, combined_row_styles = _daily_interest_and_movement_table_rows(report_data, currency_code)
    elements.append(builder.section_title("Günlük Faiz Dökümü - Tam Liste"))
    elements.append(
        builder.paragraph(
            "Bu tek tabloda dönem içindeki limit kullanımları, limit ödemeleri ve her günün faize esas borç/günlük faiz hesabı birlikte gösterilir. Ödeme satırlarında işlem tarihi ile faize etki tarihi ayrı görünür; T+1 valör farkı buradan takip edilir.",
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
                "Faize Etki",
                "Faize Esas Borç",
                "Günlük Faiz",
                "Açıklama",
            ],
            rows=combined_rows,
            col_widths=[20, 24, 31, 30, 24, 35, 30, 66],
            numeric_columns={3, 5, 6},
            center_columns={0, 1, 2, 4},
            row_statuses=combined_row_styles,
        )
    )

    return builder.build(elements)


__all__ = [
    "CreditLimitPeriodPdfReportError",
    "create_credit_limit_period_pdf_report",
]
