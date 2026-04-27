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
from app.reports.report_excel_base import (
    FtmExcelMeta,
    FtmExcelReportBuilder,
    FtmExcelSummaryCard,
)


def _decimal_to_float(value: Any) -> float:
    if value is None:
        return 0.0

    try:
        return float(Decimal(str(value)))
    except Exception:
        return 0.0


def _date_or_none(value: Any) -> date | None:
    if isinstance(value, date):
        return value

    return None


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
        f"Yön: {direction_text} | "
        f"Durum: {status_text} | "
        f"Kaynak: {source_type_text} | "
        f"Para Birimi: {currency_text}"
    )


def _movement_table_rows(report_data: BankMovementReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for row in report_data.rows:
        rows.append(
            [
                row.transaction_id,
                row.bank_name,
                row.account_name,
                _date_or_none(row.transaction_date),
                _date_or_none(row.value_date),
                row.direction_text,
                row.status_text,
                _decimal_to_float(row.amount),
                row.currency_code,
                None,
                row.source_type_text,
                row.reference_no or "",
                row.description or "",
            ]
        )

    return rows


def _movement_row_styles(report_data: BankMovementReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _account_summary_rows(report_data: BankMovementReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for summary in report_data.summary.account_summaries:
        rows.append(
            [
                summary.bank_name,
                summary.account_name,
                summary.currency_code,
                summary.transaction_count,
                summary.incoming_count,
                summary.outgoing_count,
                _first_currency_total(summary.incoming_totals, summary.currency_code),
                _first_currency_total(summary.outgoing_totals, summary.currency_code),
                _first_currency_total(summary.net_totals, summary.currency_code),
            ]
        )

    return rows


def _first_currency_total(totals: dict[str, Decimal], currency_code: str) -> float:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    if normalized_currency_code in totals:
        return _decimal_to_float(totals[normalized_currency_code])

    if totals:
        first_key = next(iter(totals.keys()))
        return _decimal_to_float(totals[first_key])

    return 0.0


def _write_summary_sheet(
    *,
    builder: FtmExcelReportBuilder,
    worksheet,
    report_data: BankMovementReportData,
    movement_total_row: int | None,
    movement_data_start_row: int | None,
    movement_last_data_row: int | None,
) -> None:
    builder.write_report_header(
        worksheet,
        last_column=12,
        subtitle=_report_filter_summary_text(report_data.filters),
    )

    has_rows = (
        movement_total_row is not None
        and movement_data_start_row is not None
        and movement_last_data_row is not None
    )

    if has_rows:
        direction_range = f"'Hareket Detayı'!F{movement_data_start_row}:F{movement_last_data_row}"
        status_range = f"'Hareket Detayı'!G{movement_data_start_row}:G{movement_last_data_row}"
        amount_range = f"'Hareket Detayı'!H{movement_data_start_row}:H{movement_last_data_row}"
        net_effect_range = f"'Hareket Detayı'!J{movement_data_start_row}:J{movement_last_data_row}"

        total_count = f"=COUNTA('Hareket Detayı'!A{movement_data_start_row}:A{movement_last_data_row})"
        incoming_count = f'=COUNTIF({direction_range},"Giriş")'
        outgoing_count = f'=COUNTIF({direction_range},"Çıkış")'
        realized_count = f'=COUNTIF({status_range},"Gerçekleşti")'
        planned_count = f'=COUNTIF({status_range},"Planlandı")'
        cancelled_count = f'=COUNTIF({status_range},"İptal Edildi")'
        incoming_total = f'=SUMIF({direction_range},"Giriş",{amount_range})'
        outgoing_total = f'=SUMIF({direction_range},"Çıkış",{amount_range})'
        net_total = f"=SUBTOTAL(109,{net_effect_range})"
    else:
        total_count = 0
        incoming_count = 0
        outgoing_count = 0
        realized_count = 0
        planned_count = 0
        cancelled_count = 0
        incoming_total = 0
        outgoing_total = 0
        net_total = 0

    cards = [
        FtmExcelSummaryCard(
            title="Toplam Hareket",
            value=total_count,
            hint="Rapor kapsamındaki banka hareketi",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Giriş Adedi",
            value=incoming_count,
            hint="Banka hesabına giren hareket sayısı",
            card_type="success",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Çıkış Adedi",
            value=outgoing_count,
            hint="Banka hesabından çıkan hareket sayısı",
            card_type="risk",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Gerçekleşen",
            value=realized_count,
            hint="Gerçekleşmiş hareket sayısı",
            card_type="success",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Planlanan",
            value=planned_count,
            hint="Planlanmış hareket sayısı",
            card_type="warning",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="İptal",
            value=cancelled_count,
            hint="İptal edilen hareket sayısı",
            card_type="normal",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Toplam Giriş",
            value=incoming_total,
            hint="Giriş yönlü hareketlerin toplamı",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Toplam Çıkış",
            value=outgoing_total,
            hint="Çıkış yönlü hareketlerin toplamı",
            card_type="risk",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Net Etki",
            value=net_total,
            hint="Girişler (+), çıkışlar (-)",
            card_type="info",
            number_format=builder.number_format,
        ),
    ]

    builder.write_summary_cards(
        worksheet,
        start_row=5,
        start_column=1,
        cards=cards,
        columns=3,
        card_width=3,
    )

    builder.write_key_value_table(
        worksheet,
        start_row=19,
        start_column=1,
        title="Rapor Açıklaması",
        rows=[
            ("Rapor Türü", "Banka Hareketleri Excel", None),
            ("Rapor Dönemi", report_data.report_period_text, None),
            ("Filtreler", _report_filter_summary_text(report_data.filters), None),
            ("Net Etki", "Giriş hareketleri pozitif, çıkış hareketleri negatif etki olarak hesaplanır.", None),
            ("Formül Mantığı", "Özet alanları Hareket Detayı sayfasındaki filtrelenebilir tablodan hesaplanır.", None),
        ],
    )

    builder.set_column_widths(
        worksheet,
        {
            1: 22,
            2: 22,
            3: 4,
            4: 4,
            5: 22,
            6: 22,
            7: 4,
            8: 4,
            9: 22,
            10: 22,
            11: 4,
            12: 4,
        },
    )
    builder.normalize_sheet(worksheet, max_column=12)


def build_bank_movement_report_excel(
    *,
    output_path: str | Path,
    report_data: BankMovementReportData,
    created_by: str,
) -> str:
    builder = FtmExcelReportBuilder(
        output_path=output_path,
        meta=FtmExcelMeta(
            title="Banka Hareketleri Raporu",
            report_period=report_data.report_period_text,
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    summary_sheet = builder.add_sheet("Özet", freeze_panes="A5")
    movement_sheet = builder.add_sheet("Hareket Detayı", freeze_panes="A7")
    account_sheet = builder.add_sheet("Hesap Özeti", freeze_panes="A7")

    builder.write_report_header(
        movement_sheet,
        last_column=13,
        subtitle="Filtrelenebilir ve formüllü banka hareketleri tablosu",
    )

    movement_headers = [
        "ID",
        "Banka",
        "Hesap",
        "İşlem Tarihi",
        "Valör",
        "Yön",
        "Durum",
        "Tutar",
        "Para",
        "Net Etki",
        "Kaynak",
        "Referans",
        "Açıklama",
    ]

    movement_next_row, movement_last_column = builder.write_table(
        movement_sheet,
        start_row=5,
        start_column=1,
        title="Banka Hareket Detayı",
        headers=movement_headers,
        rows=_movement_table_rows(report_data),
        number_formats={
            0: builder.integer_format,
            3: builder.date_format,
            4: builder.date_format,
            7: builder.number_format,
            9: builder.number_format,
        },
        formula_columns={
            9: '=IF(F{row}="Giriş",H{row},-H{row})',
        },
        row_styles=_movement_row_styles(report_data),
        auto_filter=True,
        freeze_panes="A7",
    )

    movement_total_row = None
    movement_data_start_row = None
    movement_last_data_row = None

    if report_data.rows:
        movement_total_row = movement_next_row - 2
        movement_data_start_row = 7
        movement_last_data_row = movement_total_row - 1

    builder.set_column_widths(
        movement_sheet,
        {
            1: 9,
            2: 22,
            3: 24,
            4: 13,
            5: 12,
            6: 10,
            7: 14,
            8: 15,
            9: 9,
            10: 15,
            11: 20,
            12: 18,
            13: 36,
        },
    )
    builder.normalize_sheet(movement_sheet, max_column=movement_last_column)

    builder.write_report_header(
        account_sheet,
        last_column=9,
        subtitle="Banka hesabı bazlı hareket özeti",
    )

    account_headers = [
        "Banka",
        "Hesap",
        "Para",
        "Hareket",
        "Giriş Adet",
        "Çıkış Adet",
        "Giriş Toplam",
        "Çıkış Toplam",
        "Net Etki",
    ]

    account_next_row, account_last_column = builder.write_table(
        account_sheet,
        start_row=5,
        start_column=1,
        title="Hesap Bazlı Özet",
        headers=account_headers,
        rows=_account_summary_rows(report_data),
        number_formats={
            3: builder.integer_format,
            4: builder.integer_format,
            5: builder.integer_format,
            6: builder.number_format,
            7: builder.number_format,
            8: builder.number_format,
        },
        formula_columns={},
        row_styles=[],
        auto_filter=True,
        freeze_panes="A7",
    )

    builder.set_column_widths(
        account_sheet,
        {
            1: 24,
            2: 26,
            3: 9,
            4: 10,
            5: 12,
            6: 12,
            7: 15,
            8: 15,
            9: 15,
        },
    )
    builder.normalize_sheet(account_sheet, max_column=account_last_column)

    _write_summary_sheet(
        builder=builder,
        worksheet=summary_sheet,
        report_data=report_data,
        movement_total_row=movement_total_row,
        movement_data_start_row=movement_data_start_row,
        movement_last_data_row=movement_last_data_row,
    )

    return builder.save()


def create_bank_movement_report_excel(
    *,
    output_path: str | Path,
    report_filter: BankMovementReportFilter,
    created_by: str,
) -> str:
    report_data = load_bank_movement_report_data(report_filter)

    return build_bank_movement_report_excel(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_bank_movement_report_excel(
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

    return create_bank_movement_report_excel(
        output_path=output_path,
        report_filter=BankMovementReportFilter(
            start_date=start_date,
            end_date=end_date,
            bank_id=None,
            bank_account_id=None,
            direction="ALL",
            status="ALL",
            currency_code="ALL",
            source_type="ALL",
        ),
        created_by=created_by,
    )


__all__ = [
    "build_bank_movement_report_excel",
    "create_bank_movement_report_excel",
    "create_default_current_month_bank_movement_report_excel",
]