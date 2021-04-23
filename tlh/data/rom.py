from typing import Optional
from tlh.const import RomVariant
from tlh import settings


class Rom:
    def __init__(self, filename: str):
        with open(filename, 'rb') as rom:
            self.bytes = bytearray(rom.read())

    def get_bytes(self, from_index: int, to_index: int) -> bytearray:
        # TODO apply constraints here? Or one level above in the HexEditorInstance?
        return self.bytes[from_index:to_index]

    def get_byte(self, index: int) -> int:
        return self.bytes[index]

    def length(self) -> int:
        return len(self.bytes)

    def get_pointer(self, index: int) -> int:
        return int.from_bytes(self.bytes[index:index+4], 'little')


# Rom data is read only, so we only need to read it once
roms: dict[RomVariant, Rom] = {}

# TODO invalidate roms when settings change?
# necessary? Once we have a valid rom, there will be no changes


def get_rom(variant: RomVariant) -> Optional[Rom]:
    global roms
    if variant not in roms:
        try:
            roms[variant] = Rom(settings.get_rom(variant))
        except:
            return None
    return roms[variant]

def invalidate_rom(variant: RomVariant) -> None:
    global roms
    if variant in roms:
        del roms[variant]