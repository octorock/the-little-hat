from dataclasses import dataclass
import re


@dataclass
class DataType:
    '''
    0: Single data
    1: Arrays of data
    2: Arrays of arrays of data
    3: Arrays of function pointers
    4: Arrays of arrays of puncion pointers
    '''
    regex: int
    name: str
    type: str
    count: int
    count2: int
    params: str
    inner_const: bool # Is the inner pointer also const?

def parse_type(type: str) -> DataType:
    match = re.search('(extern )?(const )?(?P<type>\S+) (?P<name>\w+);', type)
    if match is not None:
        return DataType(0, match.group('name'), match.group('type'), 0, 0, '', False)

    match = re.search('(extern )?(const )?(?P<type>\S+(?: const\*)*) (?P<inner_const>const )?(?P<name>\w+)\[(?P<count>\w+)?\];', type)
    if match is not None:
        return DataType(1, match.group('name'), match.group('type'), match.group('count'), 0, '', match.group('inner_const') != None)

    match = re.search('(extern )?(const )?(?P<type>\S+) (?P<name>\w+)\[(?P<count>\w+)?\]\[(?P<count2>\w+)?\];', type)
    if match is not None:
        return DataType(2, match.group('name'), match.group('type'), match.group('count'), match.group('count2'), '', False)

    match = re.search('(extern )?(const )?void \(\*(const )?(?P<name>\w+)\[(?P<count>\w+)?\]\)\((?P<params>.*)\);', type)
    if match is not None:
        return DataType(3, match.group('name'), '', match.group('count'), 0, match.group('params'), False)

    match = re.search('(extern )?(const )?void \(\*(const )?(?P<name>\w+)\[(?P<count>\w+)?\]\[(?P<count2>\w+)\]\)\((?P<params>.*)\);', type)
    if match is not None:
        return DataType(4, match.group('name'), '', match.group('count'), match.group('count2'), match.group('params'), False)

    return None