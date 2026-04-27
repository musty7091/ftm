from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.discount_batch_report_data import (
    DiscountBatchBankSummary,
    DiscountBatchReportBatchRow,
    DiscountBatchReportData,
    DiscountBatchReportFilter,
    DiscountBatchReportItemRow,
    load_discount_batch_report_data,
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
    rate_value = _rate_or_zero(value)
    percent_value = (rate_value * Decimal("100")).quantize(Decimal("0.01"))

    return f"%{_format_decimal_tr(percent_value)}"


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


def _report_filter_summary_text(report_filter: DiscountBatchReportFilter) -> str:
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

    bank_text = "Tümü" if report_filter.bank_id is None else f"Banka ID: {report_filter.bank_id}"
    account_text = "Tümü" if report_filter.bank_account_id is None else f"Hesap ID: {report_filter.bank_account_id}"

    return (
        f"Banka: {bank_text} | "
        f"Hesap: {account_text} | "
        f"Para Birimi: {currency_text}"
    )


def _summary_cards(report_data: DiscountBatchReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    total_gross_text = _format_currency_totals_inline(summary.total_gross_amount_by_currency)
    total_expense_text = _format_currency_totals_inline(summary.total_discount_expense_by_currency)
    net_bank_text = _format_currency_totals_inline(summary.net_bank_amount_by_currency)
    interest_text = _format_currency_totals_inline(summary.total_interest_expense_by_currency)
    commission_text = _format_currency_totals_inline(summary.total_commission_by_currency)
    bsiv_text = _format_currency_totals_inline(summary.total_bsiv_by_currency)

    return [
        FtmSummaryCard(
            title="İskonto Paketi",
            value=f"{summary.total_batch_count} paket",
            hint="Seçilen dönemdeki toplam iskonto paketi",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Çek Sayısı",
            value=f"{summary.total_check_count} çek",
            hint="İskonto paketlerine bağlı toplam çek",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Brüt Çek Tutarı",
            value=total_gross_text,
            hint="İskontoya verilen çeklerin brüt toplamı",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Toplam Kesinti",
            value=total_expense_text,
            hint="Faiz + komisyon + BSMV toplamı",
            card_type="risk" if summary.total_check_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Net Banka Tutarı",
            value=net_bank_text,
            hint="Bankaya geçen net tutar",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Faiz Gideri",
            value=interest_text,
            hint="Toplam iskonto faiz gideri",
            card_type="warning" if summary.total_check_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Komisyon",
            value=commission_text,
            hint="Toplam banka komisyonu",
            card_type="warning" if summary.total_check_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="BSMV",
            value=bsiv_text,
            hint=f"Ortalama vade: {_format_decimal_tr(summary.average_days_to_due)} gün",
            card_type="warning" if summary.total_check_count > 0 else "normal",
        ),
    ]


def _batch_table_headers() -> list[str]:
    return [
        "Tarih",
        "Banka",
        "Hesap",
        "Paket",
        "Çek",
        "Ort. Vade",
        "Brüt",
        "Kesinti",
        "Net",
        "Para",
        "Kesinti %",
        "Referans",
    ]


def _batch_table_row(batch_row: DiscountBatchReportBatchRow) -> list[str]:
    return [
        _format_date_tr(batch_row.discount_date),
        _shorten_text(batch_row.bank_name, 28),
        _shorten_text(batch_row.account_name, 30),
        str(batch_row.batch_id),
        str(batch_row.check_count),
        _format_decimal_tr(batch_row.average_days_to_due),
        _format_decimal_tr(batch_row.total_gross_amount),
        _format_decimal_tr(batch_row.total_discount_expense_amount),
        _format_decimal_tr(batch_row.net_bank_amount),
        batch_row.currency_code,
        f"%{_format_decimal_tr(batch_row.expense_ratio)}",
        _shorten_text(batch_row.reference_no, 24),
    ]


def _batch_table_rows(report_data: DiscountBatchReportData) -> list[list[str]]:
    return [
        _batch_table_row(batch_row)
        for batch_row in report_data.batch_rows
    ]


def _batch_table_row_statuses(report_data: DiscountBatchReportData) -> list[str]:
    return [
        batch_row.row_style
        for batch_row in report_data.batch_rows
    ]


def _item_table_headers() -> list[str]:
    return [
        "Paket",
        "Çek No",
        "Müşteri",
        "Keşide Bankası",
        "Vade",
        "Gün",
        "Brüt",
        "Faiz",
        "Kom.",
        "BSMV",
        "Kesinti",
        "Net",
        "Para",
    ]


def _item_table_row(item_row: DiscountBatchReportItemRow) -> list[str]:
    return [
        str(item_row.batch_id),
        _shorten_text(item_row.check_number, 18),
        _shorten_text(item_row.customer_name, 30),
        _shorten_text(item_row.drawer_bank_name, 26),
        _format_date_tr(item_row.due_date),
        str(item_row.days_to_due),
        _format_decimal_tr(item_row.gross_amount),
        _format_decimal_tr(item_row.interest_expense_amount),
        _format_decimal_tr(item_row.commission_amount),
        _format_decimal_tr(item_row.bsiv_amount),
        _format_decimal_tr(item_row.total_expense_amount),
        _format_decimal_tr(item_row.net_amount),
        item_row.currency_code,
    ]


def _item_table_rows(report_data: DiscountBatchReportData) -> list[list[str]]:
    return [
        _item_table_row(item_row)
        for item_row in report_data.item_rows
    ]


def _item_table_row_statuses(report_data: DiscountBatchReportData) -> list[str]:
    return [
        item_row.row_style
        for item_row in report_data.item_rows
    ]


def _bank_summary_headers() -> list[str]:
    return [
        "Banka",
        "Hesap",
        "Para",
        "Paket",
        "Çek",
        "Brüt",
        "Faiz",
        "Komisyon",
        "BSMV",
        "Kesinti",
        "Net",
    ]


def _bank_summary_row(bank_summary: DiscountBatchBankSummary) -> list[str]:
    return [
        _shorten_text(bank_summary.bank_name, 30),
        _shorten_text(bank_summary.account_name, 32),
        bank_summary.currency_code,
        str(bank_summary.batch_count),
        str(bank_summary.check_count),
        _format_decimal_tr(bank_summary.total_gross_amount),
        _format_decimal_tr(bank_summary.total_interest_expense_amount),
        _format_decimal_tr(bank_summary.total_commission_amount),
        _format_decimal_tr(bank_summary.total_bsiv_amount),
        _format_decimal_tr(bank_summary.total_discount_expense_amount),
        _format_decimal_tr(bank_summary.net_bank_amount),
    ]


def _bank_summary_rows(report_data: DiscountBatchReportData) -> list[list[str]]:
    return [
        _bank_summary_row(bank_summary)
        for bank_summary in report_data.summary.bank_summaries
    ]


def _totals_table_rows(report_data: DiscountBatchReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("İskonto Paketi", f"{summary.total_batch_count} paket"),
        ("Çek Sayısı", f"{summary.total_check_count} çek"),
        ("Ortalama Vade", f"{_format_decimal_tr(summary.average_days_to_due)} gün"),
        ("Brüt Çek Tutarı", _format_currency_totals_inline(summary.total_gross_amount_by_currency)),
        ("Faiz Gideri", _format_currency_totals_inline(summary.total_interest_expense_by_currency)),
        ("Komisyon", _format_currency_totals_inline(summary.total_commission_by_currency)),
        ("BSMV", _format_currency_totals_inline(summary.total_bsiv_by_currency)),
        ("Toplam Kesinti", _format_currency_totals_inline(summary.total_discount_expense_by_currency)),
        ("Net Banka Tutarı", _format_currency_totals_inline(summary.net_bank_amount_by_currency)),
    ]


def build_discount_batch_report_pdf(
    *,
    output_path: str | Path,
    report_data: DiscountBatchReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="İskonto Paketleri Raporu",
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
    elements.append(builder.section_title("İskonto Paketleri"))

    if not report_data.batch_rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun iskonto paketi bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_batch_table_headers(),
                rows=_batch_table_rows(report_data),
                col_widths=[18, 30, 33, 15, 13, 18, 27, 27, 27, 14, 20, 25],
                numeric_columns={3, 4, 5, 6, 7, 8, 10},
                center_columns={0, 3, 4, 5, 9},
                row_statuses=_batch_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Banka / Hesap Bazlı Özet"))

    if not report_data.summary.bank_summaries:
        elements.append(
            builder.paragraph(
                "Rapor döneminde iskonto yapılan banka hesabı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_bank_summary_headers(),
                rows=_bank_summary_rows(report_data),
                col_widths=[30, 32, 14, 14, 14, 26, 25, 25, 24, 27, 27],
                numeric_columns={3, 4, 5, 6, 7, 8, 9, 10},
                center_columns={2, 3, 4},
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Pakete Bağlı Çek Detayları"))

    if not report_data.item_rows:
        elements.append(
            builder.paragraph(
                "Seçilen rapor döneminde iskonto paketine bağlı çek detayı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_item_table_headers(),
                rows=_item_table_rows(report_data),
                col_widths=[15, 22, 31, 29, 19, 13, 25, 24, 23, 23, 25, 25, 13],
                numeric_columns={5, 6, 7, 8, 9, 10, 11},
                center_columns={0, 4, 5, 12},
                row_statuses=_item_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="İskonto Paketleri Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_discount_batch_report_pdf(
    *,
    output_path: str | Path,
    report_filter: DiscountBatchReportFilter,
    created_by: str,
) -> str:
    report_data = load_discount_batch_report_data(report_filter)

    return build_discount_batch_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_discount_batch_report_pdf(
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

    report_filter = DiscountBatchReportFilter(
        start_date=start_date,
        end_date=end_date,
        bank_id=None,
        bank_account_id=None,
        currency_code="ALL",
    )

    return create_discount_batch_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )


__all__ = [
    "build_discount_batch_report_pdf",
    "create_discount_batch_report_pdf",
    "create_default_current_month_discount_batch_report_pdf",
]