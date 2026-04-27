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


def _rate_to_float(value: Any) -> float:
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


def _first_currency_total(totals: dict[str, Decimal], currency_code: str) -> float:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"

    if normalized_currency_code in totals:
        return _decimal_to_float(totals[normalized_currency_code])

    if totals:
        first_key = next(iter(totals.keys()))
        return _decimal_to_float(totals[first_key])

    return 0.0


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

    bank_text = "Tümü" if report_filter.bank_id is None else f"Banka ID: {report_filter.bank_id}"
    account_text = "Tümü" if report_filter.bank_account_id is None else f"Hesap ID: {report_filter.bank_account_id}"
    pos_text = "Tümü" if report_filter.pos_device_id is None else f"POS ID: {report_filter.pos_device_id}"

    return (
        f"Banka: {bank_text} | "
        f"Hesap: {account_text} | "
        f"POS: {pos_text} | "
        f"Durum: {status_text} | "
        f"Para Birimi: {currency_text}"
    )


def _settlement_table_rows(report_data: PosSettlementReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for row in report_data.rows:
        rows.append(
            [
                row.settlement_id,
                _date_or_none(row.transaction_date),
                _date_or_none(row.expected_settlement_date),
                _date_or_none(row.realized_settlement_date),
                row.bank_name,
                row.account_name,
                row.pos_device_name,
                row.terminal_no or "",
                _decimal_to_float(row.gross_amount),
                _rate_to_float(row.commission_rate),
                None,
                None,
                None if row.actual_net_amount is None else _decimal_to_float(row.actual_net_amount),
                None,
                row.currency_code,
                row.status_text,
                row.reference_no or "",
                row.difference_reason or "",
                row.description or "",
            ]
        )

    return rows


def _settlement_row_styles(report_data: PosSettlementReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _device_summary_rows(report_data: PosSettlementReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for summary in report_data.summary.device_summaries:
        rows.append(
            [
                summary.bank_name,
                summary.account_name,
                summary.pos_device_name,
                summary.terminal_no or "",
                summary.currency_code,
                summary.record_count,
                summary.planned_count,
                summary.realized_count,
                summary.cancelled_count,
                summary.mismatch_count,
                _first_currency_total(summary.gross_totals, summary.currency_code),
                _first_currency_total(summary.commission_totals, summary.currency_code),
                _first_currency_total(summary.expected_net_totals, summary.currency_code),
                _first_currency_total(summary.actual_net_totals, summary.currency_code),
                _first_currency_total(summary.difference_totals, summary.currency_code),
            ]
        )

    return rows


def _write_summary_sheet(
    *,
    builder: FtmExcelReportBuilder,
    worksheet,
    report_data: PosSettlementReportData,
    settlement_total_row: int | None,
    settlement_data_start_row: int | None,
    settlement_last_data_row: int | None,
) -> None:
    builder.write_report_header(
        worksheet,
        last_column=12,
        subtitle=_report_filter_summary_text(report_data.filters),
    )

    has_rows = (
        settlement_total_row is not None
        and settlement_data_start_row is not None
        and settlement_last_data_row is not None
    )

    if has_rows:
        status_range = f"'POS Detayı'!P{settlement_data_start_row}:P{settlement_last_data_row}"
        gross_range = f"'POS Detayı'!I{settlement_data_start_row}:I{settlement_last_data_row}"
        commission_range = f"'POS Detayı'!K{settlement_data_start_row}:K{settlement_last_data_row}"
        expected_net_range = f"'POS Detayı'!L{settlement_data_start_row}:L{settlement_last_data_row}"
        actual_net_range = f"'POS Detayı'!M{settlement_data_start_row}:M{settlement_last_data_row}"
        difference_range = f"'POS Detayı'!N{settlement_data_start_row}:N{settlement_last_data_row}"

        total_count = f"=COUNTA('POS Detayı'!A{settlement_data_start_row}:A{settlement_last_data_row})"
        planned_count = f'=COUNTIF({status_range},"Planlandı")'
        realized_count = f'=COUNTIF({status_range},"Gerçekleşti")'
        cancelled_count = f'=COUNTIF({status_range},"İptal Edildi")'
        mismatch_count = f'=COUNTIF({status_range},"Fark Var")'
        gross_total = f"=SUBTOTAL(109,{gross_range})"
        commission_total = f"=SUBTOTAL(109,{commission_range})"
        expected_net_total = f"=SUBTOTAL(109,{expected_net_range})"
        actual_net_total = f"=SUBTOTAL(109,{actual_net_range})"
        difference_total = f"=SUBTOTAL(109,{difference_range})"
    else:
        total_count = 0
        planned_count = 0
        realized_count = 0
        cancelled_count = 0
        mismatch_count = 0
        gross_total = 0
        commission_total = 0
        expected_net_total = 0
        actual_net_total = 0
        difference_total = 0

    cards = [
        FtmExcelSummaryCard(
            title="Toplam Kayıt",
            value=total_count,
            hint="Rapor kapsamındaki POS mutabakat kaydı",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Planlanan",
            value=planned_count,
            hint="Henüz yatışı beklenen kayıtlar",
            card_type="warning",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Gerçekleşen",
            value=realized_count,
            hint="Yatışı gerçekleşen kayıtlar",
            card_type="success",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="İptal",
            value=cancelled_count,
            hint="İptal edilmiş kayıtlar",
            card_type="normal",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Fark Var",
            value=mismatch_count,
            hint="Beklenen ve gerçekleşen arasında fark olan kayıtlar",
            card_type="risk",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Brüt Toplam",
            value=gross_total,
            hint="Toplam POS brüt tutarı",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Komisyon",
            value=commission_total,
            hint="Toplam banka komisyonu",
            card_type="warning",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Beklenen Net",
            value=expected_net_total,
            hint="Brüt - komisyon",
            card_type="info",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Gerçekleşen Net",
            value=actual_net_total,
            hint="Bankaya yatan gerçek net tutar",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Toplam Fark",
            value=difference_total,
            hint="Gerçekleşen net - beklenen net",
            card_type="risk",
            number_format=builder.number_format,
        ),
    ]

    builder.write_summary_cards(
        worksheet,
        start_row=5,
        start_column=1,
        cards=cards,
        columns=4,
        card_width=3,
    )

    builder.write_key_value_table(
        worksheet,
        start_row=18,
        start_column=1,
        title="Rapor Açıklaması",
        rows=[
            ("Rapor Türü", "POS Mutabakat Excel", None),
            ("Rapor Dönemi", report_data.report_period_text, None),
            ("Filtreler", _report_filter_summary_text(report_data.filters), None),
            ("Beklenen Net", "Brüt tutardan komisyon düşülerek hesaplanır.", None),
            ("Fark", "Gerçekleşen net tutar ile beklenen net tutar arasındaki farktır.", None),
            ("Formül Mantığı", "POS Detayı sayfasındaki hesaplanan alanlar formüllüdür.", None),
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


def build_pos_settlement_report_excel(
    *,
    output_path: str | Path,
    report_data: PosSettlementReportData,
    created_by: str,
) -> str:
    builder = FtmExcelReportBuilder(
        output_path=output_path,
        meta=FtmExcelMeta(
            title="POS Mutabakat Raporu",
            report_period=report_data.report_period_text,
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    summary_sheet = builder.add_sheet("Özet", freeze_panes="A5")
    settlement_sheet = builder.add_sheet("POS Detayı", freeze_panes="A7")
    device_sheet = builder.add_sheet("POS Özeti", freeze_panes="A7")

    builder.write_report_header(
        settlement_sheet,
        last_column=19,
        subtitle="Filtrelenebilir ve formüllü POS mutabakat detay tablosu",
    )

    settlement_headers = [
        "ID",
        "İşlem Tarihi",
        "Beklenen Yatış",
        "Gerçekleşen Yatış",
        "Banka",
        "Hesap",
        "POS",
        "Terminal No",
        "Brüt",
        "Komisyon Oranı",
        "Komisyon",
        "Beklenen Net",
        "Gerçekleşen Net",
        "Fark",
        "Para",
        "Durum",
        "Referans",
        "Fark Nedeni",
        "Açıklama",
    ]

    settlement_next_row, settlement_last_column = builder.write_table(
        settlement_sheet,
        start_row=5,
        start_column=1,
        title="POS Mutabakat Detayı",
        headers=settlement_headers,
        rows=_settlement_table_rows(report_data),
        number_formats={
            0: builder.integer_format,
            1: builder.date_format,
            2: builder.date_format,
            3: builder.date_format,
            8: builder.number_format,
            9: builder.percent_format,
            10: builder.number_format,
            11: builder.number_format,
            12: builder.number_format,
            13: builder.number_format,
        },
        formula_columns={
            10: "=IF(J{row}<=1,I{row}*J{row},I{row}*(J{row}/100))",
            11: "=I{row}-K{row}",
            13: "=M{row}-L{row}",
        },
        row_styles=_settlement_row_styles(report_data),
        auto_filter=True,
        freeze_panes="A7",
    )

    settlement_total_row = None
    settlement_data_start_row = None
    settlement_last_data_row = None

    if report_data.rows:
        settlement_total_row = settlement_next_row - 2
        settlement_data_start_row = 7
        settlement_last_data_row = settlement_total_row - 1

    builder.set_column_widths(
        settlement_sheet,
        {
            1: 9,
            2: 13,
            3: 15,
            4: 17,
            5: 22,
            6: 24,
            7: 22,
            8: 16,
            9: 15,
            10: 15,
            11: 15,
            12: 16,
            13: 17,
            14: 14,
            15: 9,
            16: 14,
            17: 18,
            18: 28,
            19: 36,
        },
    )
    builder.normalize_sheet(settlement_sheet, max_column=settlement_last_column)

    builder.write_report_header(
        device_sheet,
        last_column=15,
        subtitle="POS cihazı bazlı mutabakat özeti",
    )

    device_headers = [
        "Banka",
        "Hesap",
        "POS",
        "Terminal No",
        "Para",
        "Kayıt",
        "Planlanan",
        "Gerçekleşen",
        "İptal",
        "Fark Var",
        "Brüt",
        "Komisyon",
        "Beklenen Net",
        "Gerçekleşen Net",
        "Fark",
    ]

    device_next_row, device_last_column = builder.write_table(
        device_sheet,
        start_row=5,
        start_column=1,
        title="POS Bazlı Özet",
        headers=device_headers,
        rows=_device_summary_rows(report_data),
        number_formats={
            5: builder.integer_format,
            6: builder.integer_format,
            7: builder.integer_format,
            8: builder.integer_format,
            9: builder.integer_format,
            10: builder.number_format,
            11: builder.number_format,
            12: builder.number_format,
            13: builder.number_format,
            14: builder.number_format,
        },
        formula_columns={},
        row_styles=[],
        auto_filter=True,
        freeze_panes="A7",
    )

    builder.set_column_widths(
        device_sheet,
        {
            1: 22,
            2: 24,
            3: 22,
            4: 16,
            5: 9,
            6: 10,
            7: 12,
            8: 13,
            9: 9,
            10: 10,
            11: 15,
            12: 15,
            13: 16,
            14: 17,
            15: 14,
        },
    )
    builder.normalize_sheet(device_sheet, max_column=device_last_column)

    _write_summary_sheet(
        builder=builder,
        worksheet=summary_sheet,
        report_data=report_data,
        settlement_total_row=settlement_total_row,
        settlement_data_start_row=settlement_data_start_row,
        settlement_last_data_row=settlement_last_data_row,
    )

    return builder.save()


def create_pos_settlement_report_excel(
    *,
    output_path: str | Path,
    report_filter: PosSettlementReportFilter,
    created_by: str,
) -> str:
    report_data = load_pos_settlement_report_data(report_filter)

    return build_pos_settlement_report_excel(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_pos_settlement_report_excel(
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

    return create_pos_settlement_report_excel(
        output_path=output_path,
        report_filter=PosSettlementReportFilter(
            start_date=start_date,
            end_date=end_date,
            pos_device_id=None,
            bank_id=None,
            bank_account_id=None,
            status="ALL",
            currency_code="ALL",
        ),
        created_by=created_by,
    )


__all__ = [
    "build_pos_settlement_report_excel",
    "create_pos_settlement_report_excel",
    "create_default_current_month_pos_settlement_report_excel",
]