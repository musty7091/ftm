from __future__ import annotations

from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.check_due_report_data import (
    CheckDueReportData,
    CheckDueReportFilter,
    CheckDueReportRow,
    load_check_due_report_data,
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


def _format_date_tr(value: date) -> str:
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


def _report_filter_summary_text(report_filter: CheckDueReportFilter) -> str:
    check_type_text = _filter_text(
        report_filter.check_type,
        {
            "ALL": "Tümü",
            "RECEIVED": "Alınan Çekler",
            "ISSUED": "Yazılan Çekler",
        },
    )

    status_group_text = _filter_text(
        report_filter.status_group,
        {
            "ALL": "Tümü",
            "PENDING": "Bekleyen",
            "CLOSED": "Sonuçlanan",
            "PROBLEM": "Problemli",
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

    return (
        f"Çek Türü: {check_type_text} | "
        f"Durum: {status_group_text} | "
        f"Para Birimi: {currency_text}"
    )


def _summary_cards(report_data: CheckDueReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    return [
        FtmSummaryCard(
            title="Toplam Alınan Çek",
            value=f"{summary.received_count} kayıt",
            hint=_format_currency_totals_inline(summary.received_totals),
            card_type="success",
        ),
        FtmSummaryCard(
            title="Toplam Yazılan Çek",
            value=f"{summary.issued_count} kayıt",
            hint=_format_currency_totals_inline(summary.issued_totals),
            card_type="risk",
        ),
        FtmSummaryCard(
            title="Bekleyen Çek",
            value=f"{summary.pending_count} kayıt",
            hint=_format_currency_totals_inline(summary.pending_totals),
            card_type="warning",
        ),
        FtmSummaryCard(
            title="Problemli Çek",
            value=f"{summary.problem_count} kayıt",
            hint=_format_currency_totals_inline(summary.problem_totals),
            card_type="risk" if summary.problem_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Vadesi Geçmiş",
            value=f"{summary.overdue_count} kayıt",
            hint=_format_currency_totals_inline(summary.overdue_totals),
            card_type="risk" if summary.overdue_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Bugün Vadeli",
            value=f"{summary.today_count} kayıt",
            hint=_format_currency_totals_inline(summary.today_totals),
            card_type="warning" if summary.today_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="30 Gün İçinde",
            value=f"{summary.next_30_count} kayıt",
            hint=_format_currency_totals_inline(summary.next_30_totals),
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Net Nakit Etkisi",
            value=_format_currency_totals_inline(summary.net_effect_totals),
            hint="Alınan çek toplamı - yazılan çek toplamı",
            card_type="success",
        ),
    ]


def _detail_table_headers() -> list[str]:
    return [
        "Tür",
        "Durum",
        "Taraf",
        "Çek No",
        "Vade",
        "Kalan",
        "Tutar",
        "Para",
        "Referans",
        "Açıklama",
    ]


def _detail_table_row(row: CheckDueReportRow) -> list[str]:
    return [
        row.check_type_text,
        row.status_group_text,
        _shorten_text(row.party_name, 34),
        _shorten_text(row.check_number, 18),
        _format_date_tr(row.due_date),
        row.days_text,
        _format_decimal_tr(row.amount),
        row.currency_code,
        _shorten_text(row.reference_no, 20),
        _shorten_text(row.description, 48),
    ]


def _detail_table_rows(report_data: CheckDueReportData) -> list[list[str]]:
    return [
        _detail_table_row(row)
        for row in report_data.rows
    ]


def _detail_table_row_statuses(report_data: CheckDueReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _totals_table_rows(report_data: CheckDueReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("Toplam Kayıt", f"{summary.total_count} kayıt"),
        ("Toplam Alınan", _format_currency_totals_inline(summary.received_totals)),
        ("Toplam Yazılan", _format_currency_totals_inline(summary.issued_totals)),
        ("Toplam Bekleyen", _format_currency_totals_inline(summary.pending_totals)),
        ("Toplam Sonuçlanan", _format_currency_totals_inline(summary.closed_totals)),
        ("Toplam Problemli", _format_currency_totals_inline(summary.problem_totals)),
        ("Net Nakit Etkisi", _format_currency_totals_inline(summary.net_effect_totals)),
    ]


def build_check_due_report_pdf(
    *,
    output_path: str | Path,
    report_data: CheckDueReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Vade Bazlı Çek Raporu",
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
    elements.append(builder.section_title("Vade Bazlı Detay Liste"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun çek kaydı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_detail_table_headers(),
                rows=_detail_table_rows(report_data),
                col_widths=[17, 22, 42, 22, 22, 21, 28, 16, 24, 50],
                numeric_columns={6},
                center_columns={0, 1, 4, 5, 7},
                row_statuses=_detail_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Rapor Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_check_due_report_pdf(
    *,
    output_path: str | Path,
    report_filter: CheckDueReportFilter,
    created_by: str,
) -> str:
    report_data = load_check_due_report_data(report_filter)

    return build_check_due_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_next_30_days_check_due_report_pdf(
    *,
    output_path: str | Path,
    created_by: str = "FTM Kullanıcısı",
) -> str:
    today = date.today()

    report_filter = CheckDueReportFilter(
        start_date=today,
        end_date=today + timedelta(days=30),
        check_type="ALL",
        status_group="ALL",
        currency_code="ALL",
    )

    return create_check_due_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )