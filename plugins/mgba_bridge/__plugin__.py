from PySide6.QtCore import QThread, Qt
from plugins.mgba_bridge.script_disassembler.script_disassembler import disassemble_script
from plugins.mgba_bridge.server import ServerWorker
from tlh import settings
from tlh.common.ui.close_dock import CloseDock
from tlh.const import ROM_OFFSET, RomVariant
from tlh.plugin.api import PluginApi
from tlh.data.database import get_symbol_database
from tlh.data.rom import get_rom
import os
from tlh.ui.ui_plugin_mgba_bridge_dock import Ui_BridgeDock
import requests


class MGBABridgePlugin:
    name = 'mGBA Bridge'
    description = 'Connect to mGBA'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.dock = None

    def load(self) -> None:
        self.action_show_bridge = self.api.register_menu_entry(
            'mGBA Bridge', self.slot_show_bridge)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_bridge)
        if self.dock is not None:
            self.dock.close()

    def slot_show_bridge(self) -> None:
        if get_symbol_database().get_symbols(RomVariant.CUSTOM) is None:
            self.api.show_error(self.name, 'Symbols for CUSTOM variant need to be loaded for mGBA bridge to work.')
            return
        self.dock = BridgeDock(self.api.main_window, self.api)
        self.api.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.dock)


class BridgeDock(CloseDock):

    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_BridgeDock()
        self.ui.setupUi(self)
        self.server_thread = None

        self.observer = None
        self.modified_timer = None
        self.slot_server_running(False)

        self.ui.pushButtonStartServer.clicked.connect(self.slot_start_server)
        self.ui.pushButtonStopServer.clicked.connect(self.slot_stop_server)

        self.ui.labelConnectionStatus.setText('Server not yet running.')

        self.signal_closed.connect(self.slot_closed)

    def slot_closed(self) -> None:
        self.slot_stop_server()

    def slot_server_running(self, running: bool) -> None:
        if running:
            self.ui.pushButtonStartServer.setVisible(False)
            self.ui.pushButtonStopServer.setVisible(True)
        else:
            self.ui.pushButtonStartServer.setVisible(True)
            self.ui.pushButtonStopServer.setVisible(False)

    def slot_start_server(self) -> None:
        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.signal_connected.connect(self.slot_connected)
        self.server_worker.signal_error.connect(self.slot_error)
        self.server_worker.signal_started.connect(self.slot_server_started)
        self.server_worker.signal_shutdown.connect(self.slot_server_stopped)
        self.server_worker.signal_script_addr.connect(self.slot_script_addr)
        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.process)
        self.server_thread.start()
        self.slot_server_running(True)

    def slot_stop_server(self) -> None:
        # Shutdown needs to be triggered by the server thread, so send a request
        requests.get('http://localhost:10244/shutdown')

    def slot_connected(self) -> None:
        self.ui.labelConnectionStatus.setText(
            'Connected to mGBA instance.')

    def slot_server_started(self) -> None:
        self.slot_server_running(True)
        self.ui.labelConnectionStatus.setText(
            'Server running. Please connect mGBA instance.')

    def slot_server_stopped(self) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.ui.labelConnectionStatus.setText('Server stopped.')

    def slot_error(self, error: str) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.api.show_error('mGBA Bridge', error)

    def slot_script_addr(self, addr: int) -> None:
        print('ADDR: ', addr)

        if addr == 0:
            self.ui.labelCode.setText('No script executed in current context.')
            return
        rom = get_rom(RomVariant.CUSTOM)

        # receive the current instruction pointer
        #instruction_pointer = 0x8009b70
        #instruction_pointer = 0x8009d42
        instruction_pointer = addr
        symbols = get_symbol_database().get_symbols(
            RomVariant.CUSTOM)  # Symbols for our custom USA rom
        symbol = symbols.get_symbol_at(instruction_pointer-ROM_OFFSET)
        script_name = symbol.name
        script_offset = instruction_pointer-ROM_OFFSET - symbol.address

        # Find file containing the script
        # TODO or statically find all script files?
        script_file = None
        for root, dirs, files in os.walk(os.path.join(settings.get_repo_location(), 'data', 'scripts')):
            if script_name + '.inc' in files:
                script_file = os.path.join(root, script_name + '.inc')
                break
            # TODO search the file contents for the script
            for file in files:
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    if 'SCRIPT_START ' + script_name in f.read():
                        script_file = path

        if script_file is None:
            self.ui.labelCode.setText(
                f'ERROR: Count not find script file containing {script_name}')
            return

        self.ui.labelScriptName.setText(script_file)

        script_lines = []
        with open(script_file, 'r') as file:
            script_lines = file.read().split('\n')

        # print(script_lines)
        # TODO for testing ifdefs: script_0800B200
        # print('test')
        # print(symbol)
        # print(script_offset)

        # TODO only disassemble the number of bytes, the actual instructions are not interesting as they are read from the source file.
        (_, instructions) = disassemble_script(rom.get_bytes(
            symbol.address, symbol.address+symbol.length), symbol.address)

        output = ''
        current_instruction = 0
        in_correct_script = False

        ifdef_stack = [True]

        for line in script_lines:
            stripped = line.strip()
            if stripped.startswith('SCRIPT_START'):
                in_correct_script = stripped == 'SCRIPT_START ' + script_name
                output += f'{line}\n'
                continue
            if not in_correct_script or stripped.startswith('@') or stripped.endswith(':'):
                output += f'{line}\n'
                continue

            if '.ifdef' in stripped:
                if not ifdef_stack[-1]:
                    ifdef_stack.append(False)
                    output += f'{line}\n'
                    continue
                # TODO check variant
                is_usa = stripped.split(' ')[1] == 'USA'
                ifdef_stack.append(is_usa)
                output += f'{line}\n'
                continue
            if '.ifndef' in stripped:
                if not ifdef_stack[-1]:
                    ifdef_stack.append(False)
                    output += f'{line}\n'
                    continue
                is_usa = stripped.split(' ')[1] == 'USA'
                ifdef_stack.append(not is_usa)
                output += f'{line}\n'
                continue
            if '.else' in stripped:
                if ifdef_stack[-2]:
                    # If the outermost ifdef is not true, this else does not change the validiness of this ifdef
                    ifdef_stack[-1] = not ifdef_stack[-1]
                output += f'{line}\n'
                continue
            if '.endif' in stripped:
                ifdef_stack.pop()
                output += f'{line}\n'
                continue

            if not ifdef_stack[-1]:
                # Not defined for this variant
                output += f'{line}\n'
                continue

            if current_instruction >= len(instructions):
                # TODO maybe even not print additional lines?
                output += f'{line}\n'
                continue
            addr = instructions[current_instruction].addr
            prefix = ''
            if addr == script_offset:
                prefix = '>'
            output += f'{addr:03d}| {prefix}{line}\t\n'
            current_instruction += 1
            if stripped.startswith('SCRIPT_END'):
                break
        self.ui.labelCode.setText(output)
