from operator import add, le
from tlh.data.pointer import Pointer
from sortedcontainers.sortedlist import SortedKeyList
from tlh.data.symbols import are_symbols_loaded, get_symbol_at
from tlh.const import ROM_OFFSET, RomVariant
from tlh.data.database import get_pointer_database
from tlh.plugin.api import PluginApi
import os
from tlh import settings
from dataclasses import dataclass
from intervaltree import IntervalTree, Interval
from sortedcontainers import SortedList

@dataclass
class Incbin:
    address: int = 0
    length: int = 0
    file: str = ''

@dataclass(frozen=True, eq=True) # To make it hashable https://stackoverflow.com/a/52390734
class MissingLabel:
    address: int = 0
    symbol: str = ''
    offset: int = 0
    file: str = ''

def incbin_line(addr, length) -> str:
    return f'\t.incbin "baserom.gba", {"{0:#08x}".format(addr).upper().replace("0X", "0x")}, {"{0:#09x}".format(length).upper().replace("0X", "0x")}\n'


class PointerExtractorPlugin:
    name = 'Pointer Extractor'
    description = 'Extracts marked pointers from .incbins'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.incbins = None

    def load(self) -> None:
        self.action_parse_incbins = self.api.register_menu_entry('Parse files for .incbins', self.slot_parse_incbins)
        self.action_find_pointers = self.api.register_menu_entry('Find unextracted pointers', self.slot_find_pointers)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_parse_incbins)
        self.api.remove_menu_entry(self.action_find_pointers)

    def slot_parse_incbins(self) -> None:
        incbins = []

        assembly_extensions = ['.inc', '.s']
        for root, dir, files in os.walk(settings.get_repo_location()):
            for file in files:
                filename, file_extension = os.path.splitext(file)
                if file_extension in assembly_extensions:
                    incbins.extend(self.find_incbins(os.path.join(root, file)))
        self.incbins = IntervalTree(incbins)
        self.api.show_message('Pointer Extractor', f'{len(incbins)} .incbins found')

    def find_incbins(self, path: str) -> list[Interval]:
        incbins = []
        with open(path, 'r') as file:
            for line in file:
                line = line.strip()
                if line.startswith('.incbin "baserom.gba"'):
                    arr = line.split(',')
                    if len(arr) == 3:
                        addr = int(arr[1], 16)
                        length = int(arr[2], 16)
                        incbin = Interval(addr, addr+length, path)
                        incbins.append(incbin)
                    else:
                        print(f'Invalid incbin: {line}')
        return incbins


    def slot_find_pointers(self) -> None:
        if self.incbins is None:
            #self.api.show_error('Pointer Extractor', 'Need to parse .incbins first')
            #return
            self.slot_parse_incbins()

        if not are_symbols_loaded():
            self.api.show_error('Pointer Extractor', 'Symbols for USA rom need to be loaded first')
            return

        pointers = get_pointer_database().get_pointers(RomVariant.USA)

        to_extract: dict[str, SortedKeyList[Pointer]] = {}

        for pointer in pointers:
            found = self.incbins.at(pointer.address)
            if len(found) == 1:
                interval = found.pop()
                file = interval.data

                if not file in to_extract:
                    to_extract[file] = SortedKeyList(key=lambda x:x.address)

                to_extract[file].add(pointer)
