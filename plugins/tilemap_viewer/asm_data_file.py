
from dataclasses import dataclass
from typing import Dict, List
import re

@dataclass
class AsmDataFileEntry:
    name: str
    attributes: List[str]
    attributes_dict: Dict[str, str]

@dataclass
class AsmDataFileSymbol:
    name: str
    entries: List[AsmDataFileEntry]

class AsmDataFile:
    def __init__(self, path: str) -> None:
        self.symbols: Dict[str, AsmDataFileSymbol] = {}
        with open(path, 'r') as f:
            line = ''
            def skip_header():
                global line
                while True:
                    line = f.readline().strip()
                    if len(line) == 0:
                        continue
                    if '.include' in line or '.section' in line or '.align' in line:
                        continue
                    if line.startswith('@'):
                        continue

                    # Reached end of headers
                    return line
            def skip_enum():
                global line
                while True:
                    line = f.readline().strip()
                    if 'enum' in line:
                        continue
                    if line.startswith('.if') or line.startswith('.endif'):
                        continue
                    # Reached end of enums
                    return line

            line = skip_header()

            first = True
            current_symbol = None
            while True:
                if first:
                    first = False
                else:
                    line = f.readline()
                if line == '': # EOF
                    break
                line = line.strip()
                if line == 'enum_start':
                    skip_enum()
                elif '::' in line: # label
                    name = line.split('::')[0]
                    if name in self.symbols:
                        raise Exception(f'Symbol {name} already read previously.')
                    current_symbol = AsmDataFileSymbol(name, [])
                    self.symbols[name] = current_symbol
                elif line.startswith('.if') or line.startswith('.endif'):
                    # TODO handle ifs correctly
                    pass
                elif len(line) > 0 and not line.startswith('@'): # entry
                    # TODO remove everything after @ at the end of the line

                    #parts = line.split()
                    parts = list(filter(None, re.split(r'[\s,]', line)))
                    attributes = parts[1:]
                    attributes_dict = {}
                    for attribute in attributes:
                        if '=' in attribute:
                            parts = attribute.split('=')
                            attributes_dict[parts[0].strip()] = parts[1].strip()
                    current_symbol.entries.append(AsmDataFileEntry(parts[0], attributes, attributes_dict))
