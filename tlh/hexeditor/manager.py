from enum import Enum
from tlh.data.database import read_constraints, write_constraints
from tlh.data.constraints import Constraint, ConstraintManager
from tlh.data.rom import Rom, get_rom
from tlh.const import ROM_OFFSET, RomVariant
from PySide6.QtCore import QObject
from dataclasses import dataclass


class ByteStatus(Enum):
    NONE = 0
    DIFFERING = 1



@dataclass
class DisplayByte:
    text: str
    status: ByteStatus




class HexEditorInstance(QObject):
    """
    Object that is passed to a single hex editor
    uses the constraint manager to translate from virtual to local addresses and vice versa
    """
    def __init__(self, parent, rom_variant: RomVariant, rom: Rom, constraint_manager: ConstraintManager) -> None:
        super().__init__(parent=parent)
        self.manager = parent
        self.rom_variant = rom_variant
        self.rom = rom
        self.constraint_manager = constraint_manager


    def get_local_label(self, index: int) -> str:
        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return ''
        return '%08X' % (local_address + ROM_OFFSET)

    def get_display_byte_for_index(self, index: int) -> DisplayByte:
        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return DisplayByte('  ', ByteStatus.NONE)
        
        return DisplayByte('%02X' % self.rom.get_byte(local_address), 
        ByteStatus.DIFFERING if self.manager.is_diffing(index) else ByteStatus.NONE
        )


    def get_bytes(self, from_index: int, to_index: int) -> list[DisplayByte]:
        return list(map(
            self.get_display_byte_for_index
                    , range(from_index, to_index)
        ))

    def length(self) -> int:
        return self.rom.length()




class HexEditorManager(QObject):
    """
    Manages all hex editors
    """
    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.variants = {RomVariant.USA, RomVariant.DEMO}
        self.roms: dict[RomVariant, Rom] = {}
        for variant in self.variants:
            self.roms[variant] = get_rom(variant)
        self.constraint_manager = ConstraintManager(self.variants) # TODO make configurable
        constraints = read_constraints()
        self.constraint_manager.add_all_constraints(constraints)        
        #constraints.append(Constraint(RomVariant.USA, 0x07d46d,RomVariant.DEMO, 0x07d081, 5, 'Pointer'))
        write_constraints(constraints)


    def get_hex_editor_instance(self, rom_variant: RomVariant)-> HexEditorInstance:
        return HexEditorInstance(self, rom_variant, self.roms[rom_variant], self.constraint_manager)


    def is_diffing(self, virtual_address: int) -> bool:
        # TODO cache this, optimize accesses of rom data

        data = None
        for variant in self.variants:
            local_address = self.constraint_manager.to_local(variant, virtual_address)
            if local_address == -1:
                # does not count as a difference
                continue
            local_data = self.roms[variant].get_byte(local_address)
            if data is None:
                data = local_data
                continue
            if data != local_data:
                return True
        return False
        