#                print(hex(pointer.address))
                #print(found.pop())
            elif len(found) > 1:
                print(f'Found {len(found)} incbins for address {pointer.address}')
        
        # Count unextracted pointers
        count = 0
        for file in to_extract:
            print(f'{file}: {len(to_extract[file])}')
            count += len(to_extract[file])

        self.api.show_message('Pointer Extractor', f'{count} unextracted pointers found')
        print(count)


        # Find symbols that unextracted pointers point to
        missing_labels = {}
        count = 0
        for file in to_extract:
            for pointer in to_extract[file]:

                symbol = get_symbol_at(pointer.points_to - ROM_OFFSET)
                offset = pointer.points_to - ROM_OFFSET - symbol.address
                if offset > 1: # Offset 1 is ok for function pointers
                    if symbol.file not in missing_labels:
                        missing_labels[symbol.file] = SortedKeyList(key=lambda x:x.address)
                    # Insert Missing label if there is not already one
                    label = MissingLabel(pointer.points_to - ROM_OFFSET, symbol.name, offset, symbol.file)
                    if label not in missing_labels[symbol.file]:
                        missing_labels[symbol.file].add(label)
                        count += 1
                    continue

        print(f'{count} missing labels')
        for file in missing_labels:
            print(f'{file}: {len(missing_labels[file])}')


        # Insert labels for incbins
        for path in missing_labels:
            output_lines = []
            labels = missing_labels[path]
            next_label = labels.pop(0)

            # Try to find source assembly file
            asm_path = os.path.join(settings.get_repo_location(), path.replace('.o', '.s'))
            if not os.path.isfile(asm_path):
                print(f'Cannot insert labels in {path}')
                print(missing_labels[path])
                continue

            with open(asm_path, 'r') as file:
                for line in file:
                    if next_label is not None and line.strip().startswith('.incbin "baserom.gba"'):
                        arr = line.split(',')
                        if len(arr) == 3:
                            addr = int(arr[1], 16)
                            length = int(arr[2], 16)

                            while next_label is not None and next_label.address < addr:
                                if len(labels) == 0: # Extracted all labels
                                    next_label = None
                                    break
                                next_label = labels.pop(0)
                                continue

                            while next_label is not None and next_label.address >= addr and next_label.address < addr+length:
                                # Calculate new incbins
                                prev_addr = addr
                                prev_length = next_label.address - addr
                                after_addr = next_label.address
                                after_length = addr+length - after_addr

                                if prev_length > 0:
                                    # print the incbin
                                    output_lines.append(incbin_line(prev_addr, prev_length))
                                
                                # Print the label
                                label_addr = '{0:#010x}'.format(next_label.address).upper().replace('0X', '')
                                output_lines.append(f'gUnk_{label_addr}:: @ {label_addr}\n')

                                addr = after_addr
                                length = after_length

                                if len(labels) == 0: # Extracted all labels
                                    next_label = None
                                    break
                                next_label = labels.pop(0)
                                continue


                            if length > 0:
                                output_lines.append(incbin_line(addr, length))
                            continue
                    output_lines.append(line)

            while next_label is not None:

                # tmp: print label for script
                label_addr = '{0:#010x}'.format(next_label.address + ROM_OFFSET).upper().replace('0X', '')
                print(f'SCRIPT_START script_{label_addr}')
                print(f'at {next_label.symbol}')

                #print(f'Could not insert {next_label}')
                if len(labels) == 0: # Extracted all labels
                    next_label = None
                    break
                next_label = labels.pop(0)

            with open(asm_path, 'w') as file:
                file.writelines(output_lines)

        print('Extracting pointers')

        # Extract pointers
        for path in to_extract:
            output_lines = []
            pointers = to_extract[path]
            next_pointer = pointers.pop(0)
            with open(path, 'r') as file:
                for line in file:
                    if next_pointer is not None and line.strip().startswith('.incbin "baserom.gba"'):
                        arr = line.split(',')
                        if len(arr) == 3:
                            addr = int(arr[1], 16)
                            length = int(arr[2], 16)

                            while next_pointer.address >= addr and next_pointer.address < addr+length:
                                # Pointer is in this incbin
                                symbol = get_symbol_at(next_pointer.points_to - ROM_OFFSET)
                                offset = next_pointer.points_to - ROM_OFFSET - symbol.address
                                if offset > 1:
                                    # Missing label
                                    if len(pointers) == 0: # Extracted all pointers
                                        next_pointer = None
                                        break
                                    next_pointer = pointers.pop(0)
                                    continue

                                # Calculate new incbins
                                prev_addr = addr
                                prev_length = next_pointer.address - addr
                                after_addr = next_pointer.address + 4
                                after_length = addr+length - after_addr
                                if after_length < 0:
                                    message = f'Pointer at {hex(next_pointer.address)} crosses over from incbin at {hex(addr)}'
                                    print(path)
                                    print(after_length)
                                    print(message)
                                    self.api.show_error('Pointer Extractor', message)
                                    return

                                if prev_length > 0:
                                    # print the incbin
                                    output_lines.append(incbin_line(prev_addr, prev_length))
                                
                                # Print the pointer
                                output_lines.append(f'\t.4byte {symbol.name}\n')


                                addr = after_addr
                                length = after_length

                                if len(pointers) == 0: # Extracted all pointers
                                    next_pointer = None
                                    break
                                next_pointer = pointers.pop(0)

                            if length > 0:
                                output_lines.append(incbin_line(addr, length))
                            continue

                    output_lines.append(line)

            with open(path, 'w') as file:
                file.writelines(output_lines)
            #print(''.join(output_lines))
        self.api.show_message('Pointer Extractor', f'Done extracting pointers')

