from dataclasses import dataclass
from tlh.const import RomVariant
from intervaltree import IntervalTree, Interval

@dataclass
class Pointer:
    rom_variant: RomVariant = None
    address: int = 0
    points_to: int = 0
    certainty: int = 0
    author: str = ''
    note: str = ''


class PointerList:
    def __init__(self, pointers: list[Pointer], rom_variant: RomVariant) -> None:
        intervals = []

        for pointer in pointers:
            if pointer.rom_variant == rom_variant:
                intervals.append(Interval(pointer.address, pointer.address+4, pointer))

        self.tree = IntervalTree(intervals)

    def get_pointers_at(self, index: int) -> list[Pointer]:
        pointers = []
        for interval in self.tree.at(index):
            pointers.append(interval.data)
        return pointers

    def append(self, pointer: Pointer) -> None:
        self.tree.add(Interval(pointer.address, pointer.address+4, pointer))

    def __iter__(self):
        return map(lambda x: x.data, self.tree.__iter__())