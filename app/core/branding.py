from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


REPORT_LOGO_FILE_NAME = "ftm_report_logo.png"
APP_ICON_PNG_FILE_NAME = "ftm_app_icon.png"
APP_ICON_ICO_FILE_NAME = "ftm_app_icon.ico"


@dataclass(frozen=True)
class BrandingAssets:
    """
    FTM marka görsellerinin merkezi yol bilgisini taşır.

    Bu sınıf ve yardımcı fonksiyonlar özellikle şu amaçlarla kullanılır:
    - PDF raporlarında geniş FTM logosunu kullanmak
    - PySide6 ana pencere ikonunu tek merkezden almak
    - PyInstaller ile paketlenmiş uygulamada asset yollarını bozmamak

    Not:
        Bu modül dosyaları oluşturmaz; sadece mevcut dosyaları güvenli şekilde bulur.
        Dosya yoksa None döndürerek uygulamanın çökmesini engeller.
    """

    assets_folder: Path
    report_logo: Path | None
    app_icon_png: Path | None
    app_icon_ico: Path | None


def is_packaged_app() -> bool:
    """
    Uygulama PyInstaller ile paketlenmiş .exe olarak çalışıyorsa True döndürür.
    """

    return bool(getattr(sys, "frozen", False))


def get_project_root_folder() -> Path:
    """
    Geliştirme ortamında proje kök klasörünü döndürür.

    Beklenen yapı:
        C:\\ftm
        ├─ app
        │  ├─ core
        │  │  └─ branding.py
        │  └─ assets
        │     └─ branding
        │        ├─ ftm_report_logo.png
        │        ├─ ftm_app_icon.png
        │        └─ ftm_app_icon.ico
    """

    return Path(__file__).resolve().parents[2]


def get_packaged_root_folder() -> Path:
    """
    Paketlenmiş uygulama için asset kökünü güvenli şekilde bulur.

    PyInstaller onefile/onedir kullanımında sys._MEIPASS varsa önce o klasör denenir.
    Yoksa çalıştırılabilir dosyanın bulunduğu klasör kullanılır.
    """

    pyinstaller_temp_folder = getattr(sys, "_MEIPASS", None)

    if pyinstaller_temp_folder:
        return Path(str(pyinstaller_temp_folder)).resolve()

    executable_path = getattr(sys, "executable", "")

    if executable_path:
        return Path(executable_path).resolve().parent

    return get_project_root_folder()


def get_branding_assets_folder() -> Path:
    """
    Marka asset klasörünü döndürür.

    Geliştirme ortamında:
        C:\\ftm\\app\\assets\\branding

    Paketlenmiş uygulamada önce:
        <_MEIPASS>\\app\\assets\\branding

    Alternatif paket düzenlerinde:
        <exe klasörü>\\app\\assets\\branding
    """

    root_folder = get_packaged_root_folder() if is_packaged_app() else get_project_root_folder()
    return root_folder / "app" / "assets" / "branding"


def _existing_file_or_none(path: Path) -> Path | None:
    """
    Yol gerçekten var olan bir dosyaysa Path döndürür; aksi halde None döndürür.
    """

    try:
        if path.exists() and path.is_file():
            return path
    except OSError:
        return None

    return None


def get_branding_assets() -> BrandingAssets:
    """
    FTM marka görsellerinin güvenli yol bilgisini döndürür.

    Dönen değerlerde herhangi bir dosya bulunamazsa ilgili alan None olur.
    Bu sayede rapor veya arayüz logo bulunamadığı için çökmez.
    """

    assets_folder = get_branding_assets_folder()

    return BrandingAssets(
        assets_folder=assets_folder,
        report_logo=_existing_file_or_none(assets_folder / REPORT_LOGO_FILE_NAME),
        app_icon_png=_existing_file_or_none(assets_folder / APP_ICON_PNG_FILE_NAME),
        app_icon_ico=_existing_file_or_none(assets_folder / APP_ICON_ICO_FILE_NAME),
    )


def get_report_logo_path() -> Path | None:
    """
    PDF raporları için kullanılacak geniş FTM logo yolunu döndürür.
    """

    return get_branding_assets().report_logo


def get_app_icon_png_path() -> Path | None:
    """
    Uygulama içinde gösterilecek PNG ikon yolunu döndürür.
    """

    return get_branding_assets().app_icon_png


def get_app_icon_ico_path() -> Path | None:
    """
    Windows pencere/installer ikonu için kullanılacak ICO dosya yolunu döndürür.
    """

    return get_branding_assets().app_icon_ico


def describe_branding_assets() -> list[dict[str, str]]:
    """
    Sistem ekranlarında veya manuel testlerde gösterilebilecek sade asset durum listesini üretir.
    """

    assets = get_branding_assets()

    def status(path: Path | None) -> str:
        return str(path) if path is not None else "Bulunamadı"

    return [
        {
            "label": "Marka Asset Klasörü",
            "path": str(assets.assets_folder),
        },
        {
            "label": "PDF Rapor Logosu",
            "path": status(assets.report_logo),
        },
        {
            "label": "Uygulama PNG İkonu",
            "path": status(assets.app_icon_png),
        },
        {
            "label": "Windows ICO İkonu",
            "path": status(assets.app_icon_ico),
        },
    ]
