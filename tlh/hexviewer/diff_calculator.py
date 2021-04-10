from tlh.const import RomVariant
from tlh.data.constraints import ConstraintManager
from tlh.data.rom import get_rom


class AbstractDiffCalculator:
    def is_diffing(self, virtual_address: int) -> bool:
        pass


class NoDiffCalculator(AbstractDiffCalculator):
    def is_diffing(self, virtual_address: int) -> bool:
        return False


class LinkedDiffCalculator(AbstractDiffCalculator):
    def __init__(self, constraint_manager: ConstraintManager, variants: list[RomVariant]) -> None:
        self.constraint_manager = constraint_manager
        self.variants = variants

    def set_variants(self, variants: list[RomVariant]) -> None:
        self.variants = variants

    def is_diffing(self, virtual_address: int) -> bool:
        # TODO cache this, optimize accesses of rom data
        data = None
        for variant in self.variants:
            local_address = self.constraint_manager.to_local(
                variant, virtual_address)
            if local_address == -1 or local_address > 0xffffff:
                # does count as a difference
                return True
            local_data = get_rom(variant).get_byte(local_address)
            if data is None:
                data = local_data
                continue
            if data != local_data:
                return True
        return False
