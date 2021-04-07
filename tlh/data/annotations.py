from dataclasses import dataclass
from tlh.const import RomVariant
from PySide6.QtGui import QColor
from intervaltree import Interval, IntervalTree

@dataclass
class Annotation:
    rom_variant: RomVariant = None
    address: int = 0
    length: int = 0
    color: QColor = None
    author: str = None
    note: str = None

class AnnotationList:
    def __init__(self, annotations: list[Annotation], rom_variant: RomVariant) -> None:
        intervals = []

        for annotation in annotations:
            if annotation.rom_variant == rom_variant:
                intervals.append(Interval(annotation.address, annotation.address+annotation.length, annotation))

        self.tree = IntervalTree(intervals)

    def get_annotations_at(self, index: int) -> list[Annotation]:
        annotations = []
        for interval in self.tree.at(index):
            annotations.append(interval.data)
        return annotations