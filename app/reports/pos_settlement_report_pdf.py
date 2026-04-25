from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.pos_settlement_report_data import (
    PosSettlementDeviceSummary,
    PosSettlementReportData,
    PosSettlementReportFilter,
    PosSettlementReportRow,
    load_pos_settlement_report_data,
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


def _rate_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.000000")

    try:
        return Decimal(str(value)).quantize(Decimal("0.000001"))
    except Exception:
        return Decimal("0.000000")


def _format_decimal_tr(value: Any) -> str:
    amount = _decimal_or_zero(value)

    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return formatted


def _format_rate_percent(value: Any) -> str:
    rate = _rate_or_zero(value)

    if abs(rate) <= Decimal("1.000000"):
        rate = rate * Decimal("100")

    formatted = f"{rate:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"%{formatted}"


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


def _report_filter_summary_text(report_filter: PosSettlementReportFilter) -> str:
    status_text = _filter_text(
        report_filter.status,
        {
            "ALL": "Tümü",
            "PLANNED": "Planlandı",
            "REALIZED": "Gerçekleşti",
            "CANCELLED": "İptal Edildi",
            "MISMATCH": "Fark Var",
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
        f"Durum: {status_text} | "
        f"Para Birimi: {currency_text}"
    )


def _summary_cards(report_data: PosSettlementReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    return [
        FtmSummaryCard(
            title="Toplam POS Kaydı",
            value=f"{summary.total_count} kayıt",
            hint="Seçilen filtrelere uyan toplam POS mutabakat kaydı",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Brüt POS Toplamı",
            value=_format_currency_totals_inline(summary.gross_totals),
            hint="Komisyon kesilmeden önceki toplam POS tutarı",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Komisyon Toplamı",
            value=_format_currency_totals_inline(summary.commission_totals),
            hint="POS komisyon kesintileri toplamı",
            card_type="warning",
        ),
        FtmSummaryCard(
            title="Beklenen Net",
            value=_format_currency_totals_inline(summary.expected_net_totals),
            hint="Bankaya yatması beklenen net tutar",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Gerçekleşen Net",
            value=_format_currency_totals_inline(summary.actual_net_totals),
            hint="Bankaya gerçekleşen net yatış toplamı",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Fark Toplamı",
            value=_format_currency_totals_inline(summary.difference_totals),
            hint="Beklenen ve gerçekleşen net tutar farkı",
            card_type="risk" if summary.mismatch_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Bekleyen / Planlanan",
            value=f"{summary.planned_count} kayıt",
            hint="Henüz gerçekleşmemiş POS yatışları",
            card_type="warning" if summary.planned_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Farklı Mutabakat",
            value=f"{summary.mismatch_count} kayıt",
            hint="Tutar farkı veya uyuşmazlık içeren kayıtlar",
            card_type="risk" if summary.mismatch_count > 0 else "normal",
        ),
    ]


def _detail_table_headers() -> list[str]:
    return [
        "İşlem",
        "Beklenen",
        "Gerçekleşen",
        "POS",
        "Banka",
        "Brüt",
        "Kom.",
        "Bek. Net",
        "Ger. Net",
        "Fark",
        "Durum",
    ]


def _pos_device_text(row: PosSettlementReportRow) -> str:
    if row.terminal_no:
        return f"{row.pos_device_name} / {row.terminal_no}"

    return row.pos_device_name


def _bank_text(row: PosSettlementReportRow) -> str:
    return f"{row.bank_name} / {row.account_name}"


def _actual_net_text(row: PosSettlementReportRow) -> str:
    if row.actual_net_amount is None:
        return "-"

    return _format_decimal_tr(row.actual_net_amount)


def _detail_table_row(row: PosSettlementReportRow) -> list[str]:
    return [
        _format_date_tr(row.transaction_date),
        _format_date_tr(row.expected_settlement_date),
        _format_date_tr(row.realized_settlement_date),
        _shorten_text(_pos_device_text(row), 34),
        _shorten_text(_bank_text(row), 32),
        _format_decimal_tr(row.gross_amount),
        _format_decimal_tr(row.commission_amount),
        _format_decimal_tr(row.net_amount),
        _actual_net_text(row),
        _format_decimal_tr(row.difference_amount),
        row.status_text,
    ]


def _detail_table_rows(report_data: PosSettlementReportData) -> list[list[str]]:
    return [
        _detail_table_row(row)
        for row in report_data.rows
    ]


def _detail_table_row_statuses(report_data: PosSettlementReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _device_summary_headers() -> list[str]:
    return [
        "POS",
        "Banka / Hesap",
        "Kayıt",
        "Brüt",
        "Komisyon",
        "Bek. Net",
        "Ger. Net",
        "Fark",
    ]


def _device_summary_pos_text(device_summary: PosSettlementDeviceSummary) -> str:
    if device_summary.terminal_no:
        return f"{device_summary.pos_device_name} / {device_summary.terminal_no}"

    return device_summary.pos_device_name


def _device_summary_bank_text(device_summary: PosSettlementDeviceSummary) -> str:
    return f"{device_summary.bank_name} / {device_summary.account_name}"


def _device_summary_row(device_summary: PosSettlementDeviceSummary) -> list[str]:
    return [
        _shorten_text(_device_summary_pos_text(device_summary), 38),
        _shorten_text(_device_summary_bank_text(device_summary), 38),
        str(device_summary.record_count),
        _format_currency_totals_inline(device_summary.gross_totals),
        _format_currency_totals_inline(device_summary.commission_totals),
        _format_currency_totals_inline(device_summary.expected_net_totals),
        _format_currency_totals_inline(device_summary.actual_net_totals),
        _format_currency_totals_inline(device_summary.difference_totals),
    ]


def _device_summary_rows(report_data: PosSettlementReportData) -> list[list[str]]:
    return [
        _device_summary_row(device_summary)
        for device_summary in report_data.summary.device_summaries
    ]


def _totals_table_rows(report_data: PosSettlementReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("Toplam POS Kaydı", f"{summary.total_count} kayıt"),
        ("Planlanan", f"{summary.planned_count} kayıt"),
        ("Gerçekleşen", f"{summary.realized_count} kayıt"),
        ("Farklı Mutabakat", f"{summary.mismatch_count} kayıt"),
        ("İptal Edilen", f"{summary.cancelled_count} kayıt"),
        ("Brüt Toplam", _format_currency_totals_inline(summary.gross_totals)),
        ("Komisyon Toplamı", _format_currency_totals_inline(summary.commission_totals)),
        ("Beklenen Net", _format_currency_totals_inline(summary.expected_net_totals)),
        ("Gerçekleşen Net", _format_currency_totals_inline(summary.actual_net_totals)),
        ("Fark Toplamı", _format_currency_totals_inline(summary.difference_totals)),
    ]


def build_pos_settlement_report_pdf(
    *,
    output_path: str | Path,
    report_data: PosSettlementReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="POS Mutabakat Raporu",
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
    elements.append(builder.section_title("POS Mutabakat Detayları"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun POS mutabakat kaydı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_detail_table_headers(),
                rows=_detail_table_rows(report_data),
                col_widths=[18, 18, 18, 32, 28, 24, 24, 27, 27, 24, 22],
                numeric_columns={5, 6, 7, 8, 9},
                center_columns={0, 1, 2, 10},
                row_statuses=_detail_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("POS Cihazı Bazlı Özet"))

    if not report_data.summary.device_summaries:
        elements.append(
            builder.paragraph(
                "Rapor döneminde hareket gören POS cihazı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_device_summary_headers(),
                rows=_device_summary_rows(report_data),
                col_widths=[42, 36, 15, 35, 32, 38, 38, 32],
                numeric_columns={3, 4, 5, 6, 7},
                center_columns={2},
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="POS Mutabakat Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_pos_settlement_report_pdf(
    *,
    output_path: str | Path,
    report_filter: PosSettlementReportFilter,
    created_by: str,
) -> str:
    report_data = load_pos_settlement_report_data(report_filter)

    return build_pos_settlement_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_pos_settlement_report_pdf(
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

    report_filter = PosSettlementReportFilter(
        start_date=start_date,
        end_date=end_date,
        pos_device_id=None,
        bank_id=None,
        bank_account_id=None,
        status="ALL",
        currency_code="ALL",
    )

    return create_pos_settlement_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )