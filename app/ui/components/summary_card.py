from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SummaryCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        hint: str,
        card_type: str = "normal",
    ) -> None:
        super().__init__()

        if card_type == "highlight":
            self.setObjectName("CardHighlight")
        elif card_type == "risk":
            self.setObjectName("CardRisk")
        elif card_type == "success":
            self.setObjectName("CardSuccess")
        else:
            self.setObjectName("Card")

        self.setMinimumHeight(145)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")
        value_label.setWordWrap(True)

        hint_label = QLabel(hint)
        hint_label.setObjectName("CardHint")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addStretch()
        layout.addWidget(value_label)
        layout.addWidget(hint_label)