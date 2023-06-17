from dataclasses import dataclass
from typing import List
from tlh.const import ROM_OFFSET, RomVariant
from tlh.plugin.api import PluginApi
from tlh.data.database import get_pointer_database, get_symbol_database


@dataclass
class Edge:
    from_symbol: str
    from_offset: int
    to_symbol: str
    to_offset: int


rom_variant = RomVariant.USA


class FunctionCallGraphPlugin:
    name = 'Function Call Graph'
    description = 'Calculate a graph of which functions call which\nother functions'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_call_graph = self.api.register_menu_entry(
            'Calculate call graph', self.slot_call_graph)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_call_graph)

    def slot_call_graph(self) -> None:

        symbol_database = get_symbol_database()

        pointers = get_pointer_database().get_pointers(rom_variant)
        if not symbol_database.are_symbols_loaded(rom_variant):
            self.api.show_error(
                self.name, f'Symbols for {rom_variant} rom are not loaded')
            return

        symbols = symbol_database.get_symbols(rom_variant)

        nodes = set()
        edges: List[Edge] = []

        for pointer in pointers.get_sorted_pointers():
            symbol_from = symbols.get_symbol_at(pointer.address)
            symbol_to = symbols.get_symbol_at(pointer.points_to-ROM_OFFSET)
            offset_from = pointer.address - symbol_from.address
            offset_to = pointer.points_to-ROM_OFFSET - symbol_to.address

            nodes.add(symbol_from.name)
            nodes.add(symbol_to.name)

            edges.append(Edge(symbol_from.name, offset_from,
                         symbol_to.name, offset_to))

        # Print graph
        with open('tmp/call_graph.gml', 'w') as f:
            f.write('graph [\n')
            f.write('directed 1\n')

            nodes_with_order = list(nodes)

            for i, node in enumerate(nodes_with_order):
                f.write('node [\n')
                f.write(f'id {i}\n')
                f.write(f'label "{node}"\n')
                f.write(']\n')

            for edge in edges:
                f.write('edge [\n')
                f.write(f'source {nodes_with_order.index(edge.from_symbol)}\n')
                f.write(f'target {nodes_with_order.index(edge.to_symbol)}\n')
                f.write(
                    f'label "{edge.from_symbol} +{edge.from_offset} -> {edge.to_symbol} +{edge.to_offset}"\n')
                f.write(']\n')

            f.write(']\n')
