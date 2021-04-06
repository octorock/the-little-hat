from dataclasses import dataclass
from tlh.const import RomVariant
from PySide6.QtGui import QColor

@dataclass
class Annotation:
    rom_variant: RomVariant = None
    address: int = 0
    length: int = 0
    color: QColor = None
    author: str = None
    note: str = None