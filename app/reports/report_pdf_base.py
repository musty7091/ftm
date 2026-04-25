from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.reports.report_theme import (
    FTM_REPORT_THEME,
    FtmReportFonts,
    register_ftm_report_fonts,
)


@dataclass(frozen=True)
class FtmReportMeta:
    title: str
    report_period: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class FtmSummaryCard:
    title: str
    value: str
    hint: str = ""
    card_type: str = "normal"


def _safe_text(value: Any) -> str:
    return str(value if value is not None else "")


def _safe_paragraph_text(value: Any) -> str:
    return escape(_safe_text(value)).replace("\n", "<br/>")


def _card_background_color(card_type: str):
    normalized_type = str(card_type or "normal").strip().lower()

    if normalized_type == "success":
        return FTM_REPORT_THEME.success_fill_color

    if normalized_type == "risk":
        return FTM_REPORT_THEME.risk_fill_color

    if normalized_type == "warning":
        return FTM_REPORT_THEME.warning_fill_color

    if normalized_type == "muted":
        return FTM_REPORT_THEME.muted_fill_color

    return FTM_REPORT_THEME.normal_fill_color


def _row_background_color(row_status: str):
    normalized_status = str(row_status or "").strip().upper()

    if normalized_status in {"RECEIVED", "SUCCESS", "ALINAN"}:
        return colors.HexColor("#f0fdf4")

    if normalized_status in {"ISSUED", "RISK", "YAZILAN"}:
        return colors.HexColor("#fef2f2")

    if normalized_status in {"PROBLEM", "WARNING", "OVERDUE"}:
        return colors.HexColor("#fffbeb")

    if normalized_status in {"CLOSED", "MUTED", "SONUCLANAN"}:
        return colors.HexColor("#f8fafc")

    return colors.white


