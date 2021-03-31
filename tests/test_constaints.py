

from tlh.const import RomVariant
from tlh.data.constraints import Constraint, ConstraintManager, RomVariantNotAddedError
import pytest

def assert_same_offset(manager: ConstraintManager, rom: RomVariant, offset: int) -> None:
    assert offset == manager.to_virtual(rom, offset)
    assert offset == manager.to_local(rom, offset)

def assert_differing_offset(manager: ConstraintManager, rom: RomVariant, local_offset: int, virtual_offset: int) -> None:
    assert virtual_offset == manager.to_virtual(rom, local_offset)
    assert local_offset == manager.to_local(rom, virtual_offset)

def test_no_constaints():
    manager = ConstraintManager({RomVariant.USA, RomVariant.EU})
    assert_same_offset(manager, RomVariant.USA, 0)
    assert_same_offset(manager, RomVariant.EU, 0)
    assert_same_offset(manager, RomVariant.USA, 1)
    assert_same_offset(manager, RomVariant.EU, 1)
    assert_same_offset(manager, RomVariant.USA, 100)
    assert_same_offset(manager, RomVariant.EU, 100)
    assert_same_offset(manager, RomVariant.USA, 0xffffff)
    assert_same_offset(manager, RomVariant.EU, 0xffffff)

    with pytest.raises(RomVariantNotAddedError):
        assert_same_offset(manager, RomVariant.JP, 0)
    with pytest.raises(RomVariantNotAddedError):
        assert_same_offset(manager, RomVariant.DEMO, 0)

def test_first_constraint():
    # v  A B
    # 0  0 0
    # 1  x 1
    # 2  1-2 
    # 3  2 3
    # 4  3
    manager = ConstraintManager({RomVariant.USA, RomVariant.DEMO})
    constraint = Constraint()
    constraint.romA = RomVariant.USA
    constraint.offsetA = 1
    constraint.romB = RomVariant.DEMO
    constraint.offsetB = 2
    manager.add_constraint(constraint)
    assert_same_offset(manager, RomVariant.USA, 0)
    assert_same_offset(manager, RomVariant.DEMO, 0)
    assert_same_offset(manager, RomVariant.DEMO, 1)
    assert_same_offset(manager, RomVariant.DEMO, 2)
    assert_same_offset(manager, RomVariant.DEMO, 3)
    assert_same_offset(manager, RomVariant.DEMO, 0xffffff)
    assert_differing_offset(manager, RomVariant.USA, 1, 2)
    assert_differing_offset(manager, RomVariant.USA, 2, 3)
    assert_differing_offset(manager, RomVariant.USA, 0xffffff, 0xffffff+1)