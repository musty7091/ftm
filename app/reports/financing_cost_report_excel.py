from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl.utils import get_column_letter

from app.reports.financing_cost_report_data import (
    FinancingCostReportCheckRow,
    FinancingCostReportData,
    FinancingCostReportFilter,
    FinancingCostReportRow,
    load_financing_cost_report_data,
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


def _package_table_rows(report_data: FinancingCostReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for row in report_data.rows:
        rows.append(
            [
                _date_or_none(row.discount_date),
                row.bank_name,
                row.account_name,
                row.batch_id,
                row.check_count,
                _decimal_to_float(row.average_days_to_due),
                _decimal_to_float(row.total_gross_amount),
                _decimal_to_float(row.total_interest_expense_amount),
                _decimal_to_float(row.total_commission_amount),
                _decimal_to_float(row.total_bsiv_amount),
                None,
                None,
                row.currency_code,
                None,
                None,
            ]
        )

    return rows


def _package_row_styles(report_data: FinancingCostReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _check_table_rows(report_data: FinancingCostReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for row in report_data.check_rows:
        rows.append(
            [
                row.batch_id,
                row.check_number,
                row.customer_name,
                row.drawer_bank_name,
                _date_or_none(row.due_date),
                row.days_to_due,
                _decimal_to_float(row.gross_amount),
                _decimal_to_float(row.interest_expense_amount),
                _decimal_to_float(row.commission_amount),
                _decimal_to_float(row.bsiv_amount),
                None,
                None,
                row.currency_code,
                None,
                None,
            ]
        )

    return rows


def _check_row_styles(report_data: FinancingCostReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.check_rows
    ]


def _summary_value_formula(
    *,
    sheet_name: str,
    column_letter: str,
    total_row: int | None,
    default_value: str = "0",
) -> str | int:
    if total_row is None:
        return int(default_value)

    return f"='{sheet_name}'!{column_letter}{total_row}"


def _summary_ratio_formula(
    *,
    numerator_cell: str,
    denominator_cell: str,
) -> str:
    return f"=IF({denominator_cell}=0,0,{numerator_cell}/{denominator_cell})"


def _write_summary_sheet(
    *,
    builder: FtmExcelReportBuilder,
    worksheet,
    report_data: FinancingCostReportData,
    package_total_row: int | None,
    check_data_start_row: int | None,
    check_last_data_row: int | None,
) -> None:
    builder.write_report_header(
        worksheet,
        last_column=12,
        subtitle="Formüllü ve filtrelenebilir Excel raporu",
    )

    if package_total_row is None:
        package_count_value: int | str = 0
        check_count_value: int | str = 0
        average_days_value: int | str = 0
        gross_value: int | str = 0
        interest_value: int | str = 0
        commission_value: int | str = 0
        bsiv_value: int | str = 0
        cost_value: int | str = 0
        net_value: int | str = 0
    else:
        package_count_value = f"=COUNTA('Paket Detayı'!D7:D{package_total_row - 1})"
        check_count_value = f"='Paket Detayı'!E{package_total_row}"
        gross_value = f"='Paket Detayı'!G{package_total_row}"
        interest_value = f"='Paket Detayı'!H{package_total_row}"
        commission_value = f"='Paket Detayı'!I{package_total_row}"
        bsiv_value = f"='Paket Detayı'!J{package_total_row}"
        cost_value = f"='Paket Detayı'!K{package_total_row}"
        net_value = f"='Paket Detayı'!L{package_total_row}"

        if check_data_start_row is not None and check_last_data_row is not None:
            average_days_value = f"=AVERAGE('Çek Detayı'!F{check_data_start_row}:F{check_last_data_row})"
        else:
            average_days_value = 0

    cards = [
        FtmExcelSummaryCard(
            title="Paket Sayısı",
            value=package_count_value,
            hint="Rapor kapsamındaki iskonto paketi",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Çek Sayısı",
            value=check_count_value,
            hint="Paketlerde kullanılan çek sayısı",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Ortalama Vade",
            value=average_days_value,
            hint="Çek detayındaki gün ortalaması",
            card_type="normal",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Brüt Tutar",
            value=gross_value,
            hint="İskontoya verilen toplam çek tutarı",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Faiz Gideri",
            value=interest_value,
            hint="Toplam faiz masrafı",
            card_type="warning",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Komisyon",
            value=commission_value,
            hint="Toplam komisyon masrafı",
            card_type="warning",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="BSMV",
            value=bsiv_value,
            hint="Toplam BSMV masrafı",
            card_type="warning",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Toplam Maliyet",
            value=cost_value,
            hint="Faiz + komisyon + BSMV",
            card_type="risk",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Net Banka Tutarı",
            value=net_value,
            hint="Brüt tutar - toplam maliyet",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Maliyet Oranı",
            value=_summary_ratio_formula(numerator_cell="B18", denominator_cell="B14"),
            hint="Toplam maliyet / brüt tutar",
            card_type="risk",
            number_format=builder.percent_format,
        ),
        FtmExcelSummaryCard(
            title="Net Oran",
            value=_summary_ratio_formula(numerator_cell="B19", denominator_cell="B14"),
            hint="Net banka tutarı / brüt tutar",
            card_type="success",
            number_format=builder.percent_format,
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
        start_row=17,
        start_column=1,
        title="Formüllü Kontrol Alanı",
        rows=[
            ("Brüt Tutar", gross_value, builder.number_format),
            ("Toplam Maliyet", cost_value, builder.number_format),
            ("Net Banka Tutarı", net_value, builder.number_format),
            ("Maliyet Oranı", "=IF(B18=0,0,B19/B18)", builder.percent_format),
            ("Net Oran", "=IF(B18=0,0,B20/B18)", builder.percent_format),
        ],
    )

    builder.write_key_value_table(
        worksheet,
        start_row=17,
        start_column=5,
        title="Rapor Açıklaması",
        rows=[
            ("Kullanım", "Paket bazlı veya aylık iskonto maliyetlerini analiz eder.", None),
            ("Formüller", "Tablo içinde maliyet, net tutar ve oranlar formülle hesaplanır.", None),
            ("Filtre", "Paket Detayı ve Çek Detayı sayfalarında filtre kullanabilirsin.", None),
            ("Güncelleme", "Brüt, faiz, komisyon veya BSMV değişirse formüller sonuçları yeniler.", None),
        ],
    )

    builder.set_column_widths(
        worksheet,
        {
            1: 22,
            2: 18,
            3: 4,
            4: 4,
            5: 22,
            6: 54,
            7: 4,
            8: 4,
            9: 4,
            10: 4,
            11: 4,
            12: 4,
        },
    )
    builder.normalize_sheet(worksheet, max_column=12)


def build_financing_cost_report_excel(
    *,
    output_path: str | Path,
    report_data: FinancingCostReportData,
    created_by: str,
) -> str:
    builder = FtmExcelReportBuilder(
        output_path=output_path,
        meta=FtmExcelMeta(
            title="İskonto Maliyet Raporu",
            report_period=report_data.report_period_text,
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    summary_sheet = builder.add_sheet("Özet", freeze_panes="A5")
    package_sheet = builder.add_sheet("Paket Detayı", freeze_panes="A7")
    check_sheet = builder.add_sheet("Çek Detayı", freeze_panes="A7")

    builder.write_report_header(
        package_sheet,
        last_column=15,
        subtitle="Paket bazlı formüllü iskonto maliyet tablosu",
    )

    package_headers = [
        "Tarih",
        "Banka",
        "Hesap",
        "Paket",
        "Çek",
        "Ort. Vade",
        "Brüt",
        "Faiz",
        "Komisyon",
        "BSMV",
        "Toplam Maliyet",
        "Net Banka",
        "Para",
        "Maliyet %",
        "Net %",
    ]

    package_next_row, package_last_column = builder.write_table(
        package_sheet,
        start_row=5,
        start_column=1,
        title="Paket Bazlı İskonto Maliyetleri",
        headers=package_headers,
        rows=_package_table_rows(report_data),
        number_formats={
            0: builder.date_format,
            3: builder.integer_format,
            4: builder.integer_format,
            5: builder.number_format,
            6: builder.number_format,
            7: builder.number_format,
            8: builder.number_format,
            9: builder.number_format,
            10: builder.number_format,
            11: builder.number_format,
            13: builder.percent_format,
            14: builder.percent_format,
        },
        formula_columns={
            10: "=H{row}+I{row}+J{row}",
            11: "=G{row}-K{row}",
            13: "=IF(G{row}=0,0,K{row}/G{row})",
            14: "=IF(G{row}=0,0,L{row}/G{row})",
        },
        row_styles=_package_row_styles(report_data),
        auto_filter=True,
        freeze_panes="A7",
    )

    package_total_row = None

    if report_data.rows:
        package_total_row = package_next_row - 2
        builder.apply_conditional_percent_scale(
            package_sheet,
            range_address=f"N7:N{package_total_row - 1}",
            warning_threshold=0.05,
            risk_threshold=0.10,
        )

    builder.set_column_widths(
        package_sheet,
        {
            1: 12,
            2: 22,
            3: 24,
            4: 10,
            5: 9,
            6: 11,
            7: 15,
            8: 14,
            9: 14,
            10: 14,
            11: 16,
            12: 16,
            13: 9,
            14: 12,
            15: 10,
        },
    )
    builder.normalize_sheet(package_sheet, max_column=package_last_column)

    builder.write_report_header(
        check_sheet,
        last_column=15,
        subtitle="Çek bazlı formüllü iskonto maliyet tablosu",
    )

    check_headers = [
        "Paket",
        "Çek No",
        "Müşteri",
        "Keşide Bankası",
        "Vade",
        "Gün",
        "Brüt",
        "Faiz",
        "Komisyon",
        "BSMV",
        "Masraf",
        "Net",
        "Para",
        "Masraf %",
        "Net %",
    ]

    check_next_row, check_last_column = builder.write_table(
        check_sheet,
        start_row=5,
        start_column=1,
        title="Pakette Kullanılan Çekler",
        headers=check_headers,
        rows=_check_table_rows(report_data),
        number_formats={
            0: builder.integer_format,
            4: builder.date_format,
            5: builder.integer_format,
            6: builder.number_format,
            7: builder.number_format,
            8: builder.number_format,
            9: builder.number_format,
            10: builder.number_format,
            11: builder.number_format,
            13: builder.percent_format,
            14: builder.percent_format,
        },
        formula_columns={
            10: "=H{row}+I{row}+J{row}",
            11: "=G{row}-K{row}",
            13: "=IF(G{row}=0,0,K{row}/G{row})",
            14: "=IF(G{row}=0,0,L{row}/G{row})",
        },
        row_styles=_check_row_styles(report_data),
        auto_filter=True,
        freeze_panes="A7",
    )

    check_data_start_row = None
    check_last_data_row = None

    if report_data.check_rows:
        check_total_row = check_next_row - 2
        check_data_start_row = 7
        check_last_data_row = check_total_row - 1

        builder.apply_conditional_percent_scale(
            check_sheet,
            range_address=f"N7:N{check_last_data_row}",
            warning_threshold=0.05,
            risk_threshold=0.10,
        )

    builder.set_column_widths(
        check_sheet,
        {
            1: 10,
            2: 16,
            3: 26,
            4: 22,
            5: 12,
            6: 8,
            7: 15,
            8: 14,
            9: 14,
            10: 14,
            11: 15,
            12: 15,
            13: 9,
            14: 12,
            15: 10,
        },
    )
    builder.normalize_sheet(check_sheet, max_column=check_last_column)

    _write_summary_sheet(
        builder=builder,
        worksheet=summary_sheet,
        report_data=report_data,
        package_total_row=package_total_row,
        check_data_start_row=check_data_start_row,
        check_last_data_row=check_last_data_row,
    )

    return builder.save()


def create_financing_cost_report_excel(
    *,
    output_path: str | Path,
    report_filter: FinancingCostReportFilter,
    created_by: str,
) -> str:
    report_data = load_financing_cost_report_data(report_filter)

    return build_financing_cost_report_excel(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_current_month_financing_cost_report_excel(
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

    return create_financing_cost_report_excel(
        output_path=output_path,
        report_filter=report_filter,
        created_by=created_by,
    )


__all__ = [
    "build_financing_cost_report_excel",
    "create_financing_cost_report_excel",
    "create_default_current_month_financing_cost_report_excel",
]