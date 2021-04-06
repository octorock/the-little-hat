from dataclasses import dataclass

import intervaltree
from tlh.const import RomVariant
from intervaltree import IntervalTree, Interval

@dataclass
class Pointer:
    rom_variant: RomVariant = None
    address: int = 0
    points_to: int = 0
    certainty: int = 0
    author: str = None
    note: str = None


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