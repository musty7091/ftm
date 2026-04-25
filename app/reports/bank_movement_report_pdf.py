from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.bank_movement_report_data import (
    BankMovementAccountSummary,
    BankMovementReportData,
    BankMovementReportFilter,
    BankMovementReportRow,
    load_bank_movement_report_data,
)
from app.reports.report_pdf_base import (
    FtmPdfReportBuilder,
    FtmReportMeta,
    FtmSummaryCard,
)


CURRENCY_DISPLAY_ORDER = ["TRY", "USD", "EUR", "GBP"]


def _decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")

    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


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


def _currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return (
            CURRENCY_DISPLAY_ORDER.index(normalized_currency_code),
            normalized_currency_code,
        )

    return (999, normalized_currency_code)


def _format_currency_totals_inline(currency_totals: dict[str, Decimal]) -> str:
    if not currency_totals:
        return "0,00 TL"

    parts: list[str] = []

    for currency_code in sorted(currency_totals.keys(), key=_currency_sort_key):
        parts.append(
            _format_currency_amount(
                currency_totals[currency_code],
                currency_code,
            )
        )

    return " / ".join(parts)


def _format_date_tr(value: date | None) -> str:
    if value is None:
        return "-"

    return value.strftime("%d.%m.%Y")


def _shorten_text(value: Any, max_length: int) -> str:
    text = str(value or "").strip()

    if not text:
        return "-"

    if len(text) <= max_length:
        return text

    return text[: max(0, max_length - 3)].rstrip() + "..."


def _filter_text(value: str, mapping: dict[str, str]) -> str:
    normalized_value = str(value or "ALL").strip().upper()

    return mapping.get(normalized_value, normalized_value)


def _report_filter_summary_text(report_filter: BankMovementReportFilter) -> str:
    direction_text = _filter_text(
        report_filter.direction,
        {
            "ALL": "Tümü",
            "IN": "Giriş",
            "OUT": "Çıkış",
        },
    )

    status_text = _filter_text(
        report_filter.status,
        {
            "ALL": "Tümü",
            "PLANNED": "Planlandı",
            "REALIZED": "Gerçekleşti",
            "CANCELLED": "İptal Edildi",
        },
    )

    currency_text = _filter_text(
        report_filter.currency_code,
        {
            "ALL": "Tümü",
            "TRY": "TRY",
            "USD": "USD",
            "EUR": "EUR",
            "GBP": "GBP",
        },
    )

    source_type_text = _filter_text(
        report_filter.source_type,
        {
            "ALL": "Tümü",
            "OPENING_BALANCE": "Açılış Bakiyesi",
            "CASH_DEPOSIT": "Nakit Yatırma",
            "BANK_TRANSFER": "Banka Transferi",
            "ISSUED_CHECK": "Yazılan Çek",
            "RECEIVED_CHECK": "Alınan Çek",
            "POS_SETTLEMENT": "POS Yatışı",
            "MANUAL_ADJUSTMENT": "Manuel Düzeltme",
            "OTHER": "Diğer",
        },
    )

    return (
        f"Yön: {direction_text} | "
        f"Durum: {status_text} | "
        f"Para Birimi: {currency_text} | "
        f"Kaynak: {source_type_text}"
    )


