from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

from sqlalchemy import select

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.session import session_scope
from app.models.bank import Bank, BankAccount
from app.models.bank_transaction import BankTransaction
from app.reports.bank_movement_report_data import (
    BankMovementReportFilter,
    load_bank_movement_report_data,
)
from app.reports.check_due_report_data import (
    CheckDueReportFilter,
    load_check_due_report_data,
)
from app.reports.pos_settlement_report_data import (
    PosSettlementReportFilter,
    load_pos_settlement_report_data,
)
from app.reports.report_theme import (
    FTM_REPORT_THEME,
    FtmReportFonts,
    register_ftm_report_fonts,
)
from app.reports.risk_check_report_data import (
    RiskCheckReportFilter,
    load_risk_check_report_data,
)

try:
    from app.core.branding import get_report_logo_path
except Exception:  # pragma: no cover - eski kurulumlarda logo modülü olmayabilir
    get_report_logo_path = None  # type: ignore[assignment]


ZERO = Decimal("0.00")
MONEY_QUANT = Decimal("0.01")

RECEIVED_PENDING_STATUS_GROUP = "PENDING"
ISSUED_PENDING_STATUS_GROUP = "PENDING"

REPORT_STATUS_NORMAL = "NORMAL"
REPORT_STATUS_ATTENTION = "DIKKAT"
REPORT_STATUS_RISK = "RISKLI"

STANDARD_TABLE_WIDTH_MM = 262.0
TWO_COLUMN_GAP_MM = 6.0
TWO_COLUMN_WIDTH_MM = (STANDARD_TABLE_WIDTH_MM - TWO_COLUMN_GAP_MM) / 2


@dataclass(frozen=True)
class ManagementSignatureReportContext:
    start_date: date
    end_date: date
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class ManagementSignatureReportData:
    context: ManagementSignatureReportContext
    today_data: Any
    range_7_data: Any
    range_15_data: Any
    range_30_data: Any
    received_detail_data: Any
    issued_detail_data: Any
    bank_data: Any
    current_bank_account_rows: list[dict[str, Any]]
    pos_data: Any
    risk_data: Any
    currency_positions: list[dict[str, Any]]
    daily_pressure_rows: list[dict[str, Any]]
    partner_summary_rows: list[dict[str, Any]]
    critical_due_rows: list[Any]
    critical_alerts: list[str]
    recommended_actions: list[str]
    decision_sentence: str
    general_status: str


