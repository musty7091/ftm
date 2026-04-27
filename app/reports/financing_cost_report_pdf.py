from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.financing_cost_report_data import (
    FinancingCostBankSummary,
    FinancingCostReportCheckRow,
    FinancingCostReportData,
    FinancingCostReportFilter,
    FinancingCostReportRow,
    load_financing_cost_report_data,
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

    if abs(rate_value) <= Decimal("1.000000"):
        percent_value = (rate_value * Decimal("100")).quantize(Decimal("0.01"))
    else:
        percent_value = rate_value.quantize(Decimal("0.01"))

    return f"%{_format_decimal_tr(percent_value)}"


def _format_ratio_percent(value: Any) -> str:
    ratio_value = _decimal_or_zero(value)

    return f"%{_format_decimal_tr(ratio_value)}"


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


def _format_ratio_totals_inline(ratio_totals: dict[str, Decimal]) -> str:
    if not ratio_totals:
        return "%0,00"

    parts: list[str] = []

    for currency_code in sorted(ratio_totals.keys(), key=_currency_sort_key):
        parts.append(f"{currency_code}: {_format_ratio_percent(ratio_totals[currency_code])}")

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


def _report_filter_summary_text(report_filter: FinancingCostReportFilter) -> str:
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
    package_text = "Tümü" if report_filter.discount_batch_id is None else f"Paket ID: {report_filter.discount_batch_id}"

    return (
        f"Banka: {bank_text} | "
        f"Hesap: {account_text} | "
        f"Paket: {package_text} | "
        f"Para Birimi: {currency_text}"
    )


def _summary_cards(report_data: FinancingCostReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    total_gross_text = _format_currency_totals_inline(summary.total_gross_amount_by_currency)
    interest_text = _format_currency_totals_inline(summary.total_interest_expense_by_currency)
    commission_text = _format_currency_totals_inline(summary.total_commission_by_currency)
    bsiv_text = _format_currency_totals_inline(summary.total_bsiv_by_currency)
    total_expense_text = _format_currency_totals_inline(summary.total_discount_expense_by_currency)
    net_bank_text = _format_currency_totals_inline(summary.net_bank_amount_by_currency)
    expense_ratio_text = _format_ratio_totals_inline(summary.total_expense_ratio_by_currency)
    net_ratio_text = _format_ratio_totals_inline(summary.net_ratio_by_currency)

    return [
        FtmSummaryCard(
            title="Paket Sayısı",
            value=f"{summary.total_batch_count} paket",
            hint="Seçilen dönemdeki iskonto paketi",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Çek Sayısı",
            value=f"{summary.total_check_count} çek",
            hint=f"Ortalama vade: {_format_decimal_tr(summary.average_days_to_due)} gün",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Brüt Tutar",
            value=total_gross_text,
            hint="İskontoya verilen çeklerin brüt toplamı",
            card_type="success",
        ),
        FtmSummaryCard(
            title="Faiz Gideri",
            value=interest_text,
            hint="Finansman maliyetinin faiz kısmı",
            card_type="warning" if summary.total_batch_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Komisyon",
            value=commission_text,
            hint="Banka komisyon toplamı",
            card_type="warning" if summary.total_batch_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="BSMV",
            value=bsiv_text,
            hint="Vergi / BSMV toplamı",
            card_type="warning" if summary.total_batch_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Toplam Maliyet",
            value=total_expense_text,
            hint=f"Maliyet oranı: {expense_ratio_text}",
            card_type="risk" if summary.total_batch_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Net Banka Tutarı",
            value=net_bank_text,
            hint=f"Net oran: {net_ratio_text}",
            card_type="success",
        ),
    ]


def _cost_table_headers() -> list[str]:
    return [
        "Tarih",
        "Banka",
        "Hesap",
        "Paket",
        "Çek",
        "Ort.",
        "Brüt",
        "Faiz",
        "Kom.",
        "BSMV",
        "Maliyet",
        "Net",
        "Para",
        "Mal. %",
    ]


def _cost_table_row(row: FinancingCostReportRow) -> list[str]:
    return [
        _format_date_tr(row.discount_date),
        _shorten_text(row.bank_name, 22),
        _shorten_text(row.account_name, 24),
        str(row.batch_id),
        str(row.check_count),
        _format_decimal_tr(row.average_days_to_due),
        _format_decimal_tr(row.total_gross_amount),
        _format_decimal_tr(row.total_interest_expense_amount),
        _format_decimal_tr(row.total_commission_amount),
        _format_decimal_tr(row.total_bsiv_amount),
        _format_decimal_tr(row.total_discount_expense_amount),
        _format_decimal_tr(row.net_bank_amount),
        row.currency_code,
        _format_ratio_percent(row.total_expense_ratio),
    ]


def _cost_table_rows(report_data: FinancingCostReportData) -> list[list[str]]:
    return [
        _cost_table_row(row)
        for row in report_data.rows
    ]


def _cost_table_row_statuses(report_data: FinancingCostReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _rate_table_headers() -> list[str]:
    return [
        "Tarih",
        "Banka",
        "Paket",
        "Yıl. Faiz",
        "Kom. Oranı",
        "BSMV Oranı",
        "Faiz %",
        "Kom. %",
        "BSMV %",
        "Maliyet %",
        "Net %",
        "Referans",
    ]


def _rate_table_row(row: FinancingCostReportRow) -> list[str]:
    return [
        _format_date_tr(row.discount_date),
        _shorten_text(row.bank_name, 32),
        str(row.batch_id),
        _format_rate_percent(row.annual_interest_rate),
        _format_rate_percent(row.commission_rate),
        _format_rate_percent(row.bsiv_rate),
        _format_ratio_percent(row.interest_ratio),
        _format_ratio_percent(row.commission_ratio),
        _format_ratio_percent(row.bsiv_ratio),
        _format_ratio_percent(row.total_expense_ratio),
        _format_ratio_percent(row.net_ratio),
        _shorten_text(row.reference_no, 24),
    ]


def _rate_table_rows(report_data: FinancingCostReportData) -> list[list[str]]:
    return [
        _rate_table_row(row)
        for row in report_data.rows
    ]


def _rate_table_row_statuses(report_data: FinancingCostReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _bank_summary_headers() -> list[str]:
    return [
        "Banka",
        "Hesap",
        "Para",
        "Paket",
        "Çek",
        "Ort.",
        "Brüt",
        "Faiz",
        "Kom.",
        "BSMV",
        "Maliyet",
        "Net",
        "Mal. %",
    ]


def _bank_summary_row(bank_summary: FinancingCostBankSummary) -> list[str]:
    return [
        _shorten_text(bank_summary.bank_name, 24),
        _shorten_text(bank_summary.account_name, 24),
        bank_summary.currency_code,
        str(bank_summary.batch_count),
        str(bank_summary.check_count),
        _format_decimal_tr(bank_summary.average_days_to_due),
        _format_decimal_tr(bank_summary.total_gross_amount),
        _format_decimal_tr(bank_summary.total_interest_expense_amount),
        _format_decimal_tr(bank_summary.total_commission_amount),
        _format_decimal_tr(bank_summary.total_bsiv_amount),
        _format_decimal_tr(bank_summary.total_discount_expense_amount),
        _format_decimal_tr(bank_summary.net_bank_amount),
        _format_ratio_percent(bank_summary.total_expense_ratio),
    ]


def _bank_summary_rows(report_data: FinancingCostReportData) -> list[list[str]]:
    return [
        _bank_summary_row(bank_summary)
        for bank_summary in report_data.summary.bank_summaries
    ]


def _check_table_headers() -> list[str]:
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
        "Masraf",
        "Net",
        "Para",
        "Mas. %",
    ]


def _check_table_row(check_row: FinancingCostReportCheckRow) -> list[str]:
    return [
        str(check_row.batch_id),
        _shorten_text(check_row.check_number, 18),
        _shorten_text(check_row.customer_name, 30),
        _shorten_text(check_row.drawer_bank_name, 26),
        _format_date_tr(check_row.due_date),
        str(check_row.days_to_due),
        _format_decimal_tr(check_row.gross_amount),
        _format_decimal_tr(check_row.interest_expense_amount),
        _format_decimal_tr(check_row.commission_amount),
        _format_decimal_tr(check_row.bsiv_amount),
        _format_decimal_tr(check_row.total_expense_amount),
        _format_decimal_tr(check_row.net_amount),
        check_row.currency_code,
        _format_ratio_percent(check_row.expense_ratio),
    ]


def _check_table_rows(report_data: FinancingCostReportData) -> list[list[str]]:
    return [
        _check_table_row(check_row)
        for check_row in report_data.check_rows
    ]


def _check_table_row_statuses(report_data: FinancingCostReportData) -> list[str]:
    return [
        check_row.row_style
        for check_row in report_data.check_rows
    ]


def _totals_table_rows(report_data: FinancingCostReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("Paket Sayısı", f"{summary.total_batch_count} paket"),
        ("Çek Sayısı", f"{summary.total_check_count} çek"),
        ("Ortalama Vade", f"{_format_decimal_tr(summary.average_days_to_due)} gün"),
        ("Brüt Tutar", _format_currency_totals_inline(summary.total_gross_amount_by_currency)),
        ("Faiz Gideri", _format_currency_totals_inline(summary.total_interest_expense_by_currency)),
        ("Komisyon", _format_currency_totals_inline(summary.total_commission_by_currency)),
        ("BSMV", _format_currency_totals_inline(summary.total_bsiv_by_currency)),
        ("Toplam Finansman Maliyeti", _format_currency_totals_inline(summary.total_discount_expense_by_currency)),
        ("Net Banka Tutarı", _format_currency_totals_inline(summary.net_bank_amount_by_currency)),
        ("Toplam Maliyet Oranı", _format_ratio_totals_inline(summary.total_expense_ratio_by_currency)),
        ("Net Banka Oranı", _format_ratio_totals_inline(summary.net_ratio_by_currency)),
    ]


def build_financing_cost_report_pdf(
    *,
    output_path: str | Path,
    report_data: FinancingCostReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Finansman Maliyeti Raporu",
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
    elements.append(builder.section_title("Finansman Maliyeti Detayı"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun finansman maliyeti kaydı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_cost_table_headers(),
                rows=_cost_table_rows(report_data),
                col_widths=[16, 24, 27, 12, 12, 15, 23, 21, 18, 18, 23, 23, 12, 16],
                numeric_columns={3, 4, 5, 6, 7, 8, 9, 10, 11, 13},
                center_columns={0, 3, 4, 5, 12, 13},
                row_statuses=_cost_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Oran Analizi"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Oran analizi için kayıt bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_rate_table_headers(),
                rows=_rate_table_rows(report_data),
                col_widths=[18, 34, 15, 22, 23, 23, 22, 22, 22, 23, 21, 26],
                numeric_columns={3, 4, 5, 6, 7, 8, 9, 10},
                center_columns={0, 2, 3, 4, 5, 6, 7, 8, 9, 10},
                row_statuses=_rate_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Banka / Hesap Bazlı Finansman Maliyeti"))

    if not report_data.summary.bank_summaries:
        elements.append(
            builder.paragraph(
                "Rapor döneminde finansman maliyeti oluşan banka hesabı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_bank_summary_headers(),
                rows=_bank_summary_rows(report_data),
                col_widths=[25, 27, 12, 12, 12, 15, 23, 21, 18, 18, 23, 23, 16],
                numeric_columns={3, 4, 5, 6, 7, 8, 9, 10, 11, 12},
                center_columns={2, 3, 4, 5, 12},
            )
        )

    elements.append(builder.page_break())
    elements.append(builder.section_title("Pakette Kullanılan Çekler"))

    if not report_data.check_rows:
        elements.append(
            builder.paragraph(
                "Seçilen finansman maliyeti raporu için pakete bağlı çek detayı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_check_table_headers(),
                rows=_check_table_rows(report_data),
                col_widths=[12, 18, 30, 26, 18, 11, 24, 22, 18, 18, 22, 23, 12, 16],
                numeric_columns={0, 5, 6, 7, 8, 9, 10, 11, 13},
                center_columns={0, 4, 5, 12, 13},
                row_statuses=_check_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Finansman Maliyeti Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_financing_cost_report_pdf(
    *,
    output_path: str | Path,
    report_filter: FinancingCostReportFilter,
    created_by: str,
) -> str:
    report_data = load_financing_cost_report_data(report_filter)

    return build_financing_cost_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_financing_cost_report_pdf(
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

    report_filter = FinancingCostReportFilter(
        start_date=start_date,
        end_date=end_date,
        bank_id=None,
        bank_account_id=None,
        discount_batch_id=None,
        currency_code="ALL",
    )

    return create_financing_cost_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )


__all__ = [
    "build_financing_cost_report_pdf",
    "create_financing_cost_report_pdf",
    "create_default_current_month_financing_cost_report_pdf",
]