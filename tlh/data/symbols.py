from dataclasses import dataclass
from typing import Optional
from tlh.const import ROM_OFFSET, RomVariant
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

symbols: dict[RomVariant, SortedKeyList[Symbol]] = {}

def are_symbols_loaded(rom_variant: RomVariant) -> bool:
    return rom_variant in symbols

class SymbolList:
    symbols: SortedKeyList[Symbol]

    def __init__(self, symbols: SortedKeyList[Symbol]) -> None:
        self.symbols = symbols

    def get_symbol_at(self, local_address: int) -> Optional[Symbol]:
        if len(self.symbols) == 0:
            return None
        index = self.symbols.bisect_key_right(local_address)
        return self.symbols[index-1]

    def get_symbol_after(self, local_address: int) -> Optional[Symbol]:
        if len(self.symbols) == 0:
            return None
        index = self.symbols.bisect_key_right(local_address)
        return self.symbols[index]

    def find_symbol_by_name(self, name: str) -> Optional[Symbol]:
        for symbol in self.symbols:
            if symbol.name == name:
                return symbol
        return None


def load_symbols_from_map(path: str) -> None:
    global symbols
    symbols = SortedKeyList([], key=lambda x:x.address)
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
