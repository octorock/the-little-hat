

from tlh.const import RomVariant
from tlh.data.constraints import Constraint, ConstraintManager, RomVariantNotAddedError
import pytest

# The tables in this file are showing the configuration of the constraints
# The headers have the following meaning:
# v: virtual address
# U: RomVariation.USA
# D: RomVariation.DEMO
# E: RomVariation.EU
# J: RomVariation.JP
# - between numbers denotes that these two are connected with a constraint

def assert_same_address(manager: ConstraintManager, rom: RomVariant, address: int) -> None:
    assert address == manager.to_virtual(rom, address)
    assert address == manager.to_local(rom, address)

def assert_differing_address(manager: ConstraintManager, rom: RomVariant, local_address: int, virtual_address: int) -> None:
    assert virtual_address == manager.to_virtual(rom, local_address)
    assert local_address == manager.to_local(rom, virtual_address)

def test_no_constaints():
    manager = ConstraintManager({RomVariant.USA, RomVariant.EU})
    assert_same_address(manager, RomVariant.USA, 0)
    assert_same_address(manager, RomVariant.EU, 0)
    assert_same_address(manager, RomVariant.USA, 1)
    assert_same_address(manager, RomVariant.EU, 1)
    assert_same_address(manager, RomVariant.USA, 100)
    assert_same_address(manager, RomVariant.EU, 100)
    assert_same_address(manager, RomVariant.USA, 0xffffff)
    assert_same_address(manager, RomVariant.EU, 0xffffff)

    with pytest.raises(RomVariantNotAddedError):
        assert_same_address(manager, RomVariant.JP, 0)
    with pytest.raises(RomVariantNotAddedError):
        assert_same_address(manager, RomVariant.DEMO, 0)

def test_first_constraint():
    # v  U D
    # 0  0 0
    # 1  x 1
    # 2  1-2 
    # 3  2 3
    # 4  3
    manager = ConstraintManager({RomVariant.USA, RomVariant.DEMO})
    constraint = Constraint()
    constraint.romA = RomVariant.USA
    constraint.addressA = 1
    constraint.romB = RomVariant.DEMO
    constraint.addressB = 2
    manager.add_constraint(constraint)
    assert_same_address(manager, RomVariant.USA, 0)
    assert_same_address(manager, RomVariant.DEMO, 0)
    assert_same_address(manager, RomVariant.DEMO, 1)
    assert_same_address(manager, RomVariant.DEMO, 2)
    assert_same_address(manager, RomVariant.DEMO, 3)
    assert_same_address(manager, RomVariant.DEMO, 0xffffff)
    assert_differing_address(manager, RomVariant.USA, 1, 2)
    assert_differing_address(manager, RomVariant.USA, 2, 3)
    assert_differing_address(manager, RomVariant.USA, 0xffffff, 0xffffff+1)
    print('---')
    assert -1 == manager.to_local(RomVariant.USA, 1)

def test_longer_constraint():
    # v   E   J
    # 0   0   0
    # 1   x   1
    # ... ... ...
    # 100 1   100
    # 101 2   101
    manager = ConstraintManager({RomVariant.EU, RomVariant.JP})
    constraint = Constraint()
    constraint.romA = RomVariant.JP
    constraint.addressA = 100
    constraint.romB = RomVariant.EU
    constraint.addressB = 1
    manager.add_constraint(constraint)
    assert_same_address(manager, RomVariant.EU, 0)
    assert_same_address(manager, RomVariant.JP, 0)
    assert_same_address(manager, RomVariant.JP, 100)
    assert_same_address(manager, RomVariant.JP, 5000)
    assert -1 == manager.to_local(RomVariant.EU, 1)
    assert_differing_address(manager, RomVariant.EU, 1, 100)
    assert_differing_address(manager, RomVariant.EU, 100, 199)


def add_j_e_constraint(manager: ConstraintManager, jp_address: int, eu_address: int):
    constraint = Constraint()
    constraint.romA = RomVariant.JP
    constraint.addressA = jp_address
    constraint.romB = RomVariant.EU
    constraint.addressB = eu_address
    manager.add_constraint(constraint)

#def test_two_constraints():
    # v J E
    # 0 0 0
    # 1 x 1
    # 2 1-2
    # 3 2 x
    # 4 3-3
    # 5 4 4
#    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
#    add_j_e_constraint(manager, 1, 2)
#    add_j_e_constraint(manager, 3, 3)

#    assert_same_address(manager, RomVariant.EU, 1)
#    assert_same_address(manager, RomVariant.EU, 2)
#    assert_differing_address(manager, RomVariant.JP, 1, 2)
#    assert_differing_address(manager, RomVariant.JP, 2, 3)
#    assert_differing_address(manager, RomVariant.JP, 3, 4)
#    assert_differing_address(manager, RomVariant.JP, 4, 5)
#    assert_differing_address(manager, RomVariant.EU, 3, 4)
#    assert_differing_address(manager, RomVariant.EU, 4, 5)

# TODO
# add two constraints
# add constraints in the wrong order
# add situation were local_address == next.local_address can occur (if it exists)
# add situation with invalid constraint
# add constraints between three files
# add constraints between four files
# add cyclic constraints?