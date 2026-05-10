from typing import Any

from PySide6.QtWidgets import QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox


class NoWheelComboBox(QComboBox):
    """
    QComboBox üzerinde mouse tekerleği ile yanlışlıkla seçim değişmesini engeller.

    Kullanıcı dropdown'u elle açarak seçim yapabilir.
    Klavye ile kullanım normal devam eder.
    Mouse tekerleği sayfa/form scroll davranışına bırakılır.
    """

    def wheelEvent(self, event: Any) -> None:
        event.ignore()


class NoWheelDateEdit(QDateEdit):
    """
    QDateEdit üzerinde mouse tekerleği ile yanlışlıkla tarih değişmesini engeller.

    Kullanıcı takvimi açarak veya klavye ile tarih girebilir.
    Mouse tekerleği sayfa/form scroll davranışına bırakılır.
    """

    def wheelEvent(self, event: Any) -> None:
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """
    QSpinBox üzerinde mouse tekerleği ile yanlışlıkla sayı değişmesini engeller.
    """

    def wheelEvent(self, event: Any) -> None:
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """
    QDoubleSpinBox üzerinde mouse tekerleği ile yanlışlıkla ondalıklı sayı değişmesini engeller.
    """

    def wheelEvent(self, event: Any) -> None:
        event.ignore()