def _summary_cards(report_data: BankMovementReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    return [
        FtmSummaryCard(
            title="Toplam Hareket",
            value=f"{summary.total_count} kayıt",
            hint="Seçilen filtrelere uyan toplam banka hareketi",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Toplam Giriş",
            value=f"{summary.incoming_count} kayıt",
            hint=_format_currency_totals_inline(summary.incoming_totals),
            card_type="success",
        ),
        FtmSummaryCard(
            title="Toplam Çıkış",
            value=f"{summary.outgoing_count} kayıt",
            hint=_format_currency_totals_inline(summary.outgoing_totals),
            card_type="risk" if summary.outgoing_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Net Etki",
            value=_format_currency_totals_inline(summary.net_totals),
            hint="Giriş toplamı - çıkış toplamı",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Gerçekleşen",
            value=f"{summary.realized_count} kayıt",
            hint=_format_currency_totals_inline(summary.realized_totals),
            card_type="success",
        ),
        FtmSummaryCard(
            title="Planlanan",
            value=f"{summary.planned_count} kayıt",
            hint=_format_currency_totals_inline(summary.planned_totals),
            card_type="warning" if summary.planned_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="İptal Edilen",
            value=f"{summary.cancelled_count} kayıt",
            hint=_format_currency_totals_inline(summary.cancelled_totals),
            card_type="muted" if summary.cancelled_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Hesap Sayısı",
            value=f"{len(summary.account_summaries)} hesap",
            hint="Rapor döneminde hareket gören banka hesapları",
            card_type="normal",
        ),
    ]


def _detail_table_headers() -> list[str]:
    return [
        "Tarih",
        "Banka",
        "Hesap",
        "Yön",
        "Durum",
        "Kaynak",
        "Tutar",
        "Para",
        "Referans",
        "Açıklama",
    ]


def _detail_table_row(row: BankMovementReportRow) -> list[str]:
    return [
        _format_date_tr(row.transaction_date),
        _shorten_text(row.bank_name, 30),
        _shorten_text(row.account_name, 32),
        row.direction_text,
        row.status_text,
        _shorten_text(row.source_type_text, 24),
        _format_decimal_tr(row.amount),
        row.currency_code,
        _shorten_text(row.reference_no, 24),
        _shorten_text(row.description, 50),
    ]


def _detail_table_rows(report_data: BankMovementReportData) -> list[list[str]]:
    return [
        _detail_table_row(row)
        for row in report_data.rows
    ]


def _detail_table_row_statuses(report_data: BankMovementReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _account_summary_headers() -> list[str]:
    return [
        "Banka",
        "Hesap",
        "Para",
        "Kayıt",
        "Giriş",
        "Çıkış",
        "Net",
    ]


def _account_summary_row(account_summary: BankMovementAccountSummary) -> list[str]:
    return [
        _shorten_text(account_summary.bank_name, 34),
        _shorten_text(account_summary.account_name, 38),
        account_summary.currency_code,
        str(account_summary.transaction_count),
        _format_currency_totals_inline(account_summary.incoming_totals),
        _format_currency_totals_inline(account_summary.outgoing_totals),
        _format_currency_totals_inline(account_summary.net_totals),
    ]


def _account_summary_rows(report_data: BankMovementReportData) -> list[list[str]]:
    return [
        _account_summary_row(account_summary)
        for account_summary in report_data.summary.account_summaries
    ]


def _totals_table_rows(report_data: BankMovementReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("Toplam Hareket", f"{summary.total_count} kayıt"),
        ("Toplam Giriş", _format_currency_totals_inline(summary.incoming_totals)),
        ("Toplam Çıkış", _format_currency_totals_inline(summary.outgoing_totals)),
        ("Net Etki", _format_currency_totals_inline(summary.net_totals)),
        ("Gerçekleşen", _format_currency_totals_inline(summary.realized_totals)),
        ("Planlanan", _format_currency_totals_inline(summary.planned_totals)),
        ("İptal Edilen", _format_currency_totals_inline(summary.cancelled_totals)),
    ]


def build_bank_movement_report_pdf(
    *,
    output_path: str | Path,
    report_data: BankMovementReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Banka Hareket Raporu",
            report_period=report_data.report_period_text,
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    elements: list[Any] = []

    elements.append(builder.section_title("Rapor Filtreleri"))
    elements.append(builder.paragraph(_report_filter_summary_text(report_data.filters), "normal"))
    elements.append(builder.spacer(4))

    elements.append(builder.section_title("Yönetici Özeti"))
    elements.append(
        builder.build_summary_cards(
            _summary_cards(report_data),
            columns=4,
        )
    )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Banka Hareket Detayları"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun banka hareketi bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_detail_table_headers(),
                rows=_detail_table_rows(report_data),
                col_widths=[20, 33, 36, 18, 22, 27, 28, 15, 25, 48],
                numeric_columns={6},
                center_columns={0, 3, 4, 5, 7},
                row_statuses=_detail_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Hesap Bazlı Özet"))

    if not report_data.summary.account_summaries:
        elements.append(
            builder.paragraph(
                "Rapor döneminde hareket gören banka hesabı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_account_summary_headers(),
                rows=_account_summary_rows(report_data),
                col_widths=[42, 48, 16, 16, 45, 45, 45],
                numeric_columns={4, 5, 6},
                center_columns={2, 3},
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Banka Hareket Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_bank_movement_report_pdf(
    *,
    output_path: str | Path,
    report_filter: BankMovementReportFilter,
    created_by: str,
) -> str:
    report_data = load_bank_movement_report_data(report_filter)

    return build_bank_movement_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_bank_movement_report_pdf(
    *,
    output_path: str | Path,
    created_by: str = "FTM Kullanıcısı",
) -> str:
    today = date.today()
    start_date = date(today.year, today.month, 1)

    if today.month == 12:
        end_date = date(today.year, 12, 31)
    else:
        end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)

    report_filter = BankMovementReportFilter(
        start_date=start_date,
        end_date=end_date,
        bank_id=None,
        bank_account_id=None,
        direction="ALL",
        status="ALL",
        currency_code="ALL",
        source_type="ALL",
    )

    return create_bank_movement_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )