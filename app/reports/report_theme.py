from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import Color
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


@dataclass(frozen=True)
class FtmReportFonts:
    regular: str
    bold: str


@dataclass(frozen=True)
class FtmReportTheme:
    app_name: str
    primary_color: Color
    secondary_color: Color
    muted_text_color: Color
    border_color: Color
    header_fill_color: Color
    table_header_fill_color: Color
    table_header_text_color: Color
    table_grid_color: Color
    success_fill_color: Color
    success_text_color: Color
    risk_fill_color: Color
    risk_text_color: Color
    warning_fill_color: Color
    warning_text_color: Color
    muted_fill_color: Color
    normal_fill_color: Color
    page_margin_left: float
    page_margin_right: float
    page_margin_top: float
    page_margin_bottom: float


FTM_REPORT_THEME = FtmReportTheme(
    app_name="FTM Finans Takip Merkezi",
    primary_color=colors.HexColor("#0f172a"),
    secondary_color=colors.HexColor("#1e293b"),
    muted_text_color=colors.HexColor("#64748b"),
    border_color=colors.HexColor("#cbd5e1"),
    header_fill_color=colors.HexColor("#eff6ff"),
    table_header_fill_color=colors.HexColor("#1e293b"),
    table_header_text_color=colors.white,
    table_grid_color=colors.HexColor("#dbe3ee"),
    success_fill_color=colors.HexColor("#dcfce7"),
    success_text_color=colors.HexColor("#166534"),
    risk_fill_color=colors.HexColor("#fee2e2"),
    risk_text_color=colors.HexColor("#991b1b"),
    warning_fill_color=colors.HexColor("#fef3c7"),
    warning_text_color=colors.HexColor("#92400e"),
    muted_fill_color=colors.HexColor("#f1f5f9"),
    normal_fill_color=colors.white,
    page_margin_left=12 * mm,
    page_margin_right=12 * mm,
    page_margin_top=24 * mm,
    page_margin_bottom=15 * mm,
)


def _first_existing_path(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path

    return None


def register_ftm_report_fonts() -> FtmReportFonts:
    """
    FTM PDF raporlarında Türkçe karakter desteği için TTF font kaydı yapar.

    Windows için önce Arial/Tahoma aranır.
    Linux/macOS ortamları için DejaVu ve Liberation fontları denenir.
    Hiçbiri bulunamazsa Helvetica kullanılır.
    """

    regular_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]

    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/tahomabd.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]

    regular_path = _first_existing_path(regular_candidates)
    bold_path = _first_existing_path(bold_candidates)

    if regular_path is not None:
        try:
            pdfmetrics.registerFont(TTFont("FTM-Regular", str(regular_path)))
            regular_font_name = "FTM-Regular"
        except Exception:
            regular_font_name = "Helvetica"
    else:
        regular_font_name = "Helvetica"

    if bold_path is not None:
        try:
            pdfmetrics.registerFont(TTFont("FTM-Bold", str(bold_path)))
            bold_font_name = "FTM-Bold"
        except Exception:
            bold_font_name = "Helvetica-Bold"
    else:
        bold_font_name = "Helvetica-Bold"

    return FtmReportFonts(
        regular=regular_font_name,
        bold=bold_font_name,
    )