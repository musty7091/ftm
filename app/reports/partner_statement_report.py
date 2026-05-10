from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.partner_statement_data import (
    PartnerStatementCurrencySummary,
    PartnerStatementData,
    PartnerStatementFilter,
    PartnerStatementMovementRow,
    load_partner_statement_data,
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
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_currency_amount(value: Any, currency_code: str) -> str:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    if normalized_currency_code == "TRY":
        return f"{_format_decimal_tr(value)} TL"

    return f"{_format_decimal_tr(value)} {normalized_currency_code}"


def _currency_sort_key(currency_code: str) -> tuple[int, str]:
    normalized_currency_code = str(currency_code or "").strip().upper()

    if normalized_currency_code in CURRENCY_DISPLAY_ORDER:
        return CURRENCY_DISPLAY_ORDER.index(normalized_currency_code), normalized_currency_code

    return 999, normalized_currency_code


def _format_date_tr(value: Any) -> str:
    if value is None:
        return "-"

    try:
        return value.strftime("%d.%m.%Y")
    except Exception:
        return "-"


def _shorten_text(value: Any, max_length: int) -> str:
    text = str(value or "").strip()

    if not text:
        return "-"

    if len(text) <= max_length:
        return text

    return text[: max(0, max_length - 3)].rstrip() + "..."


def _report_period_text(report_data: PartnerStatementData) -> str:
    return (
        f"{report_data.report_filter.start_date.strftime('%d.%m.%Y')} - "
        f"{report_data.report_filter.end_date.strftime('%d.%m.%Y')}"
    )


def _format_summary_total(
    summaries: list[PartnerStatementCurrencySummary],
    amount_attribute: str,
    count_attribute: str | None = None,
) -> str:
    parts: list[str] = []

    sorted_summaries = sorted(
        summaries,
        key=lambda summary: _currency_sort_key(summary.currency_code),
    )

    for summary in sorted_summaries:
        amount = _decimal_or_zero(getattr(summary, amount_attribute, Decimal("0.00")))
        count = int(getattr(summary, count_attribute, 0)) if count_attribute else 0

        if amount == Decimal("0.00") and count == 0:
            continue

        parts.append(_format_currency_amount(amount, summary.currency_code))

    if not parts:
        return "-"

    return " / ".join(parts)


def _summary_cards(report_data: PartnerStatementData) -> list[FtmSummaryCard]:
    summaries = report_data.currency_summaries

    return [
        FtmSummaryCard(
            title="Toplam Hareket",
            value=f"{report_data.total_row_count} kayıt",
            hint="Alınan çek, alınan çek hareketi ve yazılan çek kayıtları",
            card_type="normal",
        ),
        FtmSummaryCard(
            title="Alınan Çek",
            value=f"{report_data.received_check_count} kayıt",
            hint=_format_summary_total(summaries, "received_check_total", "received_check_count"),
            card_type="success",
        ),
        FtmSummaryCard(
            title="Alınan Çek Hareketi",
            value=f"{report_data.received_movement_count} kayıt",
            hint="Tahsil, iade, karşılıksız, ciro ve iskonto hareketleri",
            card_type="warning" if report_data.received_movement_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Yazılan Çek",
            value=f"{report_data.issued_check_count} kayıt",
            hint=_format_summary_total(summaries, "issued_check_total", "issued_check_count"),
            card_type="risk" if report_data.issued_check_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="Ödenen Yazılan Çek",
            value=f"{report_data.issued_paid_count} kayıt",
            hint=_format_summary_total(summaries, "issued_paid_total", "issued_paid_count"),
            card_type="success" if report_data.issued_paid_count > 0 else "normal",
        ),
        FtmSummaryCard(
            title="İptal Yazılan Çek",
            value=f"{report_data.issued_cancelled_count} kayıt",
            hint=_format_summary_total(summaries, "issued_cancelled_total", "issued_cancelled_count"),
            card_type="muted" if report_data.issued_cancelled_count > 0 else "normal",
        ),
    ]


def _partner_info_rows(report_data: PartnerStatementData) -> list[list[str]]:
    partner = report_data.partner

    return [
        ["Cari", partner.name],
        ["Cari Tipi", partner.partner_type_text],
        ["Durum", partner.status_text],
        ["Vergi No / Dairesi", f"{partner.tax_number or '-'} / {partner.tax_office or '-'}"],
        ["Yetkili", partner.authorized_person or "-"],
        ["Telefon / E-posta", f"{partner.phone or '-'} / {partner.email or '-'}"],
    ]


def _currency_summary_headers() -> list[str]:
    return [
        "Para",
        "Alınan Çek",
        "Alınan Adet",
        "Hareket",
        "Yazılan Çek",
        "Yazılan Adet",
        "Ödenen",
        "İptal",
    ]


def _currency_summary_rows(report_data: PartnerStatementData) -> list[list[str]]:
    rows: list[list[str]] = []

    for summary in report_data.currency_summaries:
        rows.append(
            [
                summary.currency_code,
                _format_decimal_tr(summary.received_check_total),
                str(summary.received_check_count),
                str(summary.received_movement_count),
                _format_decimal_tr(summary.issued_check_total),
                str(summary.issued_check_count),
                _format_decimal_tr(summary.issued_paid_total),
                _format_decimal_tr(summary.issued_cancelled_total),
            ]
        )

    return rows


def _movement_table_headers() -> list[str]:
    return [
        "Tarih",
        "Yön",
        "İşlem",
        "Çek No",
        "Vade",
        "Açıklama",
        "Borç",
        "Alacak",
        "Para",
        "Durum",
    ]


def _movement_table_row(row: PartnerStatementMovementRow) -> list[str]:
    description_parts = [row.description]

    bank_account_text = " / ".join(
        part
        for part in [row.bank_text, row.account_text]
        if str(part or "").strip() and str(part or "").strip() != "-"
    )

    if bank_account_text:
        description_parts.append(f"Banka/Hesap: {bank_account_text}")

    if row.reference_no:
        description_parts.append(f"Ref: {row.reference_no}")

    return [
        _format_date_tr(row.movement_date),
        row.check_direction,
        _shorten_text(row.operation_type, 35),
        _shorten_text(row.check_number, 18),
        _format_date_tr(row.due_date),
        _shorten_text(" | ".join(description_parts), 115),
        _format_decimal_tr(row.debit_amount) if _decimal_or_zero(row.debit_amount) != Decimal("0.00") else "-",
        _format_decimal_tr(row.credit_amount) if _decimal_or_zero(row.credit_amount) != Decimal("0.00") else "-",
        row.currency_code,
        _shorten_text(row.status_text, 22),
    ]


def _movement_table_rows(report_data: PartnerStatementData) -> list[list[str]]:
    return [
        _movement_table_row(row)
        for row in report_data.rows
    ]


def _movement_row_status(row: PartnerStatementMovementRow) -> str:
    operation_text = f"{row.operation_type} {row.status_text}".upper()

    if "KARŞILIKSIZ" in operation_text or "RİSK" in operation_text:
        return "PROBLEM"

    if "İPTAL" in operation_text or "İADE" in operation_text:
        return "CLOSED"

    if row.check_direction == "ALINAN":
        return "RECEIVED"

    if row.check_direction == "YAZILAN":
        return "ISSUED"

    return ""


def _movement_row_statuses(report_data: PartnerStatementData) -> list[str]:
    return [
        _movement_row_status(row)
        for row in report_data.rows
    ]


def _totals_rows(report_data: PartnerStatementData) -> list[tuple[str, str]]:
    return [
        ("Toplam Hareket", f"{report_data.total_row_count} kayıt"),
        ("Alınan Çek Toplamı", _format_summary_total(report_data.currency_summaries, "received_check_total", "received_check_count")),
        ("Yazılan Çek Toplamı", _format_summary_total(report_data.currency_summaries, "issued_check_total", "issued_check_count")),
        ("Ödenen Yazılan Çek", _format_summary_total(report_data.currency_summaries, "issued_paid_total", "issued_paid_count")),
        ("İptal Yazılan Çek", _format_summary_total(report_data.currency_summaries, "issued_cancelled_total", "issued_cancelled_count")),
    ]


def build_partner_statement_report_pdf(
    *,
    output_path: str | Path,
    report_data: PartnerStatementData,
    created_by: str,
) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Cari Hareket Raporu",
            report_period=_report_period_text(report_data),
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    elements: list[Any] = []

    elements.append(builder.section_title("Cari Bilgileri"))
    elements.append(
        builder.build_data_table(
            headers=["Alan", "Bilgi"],
            rows=_partner_info_rows(report_data),
            col_widths=[42, 205],
            center_columns=set(),
            numeric_columns=set(),
        )
    )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Rapor Özeti"))
    elements.append(
        builder.build_summary_cards(
            _summary_cards(report_data),
            columns=3,
        )
    )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Para Birimi Bazlı Özet"))

    if report_data.currency_summaries:
        elements.append(
            builder.build_data_table(
                headers=_currency_summary_headers(),
                rows=_currency_summary_rows(report_data),
                col_widths=[18, 33, 22, 22, 33, 22, 32, 32],
                numeric_columns={1, 2, 3, 4, 5, 6, 7},
                center_columns={0},
            )
        )
    else:
        elements.append(builder.paragraph("Seçilen dönemde bu cariye ait hareket özeti bulunamadı.", "normal"))

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Açıklamalı Cari Hareket Listesi"))

    if not report_data.rows:
        elements.append(
            builder.paragraph(
                "Seçilen tarih aralığında bu cariye ait alınan çek, alınan çek hareketi veya yazılan çek hareketi bulunamadı.",
                "normal",
            )
        )
    else:
        elements.append(
            builder.build_data_table(
                headers=_movement_table_headers(),
                rows=_movement_table_rows(report_data),
                col_widths=[18, 17, 31, 20, 18, 77, 24, 24, 12, 22],
                numeric_columns={6, 7},
                center_columns={0, 1, 3, 4, 8, 9},
                row_statuses=_movement_row_statuses(report_data),
            )
        )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Rapor Toplamları",
            totals=_totals_rows(report_data),
        )
    )

    return builder.build(elements)


def create_partner_statement_report_pdf(
    *,
    output_path: str | Path,
    report_filter: PartnerStatementFilter,
    created_by: str = "FTM Kullanıcısı",
) -> str:
    report_data = load_partner_statement_data(report_filter)

    return build_partner_statement_report_pdf(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )
