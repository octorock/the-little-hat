from dataclasses import dataclass
from typing import List
from tlh.data.pointer import Pointer
from tlh.data.constraints import Constraint
from PySide6.QtGui import QColor
from tlh.data.annotations import Annotation

@dataclass
class DisplayByte:
    text: str
    background: QColor
    is_selected: bool
    annotations: List[Annotation]
    constraints: List[Constraint]
    pointers: List[Pointer]