class FtmPdfReportBuilder:
    def __init__(
        self,
        *,
        output_path: str | Path,
        meta: FtmReportMeta,
        orientation: str = "landscape",
    ) -> None:
        self.output_path = Path(output_path)
        self.meta = meta
        self.orientation = str(orientation or "landscape").strip().lower()
        self.fonts: FtmReportFonts = register_ftm_report_fonts()
        self.styles = self._build_styles()

        if self.orientation == "portrait":
            self.pagesize = portrait(A4)
        else:
            self.pagesize = landscape(A4)

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        return {
            "title": ParagraphStyle(
                name="FTMTitle",
                fontName=self.fonts.bold,
                fontSize=15,
                leading=18,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_LEFT,
                spaceAfter=4,
            ),
            "subtitle": ParagraphStyle(
                name="FTMSubtitle",
                fontName=self.fonts.regular,
                fontSize=8.5,
                leading=11,
                textColor=FTM_REPORT_THEME.muted_text_color,
                alignment=TA_LEFT,
            ),
            "section": ParagraphStyle(
                name="FTMSection",
                fontName=self.fonts.bold,
                fontSize=11,
                leading=14,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_LEFT,
                spaceBefore=6,
                spaceAfter=6,
            ),
            "normal": ParagraphStyle(
                name="FTMNormal",
                fontName=self.fonts.regular,
                fontSize=8,
                leading=10,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_LEFT,
            ),
            "small": ParagraphStyle(
                name="FTMSmall",
                fontName=self.fonts.regular,
                fontSize=7,
                leading=8.5,
                textColor=FTM_REPORT_THEME.muted_text_color,
                alignment=TA_LEFT,
            ),
            "table_header": ParagraphStyle(
                name="FTMTableHeader",
                fontName=self.fonts.bold,
                fontSize=7.2,
                leading=8.5,
                textColor=FTM_REPORT_THEME.table_header_text_color,
                alignment=TA_CENTER,
            ),
            "table_cell": ParagraphStyle(
                name="FTMTableCell",
                fontName=self.fonts.regular,
                fontSize=7,
                leading=8.5,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_LEFT,
            ),
            "table_cell_center": ParagraphStyle(
                name="FTMTableCellCenter",
                fontName=self.fonts.regular,
                fontSize=7,
                leading=8.5,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_CENTER,
            ),
            "table_cell_right": ParagraphStyle(
                name="FTMTableCellRight",
                fontName=self.fonts.regular,
                fontSize=7,
                leading=8.5,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_RIGHT,
            ),
            "card_title": ParagraphStyle(
                name="FTMCardTitle",
                fontName=self.fonts.bold,
                fontSize=7.5,
                leading=9,
                textColor=FTM_REPORT_THEME.secondary_color,
                alignment=TA_LEFT,
            ),
            "card_value": ParagraphStyle(
                name="FTMCardValue",
                fontName=self.fonts.bold,
                fontSize=10,
                leading=12,
                textColor=FTM_REPORT_THEME.primary_color,
                alignment=TA_LEFT,
            ),
            "card_hint": ParagraphStyle(
                name="FTMCardHint",
                fontName=self.fonts.regular,
                fontSize=6.8,
                leading=8,
                textColor=FTM_REPORT_THEME.muted_text_color,
                alignment=TA_LEFT,
            ),
        }

    def paragraph(self, text: Any, style_name: str = "normal") -> Paragraph:
        style = self.styles.get(style_name, self.styles["normal"])

        return Paragraph(_safe_paragraph_text(text), style)

    def section_title(self, text: Any) -> Paragraph:
        return self.paragraph(text, "section")

    def spacer(self, height_mm: float = 4) -> Spacer:
        return Spacer(1, height_mm * mm)

    def page_break(self) -> PageBreak:
        return PageBreak()

    def build_summary_cards(
        self,
        cards: list[FtmSummaryCard],
        *,
        columns: int | None = None,
    ) -> Table:
        if columns is None:
            columns = 4 if self.orientation == "landscape" else 3

        if columns <= 0:
            columns = 4

        content_width = self._content_width()
        column_width = content_width / columns

        rows: list[list[Any]] = []
        current_row: list[Any] = []

        for card in cards:
            card_table = Table(
                [
                    [self.paragraph(card.title, "card_title")],
                    [self.paragraph(card.value, "card_value")],
                    [self.paragraph(card.hint, "card_hint")],
                ],
                colWidths=[column_width - 4 * mm],
            )

            card_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _card_background_color(card.card_type)),
                        ("BOX", (0, 0), (-1, -1), 0.6, FTM_REPORT_THEME.border_color),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )

            current_row.append(card_table)

            if len(current_row) == columns:
                rows.append(current_row)
                current_row = []

        if current_row:
            while len(current_row) < columns:
                current_row.append("")
            rows.append(current_row)

        wrapper = Table(
            rows,
            colWidths=[column_width for _ in range(columns)],
            hAlign="LEFT",
        )

        wrapper.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        return wrapper

    def build_data_table(
        self,
        *,
        headers: list[str],
        rows: list[list[Any]],
        col_widths: list[float] | None = None,
        numeric_columns: set[int] | None = None,
        center_columns: set[int] | None = None,
        row_statuses: list[str] | None = None,
    ) -> Table:
        numeric_columns = numeric_columns or set()
        center_columns = center_columns or set()

        table_data: list[list[Any]] = []

        header_row = [
            self.paragraph(header, "table_header")
            for header in headers
        ]
        table_data.append(header_row)

        for row in rows:
            output_row: list[Any] = []

            for column_index, value in enumerate(row):
                if column_index in numeric_columns:
                    style_name = "table_cell_right"
                elif column_index in center_columns:
                    style_name = "table_cell_center"
                else:
                    style_name = "table_cell"

                output_row.append(self.paragraph(value, style_name))

            table_data.append(output_row)

        if col_widths is None:
            content_width = self._content_width()
            col_widths = [content_width / max(1, len(headers)) for _ in headers]
        else:
            col_widths = [width * mm for width in col_widths]

        table = Table(
            table_data,
            colWidths=col_widths,
            repeatRows=1,
            hAlign="LEFT",
        )

        table_style_commands: list[tuple] = [
            ("BACKGROUND", (0, 0), (-1, 0), FTM_REPORT_THEME.table_header_fill_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), FTM_REPORT_THEME.table_header_text_color),
            ("GRID", (0, 0), (-1, -1), 0.35, FTM_REPORT_THEME.table_grid_color),
            ("BOX", (0, 0), (-1, -1), 0.6, FTM_REPORT_THEME.border_color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

        if row_statuses:
            for row_index, row_status in enumerate(row_statuses, start=1):
                table_style_commands.append(
                    ("BACKGROUND", (0, row_index), (-1, row_index), _row_background_color(row_status))
                )

        table.setStyle(TableStyle(table_style_commands))

        return table

    def build_total_table(
        self,
        *,
        title: str,
        totals: list[tuple[str, str]],
    ) -> Table:
        rows = [[self.paragraph(title, "table_header"), ""]]

        for label, value in totals:
            rows.append(
                [
                    self.paragraph(label, "table_cell"),
                    self.paragraph(value, "table_cell_right"),
                ]
            )

        table = Table(
            rows,
            colWidths=[45 * mm, 55 * mm],
            hAlign="RIGHT",
        )

        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (1, 0)),
                    ("BACKGROUND", (0, 0), (1, 0), FTM_REPORT_THEME.table_header_fill_color),
                    ("GRID", (0, 0), (-1, -1), 0.35, FTM_REPORT_THEME.table_grid_color),
                    ("BOX", (0, 0), (-1, -1), 0.6, FTM_REPORT_THEME.border_color),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        return table

    def build(self, elements: list[Any]) -> str:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        document = SimpleDocTemplate(
            str(self.output_path),
            pagesize=self.pagesize,
            rightMargin=FTM_REPORT_THEME.page_margin_right,
            leftMargin=FTM_REPORT_THEME.page_margin_left,
            topMargin=FTM_REPORT_THEME.page_margin_top,
            bottomMargin=FTM_REPORT_THEME.page_margin_bottom,
            title=self.meta.title,
            author=self.meta.created_by,
            subject=self.meta.report_period,
        )

        document.build(
            elements,
            onFirstPage=self._draw_header_footer,
            onLaterPages=self._draw_header_footer,
        )

        return str(self.output_path)

    def _content_width(self) -> float:
        page_width, _page_height = self.pagesize

        return (
            page_width
            - FTM_REPORT_THEME.page_margin_left
            - FTM_REPORT_THEME.page_margin_right
        )

    def _draw_header_footer(self, canvas, document) -> None:
        canvas.saveState()

        page_width, page_height = self.pagesize

        left_x = FTM_REPORT_THEME.page_margin_left
        right_x = page_width - FTM_REPORT_THEME.page_margin_right
        top_y = page_height - 10 * mm

        canvas.setStrokeColor(FTM_REPORT_THEME.primary_color)
        canvas.setLineWidth(0.8)
        canvas.line(left_x, top_y - 7 * mm, right_x, top_y - 7 * mm)

        canvas.setFont(self.fonts.bold, 10)
        canvas.setFillColor(FTM_REPORT_THEME.primary_color)
        canvas.drawString(left_x, top_y, FTM_REPORT_THEME.app_name)

        canvas.setFont(self.fonts.bold, 9)
        canvas.drawCentredString(page_width / 2, top_y, self.meta.title)

        canvas.setFont(self.fonts.regular, 7)
        canvas.setFillColor(FTM_REPORT_THEME.muted_text_color)
        canvas.drawRightString(
            right_x,
            top_y,
            self.meta.created_at.strftime("%d.%m.%Y %H:%M"),
        )

        canvas.setFont(self.fonts.regular, 7)
        canvas.drawString(left_x, top_y - 4 * mm, f"Rapor Dönemi: {self.meta.report_period}")
        canvas.drawRightString(right_x, top_y - 4 * mm, f"Oluşturan: {self.meta.created_by}")

        footer_y = 8 * mm

        canvas.setStrokeColor(FTM_REPORT_THEME.border_color)
        canvas.setLineWidth(0.5)
        canvas.line(left_x, footer_y + 5 * mm, right_x, footer_y + 5 * mm)

        canvas.setFont(self.fonts.regular, 7)
        canvas.setFillColor(FTM_REPORT_THEME.muted_text_color)
        canvas.drawString(left_x, footer_y, "FTM Finans Kontrol Paneli")
        canvas.drawRightString(right_x, footer_y, f"Sayfa {document.page}")

        canvas.restoreState()


