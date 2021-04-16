from tlh.const import RomVariant
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

        pointers = get_pointer_database().get_pointers(RomVariant.USA)

        to_extract: dict[str, SortedList] = {}

        for pointer in pointers:
            found = self.incbins.at(pointer.address)
            if len(found) == 1:
                interval = found.pop()
                file = interval.data

                if not file in to_extract:
                    to_extract[file] = SortedList()

                to_extract[file].add(pointer.address)
#                print(hex(pointer.address))
                #print(found.pop())
            elif len(found) > 1:
                print(f'Found {len(found)} incbins for address {pointer.address}')
        
        #print(to_extract)
        count = 0
        for file in to_extract:
            print(f'{file}: {len(to_extract[file])}')
            count += len(to_extract[file])

        self.api.show_message('Pointer Extractor', f'{count} unextracted pointers found')
        print(count)