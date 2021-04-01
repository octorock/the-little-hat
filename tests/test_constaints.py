

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
    if local_address != -1:
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
    manager.rebuild_relations()
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
    # 100 1---100
    # 101 2   101
    manager = ConstraintManager({RomVariant.EU, RomVariant.JP})
    constraint = Constraint()
    constraint.romA = RomVariant.JP
    constraint.addressA = 100
    constraint.romB = RomVariant.EU
    constraint.addressB = 1
    manager.add_constraint(constraint)
    manager.rebuild_relations()
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

def test_two_constraints():
    # v J E
    # 0 0 0
    # 1 x 1
    # 2 1-2
    # 3 2 x
    # 4 3-3
    # 5 4 4
    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
    add_j_e_constraint(manager, 1, 2)
    add_j_e_constraint(manager, 3, 3)
    manager.rebuild_relations()
    manager.print_relations()

    assert_same_address(manager, RomVariant.EU, 1)
    assert_same_address(manager, RomVariant.EU, 2)
    assert_differing_address(manager, RomVariant.JP, 1, 2)
    assert_differing_address(manager, RomVariant.JP, 2, 3)
    assert_differing_address(manager, RomVariant.JP, 3, 4)
    assert_differing_address(manager, RomVariant.JP, 4, 5)
    assert_differing_address(manager, RomVariant.EU, 3, 4)
    assert_differing_address(manager, RomVariant.EU, 4, 5)

def test_two_constraints_wrong_order():
    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
    add_j_e_constraint(manager, 3, 3)
    add_j_e_constraint(manager, 1, 2)
    manager.rebuild_relations()
    manager.print_relations()

    assert_same_address(manager, RomVariant.EU, 1)
    assert_same_address(manager, RomVariant.EU, 2)
    assert_differing_address(manager, RomVariant.JP, 1, 2)
    assert_differing_address(manager, RomVariant.JP, 2, 3)
    assert_differing_address(manager, RomVariant.JP, 3, 4)
    assert_differing_address(manager, RomVariant.JP, 4, 5)
    assert_differing_address(manager, RomVariant.EU, 3, 4)
    assert_differing_address(manager, RomVariant.EU, 4, 5)


def assert_j_e_address(manager: ConstraintManager, virtual_address:int, jp_address:int, eu_address:int):
    assert_differing_address(manager, RomVariant.JP, jp_address, virtual_address)
    assert_differing_address(manager, RomVariant.EU, eu_address, virtual_address)

def test_three_constraints():
    # v J E
    # 0 0 x
    # 1 1-0
    # 2 2 x
    # 3 3-1
    # 4 x 2
    # 5 x 3
    # 6 x 4
    # 7 4-5
    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
    add_j_e_constraint(manager, 1, 0)
    add_j_e_constraint(manager, 3, 1)
    add_j_e_constraint(manager, 4, 5)
    manager.rebuild_relations()
    manager.print_relations()

    assert_j_e_address(manager, 0,0,-1)
    assert_j_e_address(manager, 1,1,0)
    assert_j_e_address(manager, 2,2,-1)
    assert_j_e_address(manager, 3,3,1)
    assert_j_e_address(manager, 4,-1,2)
    assert_j_e_address(manager, 5,-1,3)
    assert_j_e_address(manager, 6,-1,4)
    assert_j_e_address(manager, 7,4,5)

def test_successive_constraints():
    # v  J E
    # 0  0 x
    # 1  1-0
    # 2  2 x
    # 3  3-1
    # 4  4 x
    # 5  5 x
    # 6  6-2
    # 7  x 3
    # 8  7-4
    # 9  8-5
    # 10 x 6
    # 11 x 7
    # 12 x 8
    # 13 9-9
    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
    add_j_e_constraint(manager, 1, 0)
    add_j_e_constraint(manager, 3, 1)
    add_j_e_constraint(manager, 6, 2)
    add_j_e_constraint(manager, 7, 4)
    add_j_e_constraint(manager, 8, 5)
    add_j_e_constraint(manager, 9, 9)
    manager.rebuild_relations()
    manager.print_relations()
    assert_j_e_address(manager, 0,0,-1)
    assert_j_e_address(manager, 1,1,0)
    assert_j_e_address(manager, 2,2,-1)
    assert_j_e_address(manager, 3,3,1)
    assert_j_e_address(manager, 4,4,-1)
    assert_j_e_address(manager, 5,5,-1)
    assert_j_e_address(manager, 6,6,2)
    assert_j_e_address(manager, 7,-1,3)
    assert_j_e_address(manager, 8,7,4)
    assert_j_e_address(manager, 9,8,5)
    assert_j_e_address(manager, 10,-1,6)
    assert_j_e_address(manager, 11,-1,7)
    assert_j_e_address(manager, 12,-1,8)
    assert_j_e_address(manager, 13,9,9)

def test_close_constraints():
    # v  J E
    # 0  0 x
    # 1  1-0
    # 2  2 x
    # 3  3-1
    # 4  4 x
    # 5  5-2
    # 6  x 3
    # 7  6-4
    # 8  7 5
    # 9  8 6
    # 10 x 7
    # 11 x 8
    # 12 9-9
    manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
    add_j_e_constraint(manager, 1, 0)
    add_j_e_constraint(manager, 3, 1)
    add_j_e_constraint(manager, 5, 2)
    add_j_e_constraint(manager, 6, 4)
    add_j_e_constraint(manager, 9, 9)
    manager.rebuild_relations()
    manager.print_relations()
    assert_j_e_address(manager, 0,0,-1)
    assert_j_e_address(manager, 1,1,0)
    assert_j_e_address(manager, 2,2,-1)
    assert_j_e_address(manager, 3,3,1)
    assert_j_e_address(manager, 4,4,-1)
    assert_j_e_address(manager, 5,5,2)
    assert_j_e_address(manager, 6,-1,3)
    assert_j_e_address(manager, 7,6,4)
    assert_j_e_address(manager, 8,7,5)
    assert_j_e_address(manager, 9,8,6)
    assert_j_e_address(manager, 10,-1,7)
    assert_j_e_address(manager, 11,-1,8)
    assert_j_e_address(manager, 12,9,9)
# TODO
# add situation with conflicting constraint
# add constraints between three files
# add constraints between four files
# add cyclic constraints?