class _SignaturePdfBuilder:
    def __init__(self, *, output_path: str | Path, data: ManagementSignatureReportData) -> None:
        self.output_path = Path(output_path)
        self.data = data
        self.fonts: FtmReportFonts = register_ftm_report_fonts()
        self.pagesize = landscape(A4)
        self.styles = self._build_styles()
        self.logo_path = _safe_logo_path()

    def build(self) -> str:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        document = SimpleDocTemplate(
            str(self.output_path),
            pagesize=self.pagesize,
            rightMargin=11 * mm,
            leftMargin=11 * mm,
            topMargin=25 * mm,
            bottomMargin=15 * mm,
            title="FTM Finansal Yönetim İmza Raporu",
            author=self.data.context.created_by,
            subject=_date_range_text(self.data.context.start_date, self.data.context.end_date),
        )

        elements = self._build_elements()

        document.build(
            elements,
            onFirstPage=self._draw_header_footer,
            onLaterPages=self._draw_header_footer,
        )

        return str(self.output_path)

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        return {
            "cover_title": ParagraphStyle(
                name="FTMSignatureCoverTitle",
                fontName=self.fonts.bold,
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
                spaceAfter=4,
            ),
            "cover_subtitle": ParagraphStyle(
                name="FTMSignatureCoverSubtitle",
                fontName=self.fonts.regular,
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#475569"),
                alignment=TA_LEFT,
            ),
            "section": ParagraphStyle(
                name="FTMSignatureSection",
                fontName=self.fonts.bold,
                fontSize=10.5,
                leading=13,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
                spaceBefore=6,
                spaceAfter=5,
            ),
            "normal": ParagraphStyle(
                name="FTMSignatureNormal",
                fontName=self.fonts.regular,
                fontSize=7.2,
                leading=9.2,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
            ),
            "small": ParagraphStyle(
                name="FTMSignatureSmall",
                fontName=self.fonts.regular,
                fontSize=6.6,
                leading=8.2,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_LEFT,
            ),
            "tiny": ParagraphStyle(
                name="FTMSignatureTiny",
                fontName=self.fonts.regular,
                fontSize=6.0,
                leading=7.3,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_LEFT,
            ),
            "decision": ParagraphStyle(
                name="FTMSignatureDecision",
                fontName=self.fonts.bold,
                fontSize=9,
                leading=11.5,
                textColor=colors.HexColor("#111827"),
                alignment=TA_LEFT,
            ),
            "card_title": ParagraphStyle(
                name="FTMSignatureCardTitle",
                fontName=self.fonts.bold,
                fontSize=7,
                leading=8.5,
                textColor=colors.HexColor("#334155"),
                alignment=TA_LEFT,
            ),
            "card_value": ParagraphStyle(
                name="FTMSignatureCardValue",
                fontName=self.fonts.bold,
                fontSize=11,
                leading=13,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
            ),
            "card_hint": ParagraphStyle(
                name="FTMSignatureCardHint",
                fontName=self.fonts.regular,
                fontSize=6.4,
                leading=7.7,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_LEFT,
            ),
            "table_header": ParagraphStyle(
                name="FTMSignatureTableHeader",
                fontName=self.fonts.bold,
                fontSize=6.4,
                leading=7.6,
                textColor=colors.white,
                alignment=TA_CENTER,
            ),
            "table_cell": ParagraphStyle(
                name="FTMSignatureTableCell",
                fontName=self.fonts.regular,
                fontSize=6.3,
                leading=7.4,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_LEFT,
            ),
            "table_cell_right": ParagraphStyle(
                name="FTMSignatureTableCellRight",
                fontName=self.fonts.regular,
                fontSize=6.3,
                leading=7.4,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_RIGHT,
            ),
            "table_cell_center": ParagraphStyle(
                name="FTMSignatureTableCellCenter",
                fontName=self.fonts.regular,
                fontSize=6.3,
                leading=7.4,
                textColor=colors.HexColor("#0f172a"),
                alignment=TA_CENTER,
            ),
        }

    def _build_elements(self) -> list[Any]:
        elements: list[Any] = []

        elements.extend(self._build_cover_page())
        elements.append(PageBreak())

        elements.extend(self._build_position_page())
        elements.append(PageBreak())

        elements.extend(self._build_due_and_pressure_page())
        elements.append(PageBreak())

        elements.extend(self._build_partner_summary_page())
        elements.append(PageBreak())

        elements.extend(self._build_received_checks_appendix())
        elements.append(PageBreak())

        elements.extend(self._build_issued_checks_appendix())
        elements.append(PageBreak())

        elements.extend(self._build_bank_movements_appendix())
        elements.append(PageBreak())

        elements.extend(self._build_pos_appendix())
        elements.append(PageBreak())

        elements.extend(self._build_risk_appendix())
        elements.append(PageBreak())

        elements.extend(self._build_partner_appendix())

        return elements

    def _build_cover_page(self) -> list[Any]:
        data = self.data
        context = data.context

        elements: list[Any] = []
        elements.append(self._build_cover_header())
        elements.append(Spacer(1, 5 * mm))

        status_text = _status_text(data.general_status)
        status_description = _status_description(data.general_status)
        status_fill = _status_fill_color(data.general_status)

        decision_table = Table(
            [
                [
                    self.p("Durum", "card_title"),
                    self.p(status_text, "card_value"),
                    self.p("Rapor Dönemi", "card_title"),
                    self.p(_date_range_text(context.start_date, context.end_date), "decision"),
                ],
                [
                    self.p("Açıklama", "card_title"),
                    self.p(status_description, "decision"),
                    self.p("Rapor Saati", "card_title"),
                    self.p(context.created_at.strftime("%d.%m.%Y %H:%M"), "decision"),
                ],
                [
                    self.p("Yönetim Karar Cümlesi", "card_title"),
                    self.p(data.decision_sentence, "decision"),
                    self.p("Oluşturan", "card_title"),
                    self.p(context.created_by, "decision"),
                ],
            ],
            colWidths=[26 * mm, 119 * mm, 25 * mm, 92 * mm],
            hAlign="LEFT",
        )
        decision_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BACKGROUND", (1, 0), (1, 0), status_fill),
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(decision_table)
        elements.append(Spacer(1, 5 * mm))

        elements.append(
            self._build_summary_cards(
                [
                    {
                        "title": "Bugün Net Çek",
                        "value": _format_totals(data.today_data.summary.net_effect_totals),
                        "hint": f"Tahsilat: {_format_totals(data.today_data.summary.received_totals)} | Ödeme: {_format_totals(data.today_data.summary.issued_totals)}",
                        "variant": _variant_for_net(data.today_data.summary.net_effect_totals),
                    },
                    {
                        "title": "7 Gün Net Çek",
                        "value": _format_totals(data.range_7_data.summary.net_effect_totals),
                        "hint": f"Tahsilat: {_format_totals(data.range_7_data.summary.received_totals)} | Ödeme: {_format_totals(data.range_7_data.summary.issued_totals)}",
                        "variant": _variant_for_net(data.range_7_data.summary.net_effect_totals),
                    },
                    {
                        "title": "30 Gün Net Çek",
                        "value": _format_totals(data.range_30_data.summary.net_effect_totals),
                        "hint": f"Tahsilat: {_format_totals(data.range_30_data.summary.received_totals)} | Ödeme: {_format_totals(data.range_30_data.summary.issued_totals)}",
                        "variant": _variant_for_net(data.range_30_data.summary.net_effect_totals),
                    },
                    {
                        "title": "Takip Gerektiren Kayıtlar",
                        "value": f"{data.risk_data.summary.total_count} kayıt",
                        "hint": f"Problemli: {data.risk_data.summary.problem_count} | Gecikmiş: {data.risk_data.summary.overdue_count} | Tutar: {_format_totals(data.risk_data.summary.grand_totals)}",
                        "variant": "warning" if data.risk_data.summary.total_count else "positive",
                    },
                ]
            )
        )
        elements.append(Spacer(1, 5 * mm))

        action_table = Table(
            [
                [
                    self._build_titled_block(
                        "Bugün Yapılacak İlk Aksiyonlar",
                        self._build_numbered_list(data.recommended_actions[:5], width_mm=TWO_COLUMN_WIDTH_MM),
                        width_mm=TWO_COLUMN_WIDTH_MM,
                    ),
                    "",
                    self._build_titled_block(
                        "Kritik Uyarılar",
                        self._build_numbered_list(data.critical_alerts[:8], width_mm=TWO_COLUMN_WIDTH_MM),
                        width_mm=TWO_COLUMN_WIDTH_MM,
                    ),
                ]
            ],
            colWidths=[TWO_COLUMN_WIDTH_MM * mm, TWO_COLUMN_GAP_MM * mm, TWO_COLUMN_WIDTH_MM * mm],
            hAlign="LEFT",
        )
        action_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(action_table)

        return elements

    def _build_position_page(self) -> list[Any]:
        elements: list[Any] = []

        elements.append(self.section("Güncel Banka Hesap Görünümü"))
        elements.append(
            self.table(
                headers=["Banka", "Hesap", "PB", "Açılış", "Giriş", "Çıkış", "Güncel Bakiye", "Not"],
                rows=[
                    [
                        row["bank_name"],
                        row["account_name"],
                        row["currency_code"],
                        _format_decimal(row["opening_balance"]),
                        _format_decimal(row["realized_in"]),
                        _format_decimal(row["realized_out"]),
                        _format_decimal(row["current_balance"]),
                        row["note"],
                    ]
                    for row in self.data.current_bank_account_rows[:18]
                ]
                or [["-", "-", "-", "-", "-", "-", "-", "Tanımlı banka hesabı bulunmuyor."]],
                col_widths=[38, 38, 12, 28, 30, 30, 34, 52],
                numeric_columns={3, 4, 5, 6},
                row_statuses=[row["row_status"] for row in self.data.current_bank_account_rows[:18]],
            )
        )
        elements.append(Spacer(1, 5 * mm))

        elements.append(self.section("Para Birimi Bazlı Net Pozisyon"))
        elements.append(
            self.table(
                headers=["Para Birimi", "Tahsilat", "Ödeme", "Net", "Yorum"],
                rows=[
                    [
                        row["currency_code"],
                        _format_decimal(row["received"]),
                        _format_decimal(row["issued"]),
                        _format_signed_decimal(row["net"]),
                        row["comment"],
                    ]
                    for row in self.data.currency_positions
                ],
                col_widths=[24, 48, 48, 48, 94],
                numeric_columns={1, 2, 3},
                row_statuses=[row["row_status"] for row in self.data.currency_positions],
            )
        )
        elements.append(Spacer(1, 5 * mm))

        pos_rows = [
            [
                summary.pos_device_name,
                summary.bank_name,
                summary.account_name,
                summary.record_count,
                _format_totals(summary.expected_net_totals),
                _format_totals(summary.actual_net_totals),
                _format_totals(summary.difference_totals),
            ]
            for summary in self.data.pos_data.summary.device_summaries[:12]
        ]
        if not pos_rows:
            pos_rows = [["-", "-", "-", "-", "-", "-", "-"]]

        elements.append(self.section("POS Beklenen / Fark Özeti"))
        elements.append(
            self.table(
                headers=["POS", "Banka", "Hesap", "Kayıt", "Beklenen", "Gerçek", "Fark"],
                rows=pos_rows,
                col_widths=[42, 40, 40, 18, 40, 40, 42],
                numeric_columns={3, 4, 5, 6},
            )
        )
        return elements

    def _build_partner_summary_page(self) -> list[Any]:
        elements: list[Any] = []
        elements.append(self.section("Kritik Muhataplar"))
        elements.append(
            self.table(
                headers=["Muhatap", "Tip", "Alınan Açık", "Yazılan Açık", "Problem/Gecikme", "Net", "Durum"],
                rows=[
                    [
                        row["party_name"],
                        row["party_type"],
                        _format_totals(row["received_totals"]),
                        _format_totals(row["issued_totals"]),
                        row["risk_count"],
                        _format_totals(row["net_totals"]),
                        row["status_text"],
                    ]
                    for row in self.data.partner_summary_rows[:18]
                ]
                or [["-", "-", "-", "-", "-", "-", "-"]],
                col_widths=[58, 26, 38, 38, 28, 39, 35],
                numeric_columns={2, 3, 4, 5},
                row_statuses=[row["row_status"] for row in self.data.partner_summary_rows[:18]],
            )
        )
        elements.append(Spacer(1, 5 * mm))

        bank_rows = [
            [
                summary.bank_name,
                summary.account_name,
                summary.currency_code,
                summary.transaction_count,
                _format_totals(summary.incoming_totals),
                _format_totals(summary.outgoing_totals),
                _format_totals(summary.net_totals),
            ]
            for summary in self.data.bank_data.summary.account_summaries[:18]
        ]
        if not bank_rows:
            bank_rows = [["-", "-", "-", "-", "-", "-", "-"]]

        elements.append(self.section("Banka Hareket Özeti"))
        elements.append(
            self.table(
                headers=["Banka", "Hesap", "PB", "Kayıt", "Giriş", "Çıkış", "Net"],
                rows=bank_rows,
                col_widths=[45, 45, 14, 18, 45, 45, 50],
                numeric_columns={3, 4, 5, 6},
            )
        )
        return elements

    def _build_due_and_pressure_page(self) -> list[Any]:
        elements: list[Any] = []
        elements.append(self.section("Yaklaşan Kritik Vadeler"))
        elements.append(
            self.table(
                headers=["Tarih", "Tür", "Muhatap", "Çek No", "Tutar", "Durum", "Kalan", "Açıklama"],
                rows=[
                    [
                        _format_date(row.due_date),
                        row.check_type_text,
                        row.party_name,
                        row.check_number,
                        f"{_format_decimal(row.amount)} {row.currency_code}",
                        row.status_text,
                        row.days_text,
                        _clean_text(row.description),
                    ]
                    for row in self.data.critical_due_rows[:25]
                ]
                or [["-", "-", "-", "-", "-", "-", "-", "Rapor döneminde kritik vade bulunmuyor."]],
                col_widths=[18, 17, 48, 25, 28, 24, 19, 73],
                numeric_columns={4},
                row_statuses=[_row_status_from_due(row) for row in self.data.critical_due_rows[:25]],
            )
        )
        elements.append(Spacer(1, 5 * mm))
        elements.append(self.section("30 Günlük Nakit Baskısı"))
        elements.append(
            self.table(
                headers=["Tarih", "Tahsilat", "Ödeme", "Net", "Kayıt", "Yorum"],
                rows=[
                    [
                        _format_date(row["date"]),
                        _format_totals(row["received_totals"]),
                        _format_totals(row["issued_totals"]),
                        _format_totals(row["net_totals"]),
                        f"{row['record_count']} kayıt",
                        row["comment"],
                    ]
                    for row in self.data.daily_pressure_rows[:30]
                ]
                or [["-", "-", "-", "-", "-", "Rapor döneminde çek kaynaklı nakit baskısı görünmüyor."]],
                col_widths=[20, 48, 48, 48, 22, 69],
                numeric_columns={1, 2, 3},
                row_statuses=[row["row_status"] for row in self.data.daily_pressure_rows[:30]],
            )
        )
        return elements

    def _build_received_checks_appendix(self) -> list[Any]:
        rows = [
            [
                _format_date(row.due_date),
                row.party_name,
                row.check_number,
                row.reference_no,
                row.currency_code,
                _format_decimal(row.amount),
                row.status_text,
                row.days_text,
                _clean_text(row.description),
            ]
            for row in self.data.received_detail_data.rows
        ]
        return self._build_appendix_table(
            title="Ek-1: Rapor Dönemine Ait Alınan Çek Listesi",
            subtitle=f"Dönem: {self.data.received_detail_data.report_period_text} | Kayıt: {len(rows)} | Toplam: {_format_totals(self.data.received_detail_data.summary.received_totals)}",
            headers=["Vade", "Muhatap", "Çek No", "Referans", "PB", "Tutar", "Durum", "Kalan", "Açıklama"],
            rows=rows,
            empty_text="Rapor döneminde alınan çek kaydı bulunmuyor.",
            col_widths=[18, 48, 25, 25, 11, 27, 25, 22, 50],
            numeric_columns={5},
            row_statuses=[row.row_style for row in self.data.received_detail_data.rows],
        )

    def _build_issued_checks_appendix(self) -> list[Any]:
        rows = [
            [
                _format_date(row.due_date),
                row.party_name,
                row.check_number,
                row.reference_no,
                row.currency_code,
                _format_decimal(row.amount),
                row.status_text,
                row.days_text,
                _clean_text(row.description),
            ]
            for row in self.data.issued_detail_data.rows
        ]
        return self._build_appendix_table(
            title="Ek-2: Rapor Dönemine Ait Yazılan Çek Listesi",
            subtitle=f"Dönem: {self.data.issued_detail_data.report_period_text} | Kayıt: {len(rows)} | Toplam: {_format_totals(self.data.issued_detail_data.summary.issued_totals)}",
            headers=["Vade", "Muhatap", "Çek No", "Referans", "PB", "Tutar", "Durum", "Kalan", "Açıklama"],
            rows=rows,
            empty_text="Rapor döneminde yazılan çek kaydı bulunmuyor.",
            col_widths=[18, 48, 25, 25, 11, 27, 25, 22, 50],
            numeric_columns={5},
            row_statuses=[row.row_style for row in self.data.issued_detail_data.rows],
        )

    def _build_bank_movements_appendix(self) -> list[Any]:
        rows = [
            [
                _format_date(row.transaction_date),
                row.bank_name,
                row.account_name,
                row.direction_text,
                row.status_text,
                row.source_type_text,
                row.currency_code,
                _format_decimal(row.amount),
                row.reference_no,
                _clean_text(row.description),
            ]
            for row in self.data.bank_data.rows
        ]
        return self._build_appendix_table(
            title="Ek-3: Banka Hesap Hareketleri",
            subtitle=(
                f"Dönem: {self.data.bank_data.report_period_text} | Kayıt: {len(rows)} | "
                f"Giriş: {_format_totals(self.data.bank_data.summary.incoming_totals)} | "
                f"Çıkış: {_format_totals(self.data.bank_data.summary.outgoing_totals)} | "
                f"Net: {_format_totals(self.data.bank_data.summary.net_totals)}"
            ),
            headers=["Tarih", "Banka", "Hesap", "Yön", "Durum", "Kaynak", "PB", "Tutar", "Referans", "Açıklama"],
            rows=rows,
            empty_text="Rapor döneminde banka hesap hareketi bulunmuyor.",
            col_widths=[18, 26, 32, 15, 20, 28, 10, 25, 24, 50],
            numeric_columns={7},
            row_statuses=[row.row_style for row in self.data.bank_data.rows],
        )

    def _build_pos_appendix(self) -> list[Any]:
        rows = [
            [
                _format_date(row.transaction_date),
                _format_date(row.expected_settlement_date),
                row.pos_device_name,
                row.bank_name,
                row.currency_code,
                _format_decimal(row.gross_amount),
                _format_decimal(row.commission_amount),
                _format_decimal(row.net_amount),
                row.status_text,
                _format_decimal(row.difference_amount),
                _clean_text(row.difference_reason or row.description),
            ]
            for row in self.data.pos_data.rows
        ]
        return self._build_appendix_table(
            title="Ek-4: POS Hareketleri ve Mutabakat Farkları",
            subtitle=(
                f"Dönem: {self.data.pos_data.report_period_text} | Kayıt: {len(rows)} | "
                f"Beklenen Net: {_format_totals(self.data.pos_data.summary.expected_net_totals)} | "
                f"Fark: {_format_totals(self.data.pos_data.summary.difference_totals)}"
            ),
            headers=["İşlem", "Beklenen", "POS", "Banka", "PB", "Brüt", "Komisyon", "Net", "Durum", "Fark", "Açıklama"],
            rows=rows,
            empty_text="Rapor döneminde POS hareketi bulunmuyor.",
            col_widths=[16, 16, 30, 24, 9, 22, 22, 22, 20, 18, 48],
            numeric_columns={5, 6, 7, 9},
            row_statuses=[row.row_style for row in self.data.pos_data.rows],
        )

    def _build_risk_appendix(self) -> list[Any]:
        rows = [
            [
                row.risk_type_text,
                row.check_type_text,
                row.party_name,
                row.check_number,
                _format_date(row.due_date),
                row.delay_text,
                row.currency_code,
                _format_decimal(row.amount),
                row.status_text,
                _clean_text(row.description),
            ]
            for row in self.data.risk_data.rows
        ]
        return self._build_appendix_table(
            title="Ek-5: Riskli / Problemli / Vadesi Geçmiş Çekler",
            subtitle=(
                f"Dönem: {self.data.risk_data.report_period_text} | Kayıt: {len(rows)} | "
                f"Problemli: {self.data.risk_data.summary.problem_count} | "
                f"Vadesi Geçmiş: {self.data.risk_data.summary.overdue_count} | "
                f"Tutar: {_format_totals(self.data.risk_data.summary.grand_totals)}"
            ),
            headers=["Risk", "Tür", "Muhatap", "Çek No", "Vade", "Gecikme", "PB", "Tutar", "Durum", "Açıklama"],
            rows=rows,
            empty_text="Rapor döneminde riskli/problemli/vadesi geçmiş çek bulunmuyor.",
            col_widths=[25, 15, 44, 22, 17, 24, 9, 23, 22, 55],
            numeric_columns={7},
            row_statuses=[row.row_style for row in self.data.risk_data.rows],
        )

    def _build_partner_appendix(self) -> list[Any]:
        rows = [
            [
                row["party_name"],
                row["party_type"],
                _format_totals(row["received_totals"]),
                _format_totals(row["issued_totals"]),
                row["risk_count"],
                _format_totals(row["net_totals"]),
                row["status_text"],
            ]
            for row in self.data.partner_summary_rows
        ]
        return self._build_appendix_table(
            title="Ek-6: Muhatap Bazlı Özet",
            subtitle="Rapor dönemindeki açık çek pozisyonu ve risk kayıtları muhatap bazında özetlenmiştir.",
            headers=["Muhatap", "Tip", "Alınan Açık", "Yazılan Açık", "Risk", "Net", "Durum"],
            rows=rows,
            empty_text="Rapor döneminde muhatap bazlı pozisyon bulunmuyor.",
            col_widths=[58, 28, 40, 40, 18, 42, 30],
            numeric_columns={2, 3, 4, 5},
            row_statuses=[row["row_status"] for row in self.data.partner_summary_rows],
        )

    def _build_appendix_table(
        self,
        *,
        title: str,
        subtitle: str,
        headers: list[str],
        rows: list[list[Any]],
        empty_text: str,
        col_widths: list[float],
        numeric_columns: set[int] | None = None,
        center_columns: set[int] | None = None,
        row_statuses: list[str] | None = None,
    ) -> list[Any]:
        output_rows = rows or [["-" for _ in headers[:-1]] + [empty_text]]
        return [
            self.section(title),
            self.p(subtitle, "small"),
            Spacer(1, 3 * mm),
            self.table(
                headers=headers,
                rows=output_rows,
                col_widths=col_widths,
                numeric_columns=numeric_columns,
                center_columns=center_columns,
                row_statuses=row_statuses,
            ),
        ]

    def _build_cover_header(self) -> Table:
        header = Table(
            [
                [self.p("FTM Finansal Yönetim İmza Raporu", "cover_title")],
                [
                    self.p(
                        "Önde yönetici özeti, arkada rapora konu olan çek, banka, POS ve muhatap detayları.",
                        "cover_subtitle",
                    )
                ],
            ],
            colWidths=[STANDARD_TABLE_WIDTH_MM * mm],
            hAlign="LEFT",
        )
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return header

    def _build_titled_block(self, title: str, body: Any, *, width_mm: float) -> Table:
        block = Table(
            [[self.section(title)], [body]],
            colWidths=[width_mm * mm],
            hAlign="LEFT",
        )
        block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return block

    def _build_summary_cards(self, cards: list[dict[str, str]]) -> Table:
        column_width = (STANDARD_TABLE_WIDTH_MM - (TWO_COLUMN_GAP_MM * 3)) / 4
        table_data: list[list[Any]] = [[]]
        col_widths: list[float] = []

        for index, card in enumerate(cards):
            if index > 0:
                table_data[0].append("")
                col_widths.append(TWO_COLUMN_GAP_MM * mm)

            table_data[0].append(
                [
                    self.p(card["title"], "card_title"),
                    Spacer(1, 2 * mm),
                    self.p(card["value"], "card_value"),
                    Spacer(1, 1.5 * mm),
                    self.p(card["hint"], "card_hint"),
                ]
            )
            col_widths.append(column_width * mm)

        wrapper = Table(table_data, colWidths=col_widths, rowHeights=[31 * mm], hAlign="LEFT")
        style_commands: list[tuple] = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]

        card_column_index = 0
        for card in cards:
            style_commands.extend(
                [
                    ("BACKGROUND", (card_column_index, 0), (card_column_index, 0), _card_fill_color(card.get("variant", "normal"))),
                    ("BOX", (card_column_index, 0), (card_column_index, 0), 0.6, colors.HexColor("#cbd5e1")),
                    ("LEFTPADDING", (card_column_index, 0), (card_column_index, 0), 6),
                    ("RIGHTPADDING", (card_column_index, 0), (card_column_index, 0), 6),
                    ("TOPPADDING", (card_column_index, 0), (card_column_index, 0), 5),
                    ("BOTTOMPADDING", (card_column_index, 0), (card_column_index, 0), 5),
                ]
            )
            card_column_index += 2

        wrapper.setStyle(TableStyle(style_commands))
        return wrapper

    def _build_numbered_list(self, items: list[str], *, width_mm: float = STANDARD_TABLE_WIDTH_MM) -> Table:
        if not items:
            items = ["Bu bölüm için dikkat gerektiren kayıt bulunmuyor."]

        rows = []
        for index, item in enumerate(items, start=1):
            rows.append([self.p(str(index), "table_cell_center"), self.p(item, "normal")])

        number_col_mm = 8.0
        text_col_mm = max(width_mm - number_col_mm, 20.0)
        table = Table(rows, colWidths=[number_col_mm * mm, text_col_mm * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return table

    def table(
        self,
        *,
        headers: list[str],
        rows: list[list[Any]],
        col_widths: list[float],
        numeric_columns: set[int] | None = None,
        center_columns: set[int] | None = None,
        row_statuses: list[str] | None = None,
        target_width_mm: float = STANDARD_TABLE_WIDTH_MM,
    ) -> Table:
        numeric_columns = numeric_columns or set()
        center_columns = center_columns or set()
        row_statuses = row_statuses or []

        normalized_col_widths = _normalize_col_widths(col_widths, target_width_mm)
        table_data: list[list[Any]] = [[self.p(header, "table_header") for header in headers]]

        for row in rows:
            output_row: list[Any] = []
            for column_index, value in enumerate(row):
                if column_index in numeric_columns:
                    style_name = "table_cell_right"
                elif column_index in center_columns:
                    style_name = "table_cell_center"
                else:
                    style_name = "table_cell"
                output_row.append(self.p(value, style_name))
            table_data.append(output_row)

        table = Table(
            table_data,
            colWidths=[width * mm for width in normalized_col_widths],
            repeatRows=1,
            hAlign="LEFT",
        )

        style_commands: list[tuple] = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dbe3ee")),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]

        for row_index, row_status in enumerate(row_statuses, start=1):
            if row_index <= len(rows):
                style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), _row_fill_color(row_status)))

        table.setStyle(TableStyle(style_commands))
        return table

    def section(self, text: Any) -> Paragraph:
        return self.p(text, "section")

    def p(self, text: Any, style_name: str = "normal") -> Paragraph:
        safe_text = escape(str(text if text is not None else "-")).replace("\n", "<br/>")
        style = self.styles.get(style_name, self.styles["normal"])
        return Paragraph(safe_text, style)

    def _draw_header_footer(self, canvas, document) -> None:
        canvas.saveState()

        page_width, page_height = self.pagesize
        left_x = 11 * mm
        right_x = page_width - 11 * mm
        top_y = page_height - 8 * mm

        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.5)
        canvas.line(left_x, top_y - 7 * mm, right_x, top_y - 7 * mm)

        if self.logo_path is not None:
            try:
                canvas.drawImage(
                    str(self.logo_path),
                    left_x,
                    top_y - 5.4 * mm,
                    width=40 * mm,
                    height=11 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                text_start_x = left_x + 45 * mm
            except Exception:
                text_start_x = left_x
        else:
            text_start_x = left_x

        canvas.setFont(self.fonts.bold, 8.2)
        canvas.setFillColor(colors.HexColor("#0f172a"))
        canvas.drawString(text_start_x, top_y, "FTM Finansal Yönetim İmza Raporu")

        canvas.setFont(self.fonts.regular, 6.8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(right_x, top_y, self.data.context.created_at.strftime("%d.%m.%Y %H:%M"))
        canvas.drawRightString(
            right_x,
            top_y - 4 * mm,
            f"Dönem: {_date_range_text(self.data.context.start_date, self.data.context.end_date)}",
        )

        footer_y = 7 * mm
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.4)
        canvas.line(left_x, footer_y + 5 * mm, right_x, footer_y + 5 * mm)

        canvas.setFont(self.fonts.regular, 6.8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(left_x, footer_y, "Önde karar. Arkada kanıt. Sonunda güven.")
        canvas.drawRightString(right_x, footer_y, f"Sayfa {document.page}")

        canvas.restoreState()


def create_management_signature_report_pdf(
    output_path: str | Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    created_by: str | None = None,
    created_by_text: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> str:
    """
    FTM Finansal Yönetim İmza Raporu PDF'i üretir.

    Bu fonksiyon özellikle Raporlar > Yönetim Özeti ekranındaki "Yönetim PDF Al"
    butonuna bağlanmak için tasarlanmıştır.

    Args:
        output_path: PDF'in kaydedileceği tam dosya yolu.
        start_date: Rapor başlangıç tarihi. Boş bırakılırsa bugün kullanılır.
        end_date: Rapor bitiş tarihi. Boş bırakılırsa başlangıçtan 30 gün sonrası kullanılır.
        created_by: Raporu oluşturan kullanıcı metni.
        created_by_text: Eski/alternatif çağrılar için created_by eşleniği.
        snapshot: Şimdilik opsiyoneldir. Ekran snapshot'ı verilirse gelecekte kullanılabilir;
            bu ilk sürüm kendi verisini rapor veri fonksiyonlarından yükler.

    Returns:
        Oluşturulan PDF dosyasının tam yolu.
    """

    _ = snapshot  # Geriye dönük uyumluluk için parametre korunur.

    today = date.today()
    normalized_start_date = start_date or today
    normalized_end_date = end_date or (normalized_start_date + timedelta(days=30))

    if normalized_end_date < normalized_start_date:
        raise ValueError("Bitiş tarihi başlangıç tarihinden küçük olamaz.")

    creator = created_by or created_by_text or "admin / ADMIN"

    context = ManagementSignatureReportContext(
        start_date=normalized_start_date,
        end_date=normalized_end_date,
        created_by=creator,
        created_at=datetime.now(),
    )

    report_data = load_management_signature_report_data(context)

    builder = _SignaturePdfBuilder(output_path=output_path, data=report_data)
    return builder.build()


def load_management_signature_report_data(
    context: ManagementSignatureReportContext,
) -> ManagementSignatureReportData:
    today = date.today()
    range_7_end = min(context.end_date, today + timedelta(days=7))
    range_15_end = min(context.end_date, today + timedelta(days=15))

    today_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=today,
            end_date=today,
            check_type="ALL",
            status_group="PENDING",
            currency_code="ALL",
        )
    )

    range_7_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=today,
            end_date=range_7_end,
            check_type="ALL",
            status_group="PENDING",
            currency_code="ALL",
        )
    )

    range_15_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=today,
            end_date=range_15_end,
            check_type="ALL",
            status_group="PENDING",
            currency_code="ALL",
        )
    )

    range_30_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=context.start_date,
            end_date=context.end_date,
            check_type="ALL",
            status_group="PENDING",
            currency_code="ALL",
        )
    )

    received_detail_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=context.start_date,
            end_date=context.end_date,
            check_type="RECEIVED",
            status_group="ALL",
            currency_code="ALL",
        )
    )

    issued_detail_data = load_check_due_report_data(
        CheckDueReportFilter(
            start_date=context.start_date,
            end_date=context.end_date,
            check_type="ISSUED",
            status_group="ALL",
            currency_code="ALL",
        )
    )

    bank_data = load_bank_movement_report_data(
        BankMovementReportFilter(
            start_date=context.start_date,
            end_date=context.end_date,
            direction="ALL",
            status="ALL",
            currency_code="ALL",
            source_type="ALL",
        )
    )

    current_bank_account_rows = _build_current_bank_account_rows(as_of_date=context.created_at.date())

    pos_data = load_pos_settlement_report_data(
        PosSettlementReportFilter(
            start_date=context.start_date,
            end_date=context.end_date,
            status="ALL",
            currency_code="ALL",
        )
    )

    risk_start_date = date(today.year, 1, 1)
    risk_end_date = max(context.end_date, date(today.year, 12, 31))
    risk_data = load_risk_check_report_data(
        RiskCheckReportFilter(
            start_date=risk_start_date,
            end_date=risk_end_date,
            check_type="ALL",
            risk_type="ALL",
            currency_code="ALL",
        )
    )

    currency_positions = _build_currency_positions(range_30_data)
    daily_pressure_rows = _build_daily_pressure_rows(range_30_data)
    partner_summary_rows = _build_partner_summary_rows(
        pending_rows=range_30_data.rows,
        risk_rows=risk_data.rows,
    )
    critical_due_rows = _build_critical_due_rows(range_30_data.rows, risk_data.rows)
    critical_alerts = _build_critical_alerts(
        range_7_data=range_7_data,
        range_15_data=range_15_data,
        range_30_data=range_30_data,
        risk_data=risk_data,
        pos_data=pos_data,
    )
    recommended_actions = _build_recommended_actions(
        range_7_data=range_7_data,
        range_30_data=range_30_data,
        risk_data=risk_data,
        pos_data=pos_data,
        daily_pressure_rows=daily_pressure_rows,
    )
    general_status = _build_general_status(
        range_7_data=range_7_data,
        range_30_data=range_30_data,
        risk_data=risk_data,
        pos_data=pos_data,
    )
    decision_sentence = _build_decision_sentence(
        general_status=general_status,
        range_7_data=range_7_data,
        range_30_data=range_30_data,
        risk_data=risk_data,
        daily_pressure_rows=daily_pressure_rows,
    )

    return ManagementSignatureReportData(
        context=context,
        today_data=today_data,
        range_7_data=range_7_data,
        range_15_data=range_15_data,
        range_30_data=range_30_data,
        received_detail_data=received_detail_data,
        issued_detail_data=issued_detail_data,
        bank_data=bank_data,
        current_bank_account_rows=current_bank_account_rows,
        pos_data=pos_data,
        risk_data=risk_data,
        currency_positions=currency_positions,
        daily_pressure_rows=daily_pressure_rows,
        partner_summary_rows=partner_summary_rows,
        critical_due_rows=critical_due_rows,
        critical_alerts=critical_alerts,
        recommended_actions=recommended_actions,
        decision_sentence=decision_sentence,
        general_status=general_status,
    )


