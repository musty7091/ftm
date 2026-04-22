from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class InfoCard(QFrame):
    def __init__(
        self,
        title: str,
        body: str,
        hint: str,
    ) -> None:
        super().__init__()

        self.setObjectName("Card")
        self.setMinimumHeight(135)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        body_label = QLabel(body)
        body_label.setObjectName("MutedText")
        body_label.setWordWrap(True)

        hint_label = QLabel(hint)
        hint_label.setObjectName("CardHint")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addStretch()
        layout.addWidget(hint_label)