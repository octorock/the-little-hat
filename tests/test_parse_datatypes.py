
from plugins.data_extractor.data_types import DataType, parse_type


def test_simple():
    type = parse_type('extern u8 test;')
    assert type == DataType(regex=0, name='test', type='u8', count=0, count2=0, params='', inner_const=False)
    type = parse_type('u8 test;')
    assert type == DataType(regex=0, name='test', type='u8', count=0, count2=0, params='', inner_const=False)

def test_exit_lists():
    type = parse_type('extern const Transition* const gExitLists_SanctuaryEntrance[];')
    assert type == DataType(regex=1, name='gExitLists_SanctuaryEntrance', type='Transition*', count=None, count2=0, params='', inner_const=True)
    type = parse_type('extern const Transition* const* const gExitLists[];')
    assert type == DataType(regex=1, name='gExitLists', type='Transition* const*', count=None, count2=0, params='', inner_const=True)

def test_func_lists():
    type = parse_type('void (*const OctorokBoss_Functions[])(OctorokBossEntity*);')
    assert type == DataType(regex=3, name='OctorokBoss_Functions', type='', count=None, count2=0, params='OctorokBossEntity*', inner_const=False)
