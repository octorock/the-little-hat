from tlh.const import RomVariant


class Constraint:
    romA: RomVariant = None
    offsetA: int = 0
    romB: RomVariant = None
    offsetB: int = 0
    certainty: int = 0
    note: str = None

class ConstraintManager:
    def __init__(self, variants: set[RomVariant]) -> None:
        """
        Pass a set of all RomVariants that should be linked using this constraint manager
        """
        self.variants = variants
        self.constraints = []

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def to_local(self, rom: RomVariant, virtual_address: int) -> int:
        """
        Convert from a virtual address to a local address for a certain rom variant
        """
        if not rom in self.variants:
            raise RomVariantNotAddedError()
        return virtual_address

    def to_virtual(self, rom: RomVariant, local_address: int) -> int:
        """
        Convert from a local address for a certain rom variant to a virtual address
        """
        if not rom in self.variants:
            raise RomVariantNotAddedError()
        return local_address


class RomVariantNotAddedError(Exception):
    pass