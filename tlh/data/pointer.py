from dataclasses import dataclass
from tlh.const import RomVariant


@dataclass
class Pointer:
    rom_variant: RomVariant = None
    address: int = 0
    points_to: int = 0
    certainty: int = 0
    author: str = None
    note: str = None