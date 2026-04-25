from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.report_pdf_base import (
    FtmPdfReportBuilder,
    FtmReportMeta,
    FtmSummaryCard,
)
from app.reports.risk_check_report_data import (
    RiskCheckPartySummary,
    RiskCheckReportData,
    RiskCheckReportFilter,
    RiskCheckReportRow,
    load_risk_check_report_data,
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


def _report_filter_summary_text(report_filter: RiskCheckReportFilter) -> str:
    check_type_text = _filter_text(
        report_filter.check_type,
        {
            "ALL": "Tümü",
            "RECEIVED": "Alınan Çekler",
            "ISSUED": "Yazılan Çekler",
        },
    )

    risk_type_text = _filter_text(
        report_filter.risk_type,
        {
            "ALL": "Tümü",
            "PROBLEM": "Problemli / Riskli",
            "OVERDUE": "Vadesi Geçmiş",
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
        f"Risk Türü: {risk_type_text} | "
        f"Para Birimi: {currency_text}"
    )


def _summary_cards(report_data: RiskCheckReportData) -> list[FtmSummaryCard]:
    summary = report_data.summary

    return [
        FtmSummaryCard(
            title="Toplam Risk Kaydı",
            value=f"{summary.total_count} kayıt",
            hint=_format_currency_totals_inline(summary.grand_totals),
            card_type="risk" if summary.total_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Problemli / Riskli",
            value=f"{summary.problem_count} kayıt",
            hint=_format_currency_totals_inline(summary.problem_totals),
            card_type="risk" if summary.problem_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Vadesi Geçmiş",
            value=f"{summary.overdue_count} kayıt",
            hint=_format_currency_totals_inline(summary.overdue_totals),
            card_type="warning" if summary.overdue_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Alınan Problemli Çek",
            value=f"{summary.received_problem_count} kayıt",
            hint=_format_currency_totals_inline(summary.received_problem_totals),
            card_type="risk" if summary.received_problem_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Yazılan Riskli Çek",
            value=f"{summary.issued_problem_count} kayıt",
            hint=_format_currency_totals_inline(summary.issued_problem_totals),
            card_type="risk" if summary.issued_problem_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Geciken Alınan Çek",
            value=f"{summary.received_overdue_count} kayıt",
            hint=_format_currency_totals_inline(summary.received_overdue_totals),
            card_type="warning" if summary.received_overdue_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Geciken Yazılan Çek",
            value=f"{summary.issued_overdue_count} kayıt",
            hint=_format_currency_totals_inline(summary.issued_overdue_totals),
            card_type="warning" if summary.issued_overdue_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Riskli Taraf Sayısı",
            value=f"{len(summary.party_summaries)} taraf",
            hint="İlk 10 taraf rapor altında listelenir",
            card_type="normal",
        ),
    ]


def _detail_table_headers() -> list[str]:
    return [
        "Risk Türü",
        "Tür",
        "Taraf",
        "Çek No",
        "Vade",
        "Gecikme",
        "Tutar",
        "Para",
        "Durum",
        "Açıklama",
    ]


def _detail_table_row(row: RiskCheckReportRow) -> list[str]:
    return [
        row.risk_type_text,
        row.check_type_text,
        _shorten_text(row.party_name, 34),
        _shorten_text(row.check_number, 18),
        _format_date_tr(row.due_date),
        row.delay_text,
        _format_decimal_tr(row.amount),
        row.currency_code,
        _shorten_text(row.status_text, 22),
        _shorten_text(row.description or row.reference_no, 52),
    ]


def _detail_table_rows(report_data: RiskCheckReportData) -> list[list[str]]:
    return [
        _detail_table_row(row)
        for row in report_data.rows
    ]


def _detail_table_row_statuses(report_data: RiskCheckReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _party_summary_headers() -> list[str]:
    return [
        "Taraf",
        "Kayıt",
        "Toplam Risk",
    ]


def _party_summary_row(party_summary: RiskCheckPartySummary) -> list[str]:
    return [
        _shorten_text(party_summary.party_name, 60),
        str(party_summary.record_count),
        _format_currency_totals_inline(party_summary.totals),
    ]


def _party_summary_rows(report_data: RiskCheckReportData) -> list[list[str]]:
    return [
        _party_summary_row(party_summary)
        for party_summary in report_data.summary.party_summaries
    ]


def _totals_table_rows(report_data: RiskCheckReportData) -> list[tuple[str, str]]:
    summary = report_data.summary

    return [
        ("Toplam Risk Kaydı", f"{summary.total_count} kayıt"),
        ("Problemli / Riskli", _format_currency_totals_inline(summary.problem_totals)),
        ("Vadesi Geçmiş", _format_currency_totals_inline(summary.overdue_totals)),
        ("Alınan Problemli", _format_currency_totals_inline(summary.received_problem_totals)),
        ("Yazılan Riskli", _format_currency_totals_inline(summary.issued_problem_totals)),
        ("Geciken Alınan", _format_currency_totals_inline(summary.received_overdue_totals)),
        ("Geciken Yazılan", _format_currency_totals_inline(summary.issued_overdue_totals)),
        ("Genel Risk Toplamı", _format_currency_totals_inline(summary.grand_totals)),
    ]


def build_risk_check_report_pdf(
    *,
    output_path: str | Path,
    report_data: RiskCheckReportData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Riskli / Problemli Çek Raporu",
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
    elements.append(builder.section_title("Risk Detay Listesi"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığı ve filtrelere uygun riskli / problemli çek kaydı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_detail_table_headers(),
                rows=_detail_table_rows(report_data),
                col_widths=[27, 17, 42, 22, 22, 24, 28, 16, 26, 45],
                numeric_columns={6},
                center_columns={0, 1, 4, 5, 7, 8},
                row_statuses=_detail_table_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Taraf Bazlı İlk 10 Risk Özeti"))

    if not report_data.summary.party_summaries:
        elements.append(
            builder.paragraph(
                "Riskli taraf kaydı bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_party_summary_headers(),
                rows=_party_summary_rows(report_data),
                col_widths=[90, 25, 65],
                numeric_columns={2},
                center_columns={1},
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Risk Raporu Toplamları",
            totals=_totals_table_rows(report_data),
        )
    )

    return builder.build(elements)


def create_risk_check_report_pdf(
    *,
    output_path: str | Path,
    report_filter: RiskCheckReportFilter,
    created_by: str,
) -> str:
    report_data = load_risk_check_report_data(report_filter)

    return build_risk_check_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_year_risk_check_report_pdf(
    *,
    output_path: str | Path,
    created_by: str = "FTM Kullanıcısı",
) -> str:
    today = date.today()

    report_filter = RiskCheckReportFilter(
        start_date=date(today.year, 1, 1),
        end_date=date(today.year, 12, 31),
        check_type="ALL",
        risk_type="ALL",
        currency_code="ALL",
    )

    return create_risk_check_report_pdf(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )