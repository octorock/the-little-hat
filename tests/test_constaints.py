

from tlh.const import RomVariant
from tlh.data.constraints import Constraint, ConstraintManager, RomVariantNotAddedError, InvalidConstraintError
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

def test_sparse_constraint():
    # v        E   J
    # 0        0   0
    # 1        x   1
    # ...      ... ...
    # 0xffffff 1---0xffffff
    manager = ConstraintManager({RomVariant.EU, RomVariant.JP})
    add_j_e_constraint(manager, 0xffffff, 1)
    manager.rebuild_relations()
    assert_j_e_address(manager, 0,0,0)
    assert_j_e_address(manager, 1,1,-1)
    assert_j_e_address(manager, 0xfffffe,0xfffffe, -1)
    assert_j_e_address(manager, 0xffffff,0xffffff, 1)

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

def test_conflicting_constraint():
    with pytest.raises(InvalidConstraintError):
        manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
        add_j_e_constraint(manager, 1, 0)
        add_j_e_constraint(manager, 1, 3)
        manager.rebuild_relations()
        manager.print_relations()

def test_conflicting_constraint_cross():
    with pytest.raises(InvalidConstraintError):
        manager = ConstraintManager({RomVariant.JP, RomVariant.EU})
        add_j_e_constraint(manager, 1, 3)
        add_j_e_constraint(manager, 3, 1)
        manager.rebuild_relations()
        manager.print_relations()

def test_conflicting_constraints_loop():
    with pytest.raises(InvalidConstraintError):
        manager = ConstraintManager({RomVariant.JP, RomVariant.EU, RomVariant.USA})
        add_u_j_constraint(manager, 1, 3)
        add_j_e_constraint(manager, 4, 6)
        add_u_e_constraint(manager, 0, 7)
        manager.rebuild_relations()
        manager.print_relations()

def add_u_j_constraint(manager: ConstraintManager, usa_address: int, jp_address: int):
    constraint = Constraint()
    constraint.romA = RomVariant.USA
    constraint.addressA = usa_address
    constraint.romB = RomVariant.JP
    constraint.addressB = jp_address
    manager.add_constraint(constraint)

def add_u_e_constraint(manager: ConstraintManager, usa_address: int, eu_address: int):
    constraint = Constraint()
    constraint.romA = RomVariant.USA
    constraint.addressA = usa_address
    constraint.romB = RomVariant.EU
    constraint.addressB = eu_address
    manager.add_constraint(constraint)


def assert_u_j_e_address(manager: ConstraintManager, virtual_address:int, usa_address:int, jp_address:int, eu_address:int):
    assert_differing_address(manager, RomVariant.USA, usa_address, virtual_address)
    assert_differing_address(manager, RomVariant.JP, jp_address, virtual_address)
    assert_differing_address(manager, RomVariant.EU, eu_address, virtual_address)


def test_three_roms():
    # v U J E
    # 0 0 0 0 
    # 1 1 x 1
    # 2 2-1 x
    # 3 3 2-2
    # 4 4 3 3
    manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU})
    add_u_j_constraint(manager, 2, 1)
    add_j_e_constraint(manager, 2, 2)
    manager.rebuild_relations()
    manager.print_relations()

    assert_u_j_e_address(manager, 0,0,0,0)
    assert_u_j_e_address(manager, 1, 1, -1, 1)
    assert_u_j_e_address(manager, 2, 2, 1, -1)
    assert_u_j_e_address(manager, 3, 3, 2, 2)
    assert_u_j_e_address(manager, 4, 4, 3, 3)

def test_three_cycle():
    # v U J E
    # 0 0 0 0 
    # 1 x 1 1
    # 2 1-2-2-
    # 3 2 3 x
    # 4 3 4-3
    # 5 x 5 4
    # 6 4 6 5-
    manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU})
    add_u_j_constraint(manager, 1, 2)
    add_j_e_constraint(manager, 2, 2)
    add_u_e_constraint(manager, 1, 2)
    add_j_e_constraint(manager, 4, 3)
    add_u_e_constraint(manager, 4, 5)
    manager.rebuild_relations()
    manager.print_relations()
    assert_u_j_e_address(manager, 0,0,0,0)
    assert_u_j_e_address(manager, 1,-1,1,1)
    assert_u_j_e_address(manager, 2,1,2,2)
    assert_u_j_e_address(manager, 3,2,3,-1)
    assert_u_j_e_address(manager, 4,3,4,3)
    assert_u_j_e_address(manager, 5,-1,5,4)
    assert_u_j_e_address(manager, 6,4,6,5)


def add_e_d_constraint(manager: ConstraintManager, eu_address: int, demo_address: int):
    constraint = Constraint()
    constraint.romA = RomVariant.EU
    constraint.addressA = eu_address
    constraint.romB = RomVariant.DEMO
    constraint.addressB = demo_address
    manager.add_constraint(constraint)

def add_u_d_constraint(manager: ConstraintManager, usa_address: int, demo_address: int):
    constraint = Constraint()
    constraint.romA = RomVariant.USA
    constraint.addressA = usa_address
    constraint.romB = RomVariant.DEMO
    constraint.addressB = demo_address
    manager.add_constraint(constraint)


def assert_u_j_e_d_address(manager: ConstraintManager, virtual_address:int, usa_address:int, jp_address:int, eu_address:int, demo_address: int):
    assert_differing_address(manager, RomVariant.USA, usa_address, virtual_address)
    assert_differing_address(manager, RomVariant.JP, jp_address, virtual_address)
    assert_differing_address(manager, RomVariant.EU, eu_address, virtual_address)
    assert_differing_address(manager, RomVariant.DEMO, demo_address, virtual_address)

def test_four_roms():
    # v U J E D
    # 0 0 0 0 0
    # 1 1 x x x
    # 2 2-1 x x
    # 3 3 2-1 x
    # 4 4 3 2-1
    # 5 5-4 3 2-
    # 6 6 5 4 3
    manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU, RomVariant.DEMO})
    add_u_j_constraint(manager, 2, 1)
    add_j_e_constraint(manager, 2, 1)
    add_e_d_constraint(manager, 2, 1)
    add_u_d_constraint(manager, 5, 2)
    add_u_j_constraint(manager, 5, 4)
    manager.rebuild_relations()
    manager.print_relations()
    assert_u_j_e_d_address(manager, 0,0,0,0,0)
    assert_u_j_e_d_address(manager, 1,1,-1,-1,-1)
    assert_u_j_e_d_address(manager, 2,2,1,-1,-1)
    assert_u_j_e_d_address(manager, 3,3,2,1,-1)
    assert_u_j_e_d_address(manager, 4,4,3,2,1)
    assert_u_j_e_d_address(manager, 5,5,4,3,2)
    assert_u_j_e_d_address(manager, 6,6,5,4,3)



def test_bigger_offsets():
    #   v   U   J   E   D
    #   0   0   0   0   0
    #   9   9   9   9   9
    #  10   x  10  10  10
    #  19   x  19
    #  20  10--20
    #  39      39
    #  40       x
    #  50      40--50
    #  69          69
    #  90          70--90
    #  99  89  89  79  99
    # 100  90  90  80   x
    #     120         100-
    manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU, RomVariant.DEMO})
    add_u_j_constraint(manager, 10, 20)
    add_j_e_constraint(manager, 40, 50)
    add_e_d_constraint(manager, 70,90)
    add_u_d_constraint(manager, 120, 100)
    manager.rebuild_relations()
    manager.print_relations()
    assert_u_j_e_d_address(manager, 9,9,9,9,9)
    assert_u_j_e_d_address(manager, 10,-1,10,10,10)
    assert_u_j_e_d_address(manager, 19,-1,19,19,19)
    assert_u_j_e_d_address(manager, 20,10,20,20,20)
    assert_u_j_e_d_address(manager, 39,29,39,39,39)
    assert_u_j_e_d_address(manager, 40,30,-1,40,40)
    assert_u_j_e_d_address(manager, 50,40,40,50,50)
    assert_u_j_e_d_address(manager, 69,59,59,69,69)
    assert_u_j_e_d_address(manager, 90,80,80,70,90)
    assert_u_j_e_d_address(manager, 99,89,89,79,99)
    assert_u_j_e_d_address(manager, 100,90,90,80,-1)
    assert_u_j_e_d_address(manager, 130,120,120,110,100)


def test_many_small_differences():
    #  v  U  J  E  D
    #  0  0  0  0  0
    #  1  1  x
    #  2  2  x
    #  3  3--1     3
    #  4  4  2     x
    #  5  5  3  5--4-
    #  6  x  x  6
    #  7  x  4--7
    #  8  x  5  8
    #  9  6--6  x  8
    # 10  x  7  x  x
    # 11  7--8--9--9  # constraints from J to all
    # 12  8  9  x 10
    # 13  9 10 10-11
    # 14  x 11-11 x
    # 15 10-12 12 x
    # 16 11 13 13-12
    manager = ConstraintManager({RomVariant.USA, RomVariant.JP, RomVariant.EU, RomVariant.DEMO})
    add_u_d_constraint(manager, 5, 4)
    add_u_j_constraint(manager, 10, 12)
    add_u_j_constraint(manager, 3, 1)
    manager.add_constraint(Constraint(RomVariant.JP, 8, RomVariant.DEMO, 9))
    add_j_e_constraint(manager, 4, 7)
    add_u_j_constraint(manager, 6, 6)
    add_j_e_constraint(manager, 8, 9)
    add_j_e_constraint(manager, 11, 11)
    add_e_d_constraint(manager, 13, 12)
    add_e_d_constraint(manager, 5, 4)
    add_u_j_constraint(manager, 7, 8)
    add_e_d_constraint(manager, 10, 11)
    manager.rebuild_relations()
    manager.print_relations()
    assert_u_j_e_d_address(manager, 0,0,0,0,0)
    assert_u_j_e_d_address(manager, 1,1,-1,1,1)
    assert_u_j_e_d_address(manager, 2,2,-1,2,2)
    assert_u_j_e_d_address(manager, 3,3,1,3,3)
    assert_u_j_e_d_address(manager, 4,4,2,4,-1)
    assert_u_j_e_d_address(manager, 5,5,3,5,4)
    assert_u_j_e_d_address(manager, 6,-1,-1,6,5)
    assert_u_j_e_d_address(manager, 7,-1,4,7,6)
    assert_u_j_e_d_address(manager, 8,-1,5,8,7)
    assert_u_j_e_d_address(manager, 9,6,6,-1,8)
    assert_u_j_e_d_address(manager, 10, -1,7,-1,-1)
    assert_u_j_e_d_address(manager, 11, 7,8,9,9)
    assert_u_j_e_d_address(manager, 12, 8,9,-1,10)
    assert_u_j_e_d_address(manager, 13,9,10,10,11)
    assert_u_j_e_d_address(manager, 14,-1,11,11,-1)
    assert_u_j_e_d_address(manager, 15,10,12,12,-1)
    assert_u_j_e_d_address(manager, 16, 11,13,13,12)

def x_test_many_trivial_constraints():
    # TODO optimize more, so this number can be higher
    CONSTRAINT_COUNT = 1000
    manager = ConstraintManager({RomVariant.EU, RomVariant.JP})
    for i in range(0, CONSTRAINT_COUNT):
        add_j_e_constraint(manager, i, i)
    manager.rebuild_relations()
    for i in range(0, CONSTRAINT_COUNT):
        assert_j_e_address(manager, i,i,i)


def test_bug():
    manager = ConstraintManager({RomVariant.USA, RomVariant.DEMO})
    add_u_d_constraint(manager, 512657, 511637)
    add_u_d_constraint(manager, 513133, 512129)
    manager.rebuild_relations()
    # USA,512657,DEMO,511637,5,Pointer
    # USA,513133,DEMO,512129,5,Pointer