def _build_current_bank_account_rows(*, as_of_date: date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    try:
        with session_scope() as session:
            account_records = session.execute(
                select(BankAccount, Bank)
                .join(Bank, BankAccount.bank_id == Bank.id)
                .order_by(Bank.name.asc(), BankAccount.account_name.asc(), BankAccount.id.asc())
            ).all()

            account_ids = [account.id for account, _bank in account_records]
            movement_map: dict[int, dict[str, Decimal]] = {
                int(account_id): {"in": ZERO, "out": ZERO} for account_id in account_ids
            }

            if account_ids:
                transaction_records = session.execute(
                    select(BankTransaction).where(
                        BankTransaction.bank_account_id.in_(account_ids),
                        BankTransaction.transaction_date <= as_of_date,
                    )
                ).scalars().all()

                for transaction in transaction_records:
                    if _enum_value(transaction.status) != "REALIZED":
                        continue

                    if _enum_value(transaction.source_type) == "OPENING_BALANCE":
                        continue

                    account_id = int(transaction.bank_account_id)
                    if account_id not in movement_map:
                        movement_map[account_id] = {"in": ZERO, "out": ZERO}

                    amount = _decimal_or_zero(transaction.amount)
                    if _enum_value(transaction.direction) == "IN":
                        movement_map[account_id]["in"] = (movement_map[account_id]["in"] + amount).quantize(MONEY_QUANT)
                    elif _enum_value(transaction.direction) == "OUT":
                        movement_map[account_id]["out"] = (movement_map[account_id]["out"] + amount).quantize(MONEY_QUANT)

            for account, bank in account_records:
                account_id = int(account.id)
                opening_balance = _decimal_or_zero(account.opening_balance)
                realized_in = _decimal_or_zero(movement_map.get(account_id, {}).get("in", ZERO))
                realized_out = _decimal_or_zero(movement_map.get(account_id, {}).get("out", ZERO))
                current_balance = (opening_balance + realized_in - realized_out).quantize(MONEY_QUANT)
                is_active = bool(account.is_active and bank.is_active)

                rows.append(
                    {
                        "bank_name": str(bank.name or "-"),
                        "account_name": str(account.account_name or "-"),
                        "currency_code": _enum_value(account.currency_code) or "TRY",
                        "opening_balance": opening_balance,
                        "realized_in": realized_in,
                        "realized_out": realized_out,
                        "current_balance": current_balance,
                        "note": "Aktif hesap" if is_active else "Pasif hesap",
                        "row_status": "SUCCESS" if current_balance >= ZERO and is_active else ("MUTED" if not is_active else "RISK"),
                    }
                )
    except Exception:
        return []

    rows.sort(
        key=lambda row: (
            0 if row["row_status"] == "RISK" else 1,
            str(row["bank_name"]).lower(),
            str(row["account_name"]).lower(),
            str(row["currency_code"]),
        )
    )
    return rows


def _build_currency_positions(range_data: Any) -> list[dict[str, Any]]:
    currencies = sorted(
        set(range_data.summary.received_totals.keys())
        | set(range_data.summary.issued_totals.keys())
        | set(range_data.summary.net_effect_totals.keys())
    )

    if not currencies:
        currencies = ["TRY"]

    rows: list[dict[str, Any]] = []
    for currency_code in currencies:
        received = _decimal_or_zero(range_data.summary.received_totals.get(currency_code, ZERO))
        issued = _decimal_or_zero(range_data.summary.issued_totals.get(currency_code, ZERO))
        net = _decimal_or_zero(range_data.summary.net_effect_totals.get(currency_code, ZERO))

        if net < ZERO:
            comment = "Ödeme baskısı var. Kaynak planı kontrol edilmeli."
            row_status = "RISK"
        elif net > ZERO:
            comment = "Tahsilat fazlası görünüyor. Tahsilat kalitesi takip edilmeli."
            row_status = "SUCCESS"
        else:
            comment = "Dengeli görünüyor. Günlük takip yeterli."
            row_status = "NORMAL"

        rows.append(
            {
                "currency_code": currency_code,
                "received": received,
                "issued": issued,
                "net": net,
                "comment": comment,
                "row_status": row_status,
            }
        )

    rows.sort(key=lambda row: (0 if row["currency_code"] == "TRY" else 1, row["currency_code"]))
    return rows


def _build_daily_pressure_rows(range_data: Any) -> list[dict[str, Any]]:
    grouped: dict[date, dict[str, Any]] = {}

    for row in range_data.rows:
        day = row.due_date
        if day not in grouped:
            grouped[day] = {
                "date": day,
                "received_totals": {},
                "issued_totals": {},
                "net_totals": {},
                "record_count": 0,
            }

        item = grouped[day]
        item["record_count"] += 1

        if row.check_type == "RECEIVED":
            _add_to_totals(item["received_totals"], row.currency_code, row.amount)
            _add_to_totals(item["net_totals"], row.currency_code, row.amount)
        else:
            _add_to_totals(item["issued_totals"], row.currency_code, row.amount)
            _subtract_from_totals(item["net_totals"], row.currency_code, row.amount)

    output: list[dict[str, Any]] = []
    for item in grouped.values():
        if _has_negative_total(item["net_totals"]):
            item["comment"] = "Ödeme günü. Banka/kasa hazırlığı kontrol edilmeli."
            item["row_status"] = "RISK"
        elif _has_positive_total(item["net_totals"]):
            item["comment"] = "Tahsilat günü. Tahsilat durumu takip edilmeli."
            item["row_status"] = "SUCCESS"
        else:
            item["comment"] = "Dengeli gün."
            item["row_status"] = "NORMAL"
        output.append(item)

    output.sort(key=lambda row: (row["date"], 0 if _has_negative_total(row["net_totals"]) else 1))
    return output


def _build_partner_summary_rows(*, pending_rows: list[Any], risk_rows: list[Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def ensure_party(party_name: str) -> dict[str, Any]:
        name = str(party_name or "-").strip() or "-"
        if name not in grouped:
            grouped[name] = {
                "party_name": name,
                "party_type": "-",
                "received_totals": {},
                "issued_totals": {},
                "net_totals": {},
                "risk_count": 0,
                "status_text": "Normal",
                "row_status": "NORMAL",
            }
        return grouped[name]

    for row in pending_rows:
        item = ensure_party(row.party_name)
        if row.check_type == "RECEIVED":
            item["party_type"] = _merge_party_type(item["party_type"], "Müşteri")
            _add_to_totals(item["received_totals"], row.currency_code, row.amount)
            _add_to_totals(item["net_totals"], row.currency_code, row.amount)
        else:
            item["party_type"] = _merge_party_type(item["party_type"], "Tedarikçi")
            _add_to_totals(item["issued_totals"], row.currency_code, row.amount)
            _subtract_from_totals(item["net_totals"], row.currency_code, row.amount)

    for row in risk_rows:
        item = ensure_party(row.party_name)
        item["risk_count"] += 1
        if row.check_type == "RECEIVED":
            item["party_type"] = _merge_party_type(item["party_type"], "Müşteri")
        else:
            item["party_type"] = _merge_party_type(item["party_type"], "Tedarikçi")

    for item in grouped.values():
        if item["risk_count"] > 0:
            item["status_text"] = "Risk/problem var"
            item["row_status"] = "RISK"
        elif _has_negative_total(item["net_totals"]):
            item["status_text"] = "Ödeme baskısı"
            item["row_status"] = "WARNING"
        elif _has_positive_total(item["net_totals"]):
            item["status_text"] = "Tahsilat bekleniyor"
            item["row_status"] = "SUCCESS"

    rows = list(grouped.values())
    rows.sort(
        key=lambda row: (
            0 if row["risk_count"] else 1,
            _negative_magnitude(row["net_totals"]),
            row["party_name"].lower(),
        )
    )
    return rows


def _build_critical_due_rows(pending_rows: list[Any], risk_rows: list[Any]) -> list[Any]:
    rows = list(pending_rows)
    risk_check_keys = {(row.check_type, row.check_id) for row in risk_rows}

    rows.sort(
        key=lambda row: (
            0 if (row.check_type, row.check_id) in risk_check_keys else 1,
            row.due_date,
            0 if row.check_type == "ISSUED" else 1,
            row.party_name.lower(),
        )
    )
    return rows


def _build_critical_alerts(
    *,
    range_7_data: Any,
    range_15_data: Any,
    range_30_data: Any,
    risk_data: Any,
    pos_data: Any,
) -> list[str]:
    alerts: list[str] = []

    if _has_negative_total(range_7_data.summary.net_effect_totals):
        alerts.append(f"7 günlük çek netinde açık var: {_format_totals(range_7_data.summary.net_effect_totals)}")

    if _has_negative_total(range_15_data.summary.net_effect_totals):
        alerts.append(f"15 günlük çek netinde açık var: {_format_totals(range_15_data.summary.net_effect_totals)}")

    if _has_negative_total(range_30_data.summary.net_effect_totals):
        alerts.append(f"30 günlük çek netinde açık var: {_format_totals(range_30_data.summary.net_effect_totals)}")

    if risk_data.summary.problem_count > 0:
        alerts.append(f"Problemli çek kaydı var: {risk_data.summary.problem_count} kayıt")

    if risk_data.summary.overdue_count > 0:
        alerts.append(f"Vadesi geçmiş bekleyen çek var: {risk_data.summary.overdue_count} kayıt")

    if pos_data.summary.mismatch_count > 0:
        alerts.append(f"POS mutabakatında fark görünen kayıt var: {pos_data.summary.mismatch_count} kayıt")

    if not alerts:
        alerts.append("Kritik uyarı görünmüyor. Yine de vade ve banka hareketleri günlük kontrol edilmeli.")

    return alerts


def _build_recommended_actions(
    *,
    range_7_data: Any,
    range_30_data: Any,
    risk_data: Any,
    pos_data: Any,
    daily_pressure_rows: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []

    if risk_data.summary.problem_count > 0:
        actions.append(
            f"Problemli çek bulunan {risk_data.summary.problem_count} kayıt için muhatap kontrolü yapılmalı; yeni işlem öncesi risk notu incelenmeli."
        )

    if risk_data.summary.overdue_count > 0:
        actions.append(
            f"Vadesi geçmiş bekleyen {risk_data.summary.overdue_count} çek için tahsilat/ödeme takip aksiyonu açılmalı."
        )

    if _has_negative_total(range_7_data.summary.net_effect_totals):
        actions.append(
            f"Önümüzdeki 7 gün için çek neti açıkta: {_format_totals(range_7_data.summary.net_effect_totals)}. Banka/kasa kaynak planı kontrol edilmeli."
        )

    if _has_negative_total(range_30_data.summary.net_effect_totals):
        actions.append(
            f"30 günlük çek netinde açık var: {_format_totals(range_30_data.summary.net_effect_totals)}. Ödeme takvimi ve tahsilat öncelikleri birlikte değerlendirilmelidir."
        )

    pressure_days = [row for row in daily_pressure_rows if _has_negative_total(row["net_totals"])]
    if pressure_days:
        first_pressure_day = pressure_days[0]
        actions.append(
            f"En yakın nakit baskısı {_format_date(first_pressure_day['date'])} tarihinde: {_format_totals(first_pressure_day['net_totals'])}. İlgili banka hesabı önceden kontrol edilmeli."
        )

    if pos_data.summary.mismatch_count > 0:
        actions.append(f"POS mutabakatında fark görünen {pos_data.summary.mismatch_count} kayıt incelenmeli.")

    if not actions:
        actions.append("Günlük vade, banka ve POS kontrolleri rutin takip planıyla sürdürülebilir.")

    return actions


def _build_general_status(*, range_7_data: Any, range_30_data: Any, risk_data: Any, pos_data: Any) -> str:
    if risk_data.summary.problem_count > 0 or risk_data.summary.overdue_count > 0:
        return REPORT_STATUS_RISK

    if _has_negative_total(range_7_data.summary.net_effect_totals):
        return REPORT_STATUS_RISK

    if _has_negative_total(range_30_data.summary.net_effect_totals):
        return REPORT_STATUS_ATTENTION

    if pos_data.summary.mismatch_count > 0:
        return REPORT_STATUS_ATTENTION

    return REPORT_STATUS_NORMAL


def _build_decision_sentence(
    *,
    general_status: str,
    range_7_data: Any,
    range_30_data: Any,
    risk_data: Any,
    daily_pressure_rows: list[dict[str, Any]],
) -> str:
    if risk_data.summary.problem_count > 0:
        return (
            f"Öncelik problemli çeklerde: {risk_data.summary.problem_count} kayıt var. "
            "Yeni işlemden önce bu muhataplar kontrol edilmeli."
        )

    if risk_data.summary.overdue_count > 0:
        return (
            f"Vadesi geçmiş bekleyen {risk_data.summary.overdue_count} çek var. "
            "Tahsilat/ödeme takibi aynı gün içinde netleştirilmeli."
        )

    if _has_negative_total(range_7_data.summary.net_effect_totals):
        return (
            f"7 günlük ödeme baskısı oluşuyor: {_format_totals(range_7_data.summary.net_effect_totals)}. "
            "Banka/kasa kaynak planı bugün kontrol edilmeli."
        )

    if _has_negative_total(range_30_data.summary.net_effect_totals):
        return (
            f"30 günlük vade döneminde açık görünüyor: {_format_totals(range_30_data.summary.net_effect_totals)}. "
            "Tahsilat öncelikleri ve ödeme günleri birlikte planlanmalı."
        )

    pressure_days = [row for row in daily_pressure_rows if _has_negative_total(row["net_totals"])]
    if pressure_days:
        row = pressure_days[0]
        return f"En yakın nakit baskısı {_format_date(row['date'])} tarihinde görünüyor: {_format_totals(row['net_totals'])}."

    if general_status == REPORT_STATUS_NORMAL:
        return "Rapor döneminde kritik açık görünmüyor. Vade, banka ve POS kontrolleri rutin düzende sürdürülebilir."

    return "Rapor döneminde takip edilmesi gereken finansal başlıklar var. Detay ekleri kontrol edilmeli."


def _safe_logo_path() -> Path | None:
    if get_report_logo_path is None:
        return None

    try:
        logo_path = get_report_logo_path()
    except Exception:
        return None

    if logo_path is None:
        return None

    try:
        path = Path(logo_path)
        if path.exists() and path.is_file():
            return path
    except Exception:
        return None

    return None


def _format_decimal(value: Any) -> str:
    amount = _decimal_or_zero(value)
    text = f"{amount:,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_signed_decimal(value: Any) -> str:
    amount = _decimal_or_zero(value)
    sign = "+" if amount > ZERO else ""
    return f"{sign}{_format_decimal(amount)}"


def _format_totals(totals: dict[str, Decimal] | None) -> str:
    if not totals:
        return "-"

    parts: list[str] = []
    for currency_code in sorted(totals.keys(), key=lambda code: (0 if str(code).upper() == "TRY" else 1, str(code).upper())):
        amount = _decimal_or_zero(totals.get(currency_code, ZERO))
        if amount == ZERO:
            continue
        parts.append(f"{_format_decimal(amount)} {str(currency_code).upper()}")

    return " / ".join(parts) if parts else "-"


def _format_date(value: date | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d.%m.%Y")


def _date_range_text(start_date: date, end_date: date) -> str:
    return f"{_format_date(start_date)} - {_format_date(end_date)}"


def _decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return ZERO
    try:
        return Decimal(str(value)).quantize(MONEY_QUANT)
    except Exception:
        return ZERO


def _add_to_totals(totals: dict[str, Decimal], currency_code: str, amount: Any) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"
    totals[normalized_currency_code] = (
        _decimal_or_zero(totals.get(normalized_currency_code, ZERO)) + _decimal_or_zero(amount)
    ).quantize(MONEY_QUANT)


def _subtract_from_totals(totals: dict[str, Decimal], currency_code: str, amount: Any) -> None:
    normalized_currency_code = str(currency_code or "TRY").strip().upper() or "TRY"
    totals[normalized_currency_code] = (
        _decimal_or_zero(totals.get(normalized_currency_code, ZERO)) - _decimal_or_zero(amount)
    ).quantize(MONEY_QUANT)


def _has_negative_total(totals: dict[str, Decimal] | None) -> bool:
    if not totals:
        return False
    return any(_decimal_or_zero(amount) < ZERO for amount in totals.values())


def _has_positive_total(totals: dict[str, Decimal] | None) -> bool:
    if not totals:
        return False
    return any(_decimal_or_zero(amount) > ZERO for amount in totals.values())


def _negative_magnitude(totals: dict[str, Decimal] | None) -> Decimal:
    if not totals:
        return ZERO
    total = ZERO
    for amount in totals.values():
        decimal_amount = _decimal_or_zero(amount)
        if decimal_amount < ZERO:
            total += abs(decimal_amount)
    return total


def _clean_text(value: Any) -> str:
    text = str(value or "-").strip()
    return text if text else "-"


def _merge_party_type(current: str, new_value: str) -> str:
    current_normalized = str(current or "-").strip()
    new_normalized = str(new_value or "-").strip()

    if current_normalized in {"", "-"}:
        return new_normalized

    if current_normalized == new_normalized:
        return current_normalized

    return "Her İkisi"


def _variant_for_net(totals: dict[str, Decimal] | None) -> str:
    if _has_negative_total(totals):
        return "critical"
    if _has_positive_total(totals):
        return "positive"
    return "normal"


def _normalize_col_widths(col_widths: list[float], target_width_mm: float) -> list[float]:
    if not col_widths:
        return []

    total_width = sum(float(width) for width in col_widths)
    if total_width <= 0:
        equal_width = target_width_mm / len(col_widths)
        return [equal_width for _ in col_widths]

    scale = target_width_mm / total_width
    normalized = [round(float(width) * scale, 4) for width in col_widths]
    rounding_gap = target_width_mm - sum(normalized)
    normalized[-1] = round(normalized[-1] + rounding_gap, 4)
    return normalized


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value).strip().upper()
    return str(value or "").strip().upper()


def _card_fill_color(variant: str) -> colors.Color:
    normalized = str(variant or "normal").strip().lower()
    if normalized == "critical":
        return colors.HexColor("#fee2e2")
    if normalized == "warning":
        return colors.HexColor("#fef3c7")
    if normalized == "positive":
        return colors.HexColor("#dcfce7")
    return colors.HexColor("#ffffff")


def _row_fill_color(row_status: str) -> colors.Color:
    normalized = str(row_status or "NORMAL").strip().upper()
    if normalized in {"RISK", "PROBLEM", "OVERDUE"}:
        return colors.HexColor("#fff1f2")
    if normalized in {"WARNING", "PLANNED"}:
        return colors.HexColor("#fffbeb")
    if normalized in {"SUCCESS", "RECEIVED", "IN"}:
        return colors.HexColor("#f0fdf4")
    if normalized in {"MUTED", "CLOSED", "CANCELLED"}:
        return colors.HexColor("#f8fafc")
    if normalized in {"ISSUED", "OUT"}:
        return colors.HexColor("#fef2f2")
    return colors.white


def _status_text(status: str) -> str:
    normalized = str(status or REPORT_STATUS_NORMAL).strip().upper()
    if normalized == REPORT_STATUS_RISK:
        return "İzlenmeli"
    if normalized == REPORT_STATUS_ATTENTION:
        return "Dikkat Gerektiriyor"
    return "Normal Seyir"


def _status_description(status: str) -> str:
    normalized = str(status or REPORT_STATUS_NORMAL).strip().upper()
    if normalized == REPORT_STATUS_RISK:
        return "Takip edilmesi gereken riskli durumlar var."
    if normalized == REPORT_STATUS_ATTENTION:
        return "Yakın takip gerektiren finansal başlıklar var."
    return "Rapor döneminde kritik açık görünmüyor."


def _status_fill_color(status: str) -> colors.Color:
    normalized = str(status or REPORT_STATUS_NORMAL).strip().upper()
    if normalized == REPORT_STATUS_RISK:
        return colors.HexColor("#fef3c7")
    if normalized == REPORT_STATUS_ATTENTION:
        return colors.HexColor("#e0f2fe")
    return colors.HexColor("#dcfce7")


def _row_status_from_due(row: Any) -> str:
    if str(row.status_group or "").upper() == "PROBLEM":
        return "PROBLEM"
    if row.days_difference < 0:
        return "OVERDUE"
    if row.check_type == "ISSUED":
        return "ISSUED"
    if row.check_type == "RECEIVED":
        return "RECEIVED"
    return "NORMAL"

