from tlh.const import RomVariant
from tlh.data.constraints import ConstraintManager

class AbstractAddressResolver:
    def to_virtual(self, local_address: int) -> int:
        pass

    def to_local(self, virtual_address: int) -> int:
        pass


class TrivialAddressResolver(AbstractAddressResolver):
    def to_virtual(self, local_address: int) -> int:
        return local_address

    def to_local(self, virtual_address: int) -> int:
        return virtual_address


class LinkedAddressResolver(AbstractAddressResolver):
    def __init__(self, constraint_manager: ConstraintManager, rom_variant: RomVariant) -> None:
        self.constraint_manager = constraint_manager
        self.rom_variant = rom_variant

    def to_virtual(self, local_address: int) -> int:
        #print(f'Linked{self.rom_variant} tv')
        return self.constraint_manager.to_virtual(self.rom_variant, local_address)

    def to_local(self, virtual_address: int) -> int:
        #print(f'Linked{self.rom_variant} tl')
        return self.constraint_manager.to_local(self.rom_variant, virtual_address)