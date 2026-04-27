from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.reports.check_due_report_data import (
    CheckDueReportData,
    CheckDueReportFilter,
    CheckDueReportRow,
    load_check_due_report_data,
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


def _report_filter_summary_text(report_filter: CheckDueReportFilter) -> str:
    check_type_text = _filter_text(
        report_filter.check_type,
        {
            "ALL": "Tümü",
            "RECEIVED": "Alınan",
            "ISSUED": "Yazılan",
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
        f"Durum Grubu: {status_group_text} | "
        f"Para Birimi: {currency_text}"
    )


def _detail_table_rows(report_data: CheckDueReportData) -> list[list[Any]]:
    rows: list[list[Any]] = []

    for row in report_data.rows:
        rows.append(
            [
                row.check_type_text,
                row.status_group_text,
                row.status_text,
                row.party_name,
                row.check_number,
                _date_or_none(row.due_date),
                row.days_difference,
                row.days_text,
                _decimal_to_float(row.amount),
                row.currency_code,
                None,
                row.reference_no or "",
                row.description or "",
            ]
        )

    return rows


def _detail_row_styles(report_data: CheckDueReportData) -> list[str]:
    return [
        row.row_style
        for row in report_data.rows
    ]


def _summary_formula_or_zero(formula: str, has_rows: bool) -> str | int:
    if not has_rows:
        return 0

    return formula


def _write_summary_sheet(
    *,
    builder: FtmExcelReportBuilder,
    worksheet,
    report_data: CheckDueReportData,
    detail_total_row: int | None,
    detail_data_start_row: int | None,
    detail_last_data_row: int | None,
) -> None:
    builder.write_report_header(
        worksheet,
        last_column=12,
        subtitle=_report_filter_summary_text(report_data.filters),
    )

    has_rows = (
        detail_total_row is not None
        and detail_data_start_row is not None
        and detail_last_data_row is not None
    )

    if has_rows:
        type_range = f"'Çek Detayı'!A{detail_data_start_row}:A{detail_last_data_row}"
        status_group_range = f"'Çek Detayı'!B{detail_data_start_row}:B{detail_last_data_row}"
        due_day_range = f"'Çek Detayı'!G{detail_data_start_row}:G{detail_last_data_row}"
        amount_range = f"'Çek Detayı'!I{detail_data_start_row}:I{detail_last_data_row}"
        cash_effect_range = f"'Çek Detayı'!K{detail_data_start_row}:K{detail_last_data_row}"

        total_count = f"=COUNTA('Çek Detayı'!E{detail_data_start_row}:E{detail_last_data_row})"
        received_count = f'=COUNTIF({type_range},"Alınan")'
        issued_count = f'=COUNTIF({type_range},"Yazılan")'
        pending_count = f'=COUNTIF({status_group_range},"Bekleyen")'
        closed_count = f'=COUNTIF({status_group_range},"Sonuçlanan")'
        problem_count = f'=COUNTIF({status_group_range},"Problemli")'
        overdue_count = f'=COUNTIF({due_day_range},"<0")'
        today_count = f'=COUNTIF({due_day_range},0)'
        next_7_count = f'=COUNTIFS({due_day_range},">=0",{due_day_range},"<=7")'
        next_30_count = f'=COUNTIFS({due_day_range},">=0",{due_day_range},"<=30")'
        received_total = f'=SUMIF({type_range},"Alınan",{amount_range})'
        issued_total = f'=SUMIF({type_range},"Yazılan",{amount_range})'
        pending_total = f'=SUMIF({status_group_range},"Bekleyen",{amount_range})'
        problem_total = f'=SUMIF({status_group_range},"Problemli",{amount_range})'
        net_effect_total = f"=SUBTOTAL(109,{cash_effect_range})"
    else:
        total_count = 0
        received_count = 0
        issued_count = 0
        pending_count = 0
        closed_count = 0
        problem_count = 0
        overdue_count = 0
        today_count = 0
        next_7_count = 0
        next_30_count = 0
        received_total = 0
        issued_total = 0
        pending_total = 0
        problem_total = 0
        net_effect_total = 0

    cards = [
        FtmExcelSummaryCard(
            title="Toplam Çek",
            value=total_count,
            hint="Rapor kapsamındaki toplam çek sayısı",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Alınan Çek",
            value=received_count,
            hint="Müşterilerden alınan çek adedi",
            card_type="success",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Yazılan Çek",
            value=issued_count,
            hint="Tedarikçilere verilen çek adedi",
            card_type="risk",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Bekleyen",
            value=pending_count,
            hint="Henüz sonuçlanmamış çekler",
            card_type="warning",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Sonuçlanan",
            value=closed_count,
            hint="Tahsil / ödeme / kapanış yapılmış çekler",
            card_type="normal",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Problemli",
            value=problem_count,
            hint="Riskli veya karşılıksız çekler",
            card_type="risk",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Vadesi Geçen",
            value=overdue_count,
            hint="Bekleyen ve vadesi geçmiş kayıtlar",
            card_type="risk",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Bugün Vadeli",
            value=today_count,
            hint="Bugün vadesi gelen çekler",
            card_type="warning",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="7 Gün İçinde",
            value=next_7_count,
            hint="Bugünden itibaren 7 gün içindeki çekler",
            card_type="warning",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="30 Gün İçinde",
            value=next_30_count,
            hint="Bugünden itibaren 30 gün içindeki çekler",
            card_type="info",
            number_format=builder.integer_format,
        ),
        FtmExcelSummaryCard(
            title="Alınan Toplam",
            value=received_total,
            hint="Alınan çeklerin toplam tutarı",
            card_type="success",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Yazılan Toplam",
            value=issued_total,
            hint="Yazılan çeklerin toplam tutarı",
            card_type="risk",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Bekleyen Toplam",
            value=pending_total,
            hint="Bekleyen çeklerin toplam tutarı",
            card_type="warning",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Problemli Toplam",
            value=problem_total,
            hint="Problemli çeklerin toplam tutarı",
            card_type="risk",
            number_format=builder.number_format,
        ),
        FtmExcelSummaryCard(
            title="Net Nakit Etkisi",
            value=net_effect_total,
            hint="Alınan çekler (+), yazılan çekler (-)",
            card_type="info",
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
        start_row=22,
        start_column=1,
        title="Rapor Açıklaması",
        rows=[
            ("Rapor Türü", "Çek Listesi Excel", None),
            ("Rapor Dönemi", report_data.report_period_text, None),
            ("Filtreler", _report_filter_summary_text(report_data.filters), None),
            ("Nakit Etkisi", "Alınan çekler pozitif, yazılan çekler negatif etki olarak hesaplanır.", None),
            ("Formül Mantığı", "Özet alanları Çek Detayı sayfasındaki filtrelenebilir tablodan hesaplanır.", None),
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


def build_check_due_report_excel(
    *,
    output_path: str | Path,
    report_data: CheckDueReportData,
    created_by: str,
) -> str:
    builder = FtmExcelReportBuilder(
        output_path=output_path,
        meta=FtmExcelMeta(
            title="Çek Listesi Raporu",
            report_period=report_data.report_period_text,
            created_by=created_by,
            created_at=datetime.now(),
        ),
    )

    summary_sheet = builder.add_sheet("Özet", freeze_panes="A5")
    detail_sheet = builder.add_sheet("Çek Detayı", freeze_panes="A7")

    builder.write_report_header(
        detail_sheet,
        last_column=13,
        subtitle="Filtrelenebilir ve formüllü çek detay tablosu",
    )

    headers = [
        "Tür",
        "Durum Grubu",
        "Durum",
        "Taraf",
        "Çek No",
        "Vade",
        "Gün Farkı",
        "Gün Açıklama",
        "Tutar",
        "Para",
        "Nakit Etkisi",
        "Referans",
        "Açıklama",
    ]

    next_row, last_column = builder.write_table(
        detail_sheet,
        start_row=5,
        start_column=1,
        title="Çek Detayı",
        headers=headers,
        rows=_detail_table_rows(report_data),
        number_formats={
            5: builder.date_format,
            6: builder.integer_format,
            8: builder.number_format,
            10: builder.number_format,
        },
        formula_columns={
            10: '=IF(A{row}="Alınan",I{row},-I{row})',
        },
        row_styles=_detail_row_styles(report_data),
        auto_filter=True,
        freeze_panes="A7",
    )

    detail_total_row = None
    detail_data_start_row = None
    detail_last_data_row = None

    if report_data.rows:
        detail_total_row = next_row - 2
        detail_data_start_row = 7
        detail_last_data_row = detail_total_row - 1

    builder.set_column_widths(
        detail_sheet,
        {
            1: 12,
            2: 15,
            3: 16,
            4: 28,
            5: 18,
            6: 12,
            7: 11,
            8: 16,
            9: 15,
            10: 9,
            11: 16,
            12: 18,
            13: 34,
        },
    )
    builder.normalize_sheet(detail_sheet, max_column=last_column)

    _write_summary_sheet(
        builder=builder,
        worksheet=summary_sheet,
        report_data=report_data,
        detail_total_row=detail_total_row,
        detail_data_start_row=detail_data_start_row,
        detail_last_data_row=detail_last_data_row,
    )

    return builder.save()


def create_check_due_report_excel(
    *,
    output_path: str | Path,
    report_filter: CheckDueReportFilter,
    created_by: str,
) -> str:
    report_data = load_check_due_report_data(report_filter)

    return build_check_due_report_excel(
        output_path=output_path,
        report_data=report_data,
        created_by=created_by,
    )


def create_default_next_30_days_check_due_report_excel(
    *,
    output_path: str | Path,
    created_by: str = "FTM Kullanıcısı",
) -> str:
    today = date.today()

    return create_check_due_report_excel(
        output_path=output_path,
        report_filter=CheckDueReportFilter(
            start_date=today,
            end_date=today + timedelta(days=30),
            check_type="ALL",
            status_group="ALL",
            currency_code="ALL",
        ),
        created_by=created_by,
    )


__all__ = [
    "build_check_due_report_excel",
    "create_check_due_report_excel",
    "create_default_next_30_days_check_due_report_excel",
]