def create_demo_report_pdf(output_path: str | Path) -> str:
    builder = FtmPdfReportBuilder(
        output_path=output_path,
        orientation="landscape",
        meta=FtmReportMeta(
            title="Vade Bazlı Çek Raporu - Taslak Önizleme",
            report_period="01.05.2026 - 31.05.2026",
            created_by="Mustafa / ADMIN",
            created_at=datetime.now(),
        ),
    )

    elements: list[Any] = []

    elements.append(builder.section_title("Yönetici Özeti"))
    elements.append(
        builder.build_summary_cards(
            [
                FtmSummaryCard(
                    title="Toplam Alınan Çek",
                    value="1.433.908,10 TL",
                    hint="Bekleyen ve sonuçlanan alınan çek toplamı",
                    card_type="success",
                ),
                FtmSummaryCard(
                    title="Toplam Yazılan Çek",
                    value="184.522,00 TL",
                    hint="Vadesi gelen ve gelecek yazılan çekler",
                    card_type="risk",
                ),
                FtmSummaryCard(
                    title="Bekleyen Çek",
                    value="8 kayıt",
                    hint="Henüz sonuçlanmamış çekler",
                    card_type="warning",
                ),
                FtmSummaryCard(
                    title="Net Nakit Etkisi",
                    value="1.249.386,10 TL",
                    hint="Alınan - yazılan çek farkı",
                    card_type="normal",
                ),
            ]
        )
    )

    elements.append(builder.spacer(5))
    elements.append(builder.section_title("Detay Liste"))

    headers = [
        "Tür",
        "Durum",
        "Taraf",
        "Çek No",
        "Vade",
        "Kalan",
        "Tutar",
        "Para",
        "Referans",
        "Açıklama",
    ]

    rows = [
        [
            "Alınan",
            "Bekleyen",
            "ABC Market Ltd.",
            "A-1025",
            "05.05.2026",
            "10 gün",
            "250.000,00",
            "TRY",
            "REF-001",
            "Portföyde bekleyen çek",
        ],
        [
            "Yazılan",
            "Bekleyen",
            "XYZ Tedarik Ltd.",
            "Y-3381",
            "08.05.2026",
            "13 gün",
            "84.522,00",
            "TRY",
            "REF-002",
            "Ödeme planında",
        ],
        [
            "Alınan",
            "Problemli",
            "Örnek Müşteri",
            "A-9991",
            "18.04.2026",
            "7 gün geçti",
            "100.000,00",
            "TRY",
            "REF-003",
            "Kontrol gerektirir",
        ],
    ]

    elements.append(
        builder.build_data_table(
            headers=headers,
            rows=rows,
            col_widths=[17, 23, 42, 22, 22, 20, 28, 16, 24, 48],
            numeric_columns={6},
            center_columns={0, 1, 4, 5, 7},
            row_statuses=["RECEIVED", "ISSUED", "PROBLEM"],
        )
    )

    elements.append(builder.spacer(5))
    elements.append(
        builder.build_total_table(
            title="Genel Toplam",
            totals=[
                ("Toplam Alınan", "350.000,00 TL"),
                ("Toplam Yazılan", "84.522,00 TL"),
                ("Net Fark", "265.478,00 TL"),
            ],
        )
    )

    return builder.build(elements)