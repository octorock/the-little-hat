from dataclasses import dataclass
from PySide6.QtGui import QColor

@dataclass
class DisplayByte:
    text: str
    background: QColor
    is_selected: bool
