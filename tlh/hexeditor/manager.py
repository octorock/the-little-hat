from enum import Enum
from tlh.data.database import read_constraints, write_constraints
from tlh.data.constraints import Constraint, ConstraintManager
from tlh.data.rom import Rom, get_rom
from tlh.const import ROM_OFFSET, RomVariant
from PySide6.QtCore import QObject, Signal
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

    cursor_moved = Signal(int)
    cursor_moved_externally = Signal(int)

    def __init__(self, parent, rom_variant: RomVariant, rom: Rom, constraint_manager: ConstraintManager) -> None:
        super().__init__(parent=parent)
        self.manager = parent
        self.rom_variant = rom_variant
        self.rom = rom
        self.constraint_manager = constraint_manager

        self.display_byte_cache = {} # TODO invalidate this cache if a constraint is added


    def get_local_label(self, index: int) -> str:
        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return ''
        return '%08X' % (local_address + ROM_OFFSET)

    def get_display_byte_for_index(self, index: int) -> DisplayByte:
        if index in self.display_byte_cache: # TODO test if the cache actually improves performance or is just a memory waste
            return self.display_byte_cache[index]

        local_address = self.constraint_manager.to_local(self.rom_variant, index)
        if local_address == -1:
            return DisplayByte('  ', ByteStatus.NONE)

        # TODO make sure local address is < length of rom
        
        display_byte = DisplayByte('%02X' % self.rom.get_byte(local_address), 
        ByteStatus.DIFFERING if self.manager.is_diffing(index) else ByteStatus.NONE
        )
        self.display_byte_cache[index] = display_byte
        return display_byte


    def get_bytes(self, from_index: int, to_index: int) -> list[DisplayByte]:
        return list(map(
            self.get_display_byte_for_index
                    , range(from_index, to_index)
        ))

    def length(self) -> int:
        # TODO calculate length of virtual rom
        return self.rom.length()

    def jump_to_local_address(self, local_address: int) -> None:
        virtual_address = self.constraint_manager.to_virtual(self.rom_variant, local_address)
        self.cursor_moved.emit(virtual_address)




class HexEditorManager(QObject):
    """
    Manages all hex editors
    """
    def __init__(self, parent) -> None:
        super().__init__(parent=parent)
        self.variants = {RomVariant.USA, RomVariant.DEMO, RomVariant.JP}
        self.roms: dict[RomVariant, Rom] = {}
        for variant in self.variants:
            self.roms[variant] = get_rom(variant)
        self.instances = []


        self.constraint_manager = ConstraintManager(self.variants) # TODO make configurable
        constraints = read_constraints()
        self.constraint_manager.add_all_constraints(constraints)        
        #constraints.append(Constraint(RomVariant.USA, 0x07d46d,RomVariant.DEMO, 0x07d081, 5, 'Pointer'))
        write_constraints(constraints)


    def get_hex_editor_instance(self, rom_variant: RomVariant)-> HexEditorInstance:
        instance = HexEditorInstance(self, rom_variant, self.roms[rom_variant], self.constraint_manager)
        instance.cursor_moved.connect(self.move_all_cursors)
        self.instances.append(instance)
        return instance

    def move_all_cursors(self, virtual_address: int) -> None:
        for instance in self.instances:
            instance.cursor_moved_externally.emit(virtual_address)

    

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
        
