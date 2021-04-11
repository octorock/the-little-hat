from dataclasses import dataclass
from typing import Optional
from tlh.const import ROM_OFFSET
from tlh import settings
from sortedcontainers import SortedKeyList
from sortedcontainers.sortedlist import SortedList
from os import path

@dataclass
class Symbol:
    address: int = 0
    name: str = None
    file: str = None
    length: int = 0

symbols = SortedKeyList([], key=lambda x:x.address)


def get_symbol_at(local_address: int) -> Optional[Symbol]:
    if len(symbols) == 0:
        return None
    index = symbols.bisect_key_right(local_address)
    return symbols[index-1]


def load_symbols_from_map(path: str) -> None:
    global symbols
    with open(path, 'r') as map_file:

        # ignore header
        line = map_file.readline()
        while not line.startswith('rom'):
            line = map_file.readline()
        line = map_file.readline()
        while not line.startswith('rom'): # The second line starting with 'rom' is the one we need
            line = map_file.readline()

        # Parse declarations

        prev_symbol = None
        current_file = 'UNKNOWN'
        for line in map_file:
            if line.startswith(' .'):
                # ignore this definition of filename
                continue
            elif line.startswith('  '):
                parts = line.split()
                if len(parts) == 2 and parts[1] !='': # it is actually a symbol
                    addr = int(parts[0],16)-ROM_OFFSET
                    if prev_symbol is not None:
                        prev_symbol.length = addr-prev_symbol.address
                    symbol = Symbol(addr, parts[1], current_file)
                    symbols.add(symbol)
                    prev_symbol = symbol
                    
            elif not line.startswith(' *'):
                # this defines the name
                current_file = line.split('(')[0].strip()
