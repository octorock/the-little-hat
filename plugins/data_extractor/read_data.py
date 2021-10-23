from tlh.const import ROM_OFFSET
from tlh.data.database import get_file_in_database
import json
import os

from tlh.data.symbols import SymbolList

def conv_addr(addr: int) -> int:
    if addr > 0x08000000:
        return addr - 0x08000000
    return addr

class Reader:
    def __init__(self, data: bytearray, symbols: SymbolList) -> None:
        self.data = data
        self.cursor = 0
        self.bitfield = 0
        self.bitfield_remaining = 0
        self.symbols = symbols

    def read_u8(self) -> int:
        val = self.data[self.cursor]
        self.cursor += 1
        return val

    def read_s8(self) -> int:
        val = self.data[self.cursor]
        self.cursor += 1
        if val > 127:
            return val-256
        else:
            return val

    def read_u16(self) -> int:
        val = self.data[self.cursor:self.cursor+2]
        self.cursor += 2
        return int.from_bytes(val, 'little')

    def read_s16(self) -> int:
        val = self.read_u16()
        if val > 32768:
            return val - 65536
        else:
            return val

    def read_u32(self) -> int:
        val = self.data[self.cursor:self.cursor+4]
        self.cursor += 4
        return int.from_bytes(val, 'little')

structs = None
unions = None

def load_json_files() -> None:
    global structs
    with open(get_file_in_database(os.path.join('data_extractor', 'structs.json'))) as file:
        structs = json.load(file)
#    print(structs)



def read_struct(reader: Reader, struct: any) -> any:
    res = {}
    for key in struct:
        res[key] = read_var(reader, struct[key])
    return res

def read_array(reader: Reader, type: str, length: int) -> any:
    res = []
    if length > 0:
        for i in range(length):
            res.append(read_var(reader, type))
    else:
        while reader.cursor < len(reader.data):
            res.append(read_var(reader, type))

    return res

def read_union(reader: Reader, union: any) -> any:
    assert(False)

def read_pointer(reader: Reader, type: str) -> any:
    pointer = reader.read_u32()
    if pointer == 0:
        return 'NULL'
    symbol = reader.symbols.get_symbol_at(pointer - ROM_OFFSET)
    if symbol is None:
        raise Exception(f'Could not find symbol at {hex(pointer)}')
    return '&' + symbol.name

def read_var(reader: Reader, type: str) -> any:
    if '*' in type:
        return read_pointer(reader, type)
    if '[' in type:
        arr = type.split('[')
        if len(arr[1]) == 1:
            length = 0
        else:
            length = int(arr[1][0:-1])
        return read_array(reader, arr[0], length)
    if type == 'u8':
        return reader.read_u8()
    elif type == 's8':
        return reader.read_s8()
    elif type == 'u16':
        return reader.read_u16()
    elif type == 's16':
        return reader.read_s16()
    elif type == 'u32':
        return reader.read_u32()
    elif type in structs:
        return read_struct(reader, structs[type])
    else:
        raise Exception(f'Unknown type {type}')