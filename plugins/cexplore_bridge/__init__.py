import traceback

from PySide6.QtGui import QKeySequence
from plugins.cexplore_bridge.ghidra import improve_decompilation
from plugins.cexplore_bridge.code import find_globals, get_code, split_code, store_code
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QDockWidget
from plugins.cexplore_bridge.link import generate_cexplore_url
from tlh.const import RomVariant
from tlh.data.database import get_symbol_database
from tlh.data.rom import get_rom
from tlh.plugin.api import PluginApi
from tlh.plugin.loader import get_plugin
from tlh.ui.ui_plugin_cexplore_bridge_dock import Ui_BridgeDock
from plugins.cexplore_bridge.server import ServerWorker
import requests
from tlh.ui.ui_plugin_cexplore_bridge_received_code_dialog import Ui_ReceivedCodeDialog
import os
import re
from tlh import settings

# Set this to true if you know what you are doing and want to skip all confirm dialogs and confirmation messages
NO_CONFIRMS = False
# Menu entries to created NONMATCH lists
CREATE_LISTS = False

class CExploreBridgePlugin:
    name = 'CExplore Bridge'
    description = 'Connects to CExplore instance for simple transfer\nof source code'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.dock = None

    def load(self) -> None:
        self.action_show_bridge = self.api.register_menu_entry(
            'CExplorex Bridge', self.slot_show_bridge)
        if CREATE_LISTS:
            self.action_find_nonmatching = self.api.register_menu_entry('List NONMATCH', self.slot_find_nonmatching)
            self.action_find_nonmatching.setShortcut(QKeySequence("Ctrl+F3"))
            self.action_find_asmfunc = self.api.register_menu_entry('List ASM_FUNC', self.slot_find_asmfunc)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_bridge)
        if CREATE_LISTS:
            self.api.remove_menu_entry(self.action_find_nonmatching)
            self.api.remove_menu_entry(self.action_find_asmfunc)
        if self.dock is not None:
            self.dock.close()

    def slot_show_bridge(self) -> None:
        self.dock = BridgeDock(self.api.main_window, self.api)

        self.api.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.dock)


    def slot_find_nonmatching(self) -> None:
        symbols = get_symbol_database().get_symbols(RomVariant.CUSTOM) # Symbols for our custom USA rom
        nonmatch = self.collect_non_matching_funcs()
        with open('tmp/nonmatching.html', 'w') as out:
            out.write('<link rel="stylesheet" href="theme.css" /><script src="sortable.min.js"></script><table class="sortable-theme-slick" data-sortable><thead><tr><th>File</th><th>Function</th><th>Size</th><th data-sortable="false"></th></thead><tbody>\n')
            for (file, func) in nonmatch:
                symbol = symbols.find_symbol_by_name(func)
                size = 0
                if symbol is None:
                    print(f'No symbol found for {func}, maybe static?')
                    return
                else:
                    size = symbol.length

                (err, asm, src, signature) = get_code(func, True)
                if err:
                    self.api.show_error(self.name, asm)
                    return
                url = generate_cexplore_url(src, asm)
                out.write(f'<tr><td>{file}</td><td>{func}</td><td>{size}</td><td><a href="{url}">CExplore</a></td></tr>\n')
            out.write('</tbody></table>\n')
        self.api.show_message(self.name, 'Wrote to tmp/nonmatching.html')

    def slot_find_asmfunc(self) -> None:
        symbols = get_symbol_database().get_symbols(RomVariant.CUSTOM) # Symbols for our custom USA rom
        nonmatch = self.collect_asm_funcs()
        with open('tmp/asm_funcs.html', 'w') as out:
            out.write('<link rel="stylesheet" href="theme.css" /><script src="sortable.min.js"></script><table class="sortable-theme-slick" data-sortable><thead><tr><th>File</th><th>Function</th><th>Size</th></thead><tbody>')
            for (file, func) in nonmatch:
                symbol = symbols.find_symbol_by_name(func)
                size = 0
                if symbol is None:
                    print(f'No symbol found for {func}, maybe static?')
                    size = '?'
                else:
                    size = symbol.length
                out.write(f'<tr><td>{file}</td><td>{func}</td><td>{size}</td></tr>')
            out.write('</tbody></table>')
        self.api.show_message(self.name, 'Wrote to tmp/asm_funcs.html')

    def collect_non_matching_funcs(self):
        result = []
        src_folder = os.path.join(settings.get_repo_location(), 'src')
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.endswith('.c'):
                    with open(os.path.join(root, file), 'r') as f:
                        data = f.read()
                        # Find all NONMATCH macros
                        for match in re.findall(r'NONMATCH\(".*",(?: static)?\W*\w*\W*(\w*).*\)', data):
                            result.append((os.path.relpath(os.path.join(root,file), src_folder), match))
        return result

    def collect_asm_funcs(self):
        result = []
        src_folder = os.path.join(settings.get_repo_location(), 'src')
        for root, dirs, files in os.walk(src_folder):
            for file in files:
                if file.endswith('.c'):
                    with open(os.path.join(root, file), 'r') as f:
                        data = f.read()
                        # Find all ASM_FUNC macros
                        for match in re.findall(r'ASM_FUNC\(".*",(?: static)?\W*\w*\W*(\w*).*\)', data):
                            result.append((os.path.relpath(os.path.join(root,file), src_folder), match))
        return result

class BridgeDock(QDockWidget):

    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_BridgeDock()
        self.ui.setupUi(self)
        self.server_thread = None

        self.symbols = None
        self.rom = None
        self.data_extractor_plugin = None

        self.slot_server_running(False)

        self.ui.pushButtonStartServer.clicked.connect(self.slot_start_server)
        self.ui.pushButtonStopServer.clicked.connect(self.slot_stop_server)
        self.ui.pushButtonUpload.clicked.connect(self.slot_upload_function)
        self.ui.pushButtonDownload.clicked.connect(self.slot_download_function)
        self.ui.pushButtonCopyJs.clicked.connect(self.slot_copy_js_code)
        self.ui.pushButtonGoTo.clicked.connect(self.slot_goto)
        self.ui.pushButtonDecompile.clicked.connect(self.slot_decompile)
        self.ui.pushButtonGlobalTypes.clicked.connect(self.slot_global_types)
        self.ui.pushButtonUploadAndDecompile.clicked.connect(self.slot_upload_and_decompile)

        self.enable_function_group(False)
        self.ui.labelConnectionStatus.setText('Server not yet running.')
        self.visibilityChanged.connect(self.slot_close)

    def slot_close(self, visibility: bool) -> None:
        # TODO temporarily disable until a good way to detect dock closing is found
        pass
        #if not visibility and self.server_thread is not None:
        #    self.slot_stop_server()

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
        self.server_worker.signal_disconnected.connect(self.slot_disconnected)
        self.server_worker.signal_error.connect(self.slot_error)
        self.server_worker.signal_c_code.connect(self.slot_received_c_code)
        self.server_worker.signal_started.connect(self.slot_server_started)
        self.server_worker.signal_shutdown.connect(self.slot_server_stopped)
        self.server_worker.signal_extract_data.connect(self.slot_extract_data)
        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.process)
        self.server_thread.start()
        self.slot_server_running(True)

    def enable_function_group(self, enabled: bool) -> None:
        self.ui.lineEditFunctionName.setEnabled(enabled)
        self.ui.pushButtonUpload.setEnabled(enabled)
        self.ui.pushButtonDownload.setEnabled(enabled)
        self.ui.pushButtonGoTo.setEnabled(enabled)
        self.ui.pushButtonDecompile.setEnabled(enabled)
        self.ui.pushButtonUploadAndDecompile.setEnabled(enabled)

    def slot_stop_server(self) -> None:
        # Shutdown needs to be triggered by the server thread, so send a request
        requests.get('http://localhost:10241/shutdown')

    def slot_upload_function(self) -> None:
        self.upload_function(True)

    # Returns true if the user accepted the uploading
    def upload_function(self, include_function: bool) -> bool:
        # TODO try catch all of the slots?
        (err, asm, src, signature) = get_code(self.ui.lineEditFunctionName.text(), include_function)
        if err:
            self.api.show_error('CExplore Bridge', asm)
            return

        if NO_CONFIRMS:
            # For pros also directly go to the function in Ghidra and apply the signature
            self.slot_goto()
            self.apply_function_type(self.ui.lineEditFunctionName.text(), signature)

        if NO_CONFIRMS or self.api.show_question('CExplore Bridge', f'Replace code in CExplore with {self.ui.lineEditFunctionName.text()}?'):
            self.server_worker.slot_send_asm_code(asm)
            self.server_worker.slot_send_c_code(src)
            if not NO_CONFIRMS:
                self.api.show_message(
                    'CExplore Bridge', f'Uploaded code of {self.ui.lineEditFunctionName.text()}.')
            return True
        return False

    def slot_download_function(self) -> None:
        self.enable_function_group(False)
        self.server_worker.slot_request_c_code()

    def slot_received_c_code(self, code: str) -> None:

        self.enable_function_group(True)
        (includes, header, src) = split_code(code)
        dialog = ReceivedDialog(self)
        dialog.signal_matching.connect(self.slot_store_matching)
        dialog.signal_nonmatching.connect(self.slot_store_nonmatching)
        dialog.show_code(includes, header, src)

    def slot_store_matching(self, includes: str, header: str, code: str) -> None:
        self.store(includes, header, code, True)

    def slot_store_nonmatching(self, includes: str,header: str, code: str) -> None:
        self.store(includes, header, code, False)

    def store(self, includes: str,header: str, code: str, matching: bool) -> None:
        (err, msg) = store_code(
            self.ui.lineEditFunctionName.text(), includes, header, code, matching)
        if err:
            self.api.show_error('CExplore Bridge', msg)
            return
        if not NO_CONFIRMS:
            self.api.show_message(
                'CExplore Bridge', f'Sucessfully replaced code of {self.ui.lineEditFunctionName.text()}.')

    def slot_copy_js_code(self) -> None:
        QApplication.clipboard().setText(
            'javascript:var script = document.createElement("script");script.src = "http://localhost:10241/static/bridge.js";document.body.appendChild(script);')
        self.api.show_message(
            'CExplore Bridge', 'Copied JS code to clipboard.\nPaste it as the url to a bookmark.\nThen go open the CExplore instance and click on the bookmark to connect.')

    def slot_connected(self) -> None:
        self.ui.labelConnectionStatus.setText(
            'Connected to CExplore instance.')
        self.enable_function_group(True)
        self.ui.pushButtonCopyJs.setVisible(False)

    def slot_disconnected(self) -> None:
        self.ui.labelConnectionStatus.setText(
            'Disconnected from CExplore instance.')
        self.enable_function_group(False)

    def slot_server_started(self) -> None:
        self.slot_server_running(True)
        self.ui.labelConnectionStatus.setText(
            'Server running. Please connect CExplore instance.')

    def slot_server_stopped(self) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.enable_function_group(False)
        self.ui.pushButtonCopyJs.setVisible(True)
        self.ui.labelConnectionStatus.setText('Server stopped.')

    def slot_error(self, error: str) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.enable_function_group(False)
        self.ui.pushButtonCopyJs.setVisible(True)
        self.api.show_error('CExplore Bridge', error)

    def slot_goto(self) -> None:
        try:
            r = requests.get('http://localhost:10242/goto/' + self.ui.lineEditFunctionName.text())
            if r.status_code != 200:
                self.api.show_error('CExplore Bridge', r.text)
                return
        except requests.exceptions.RequestException as e:
            self.api.show_error('CExplore Bridge', 'Could not reach Ghidra server. Did you start the script?')

    def slot_decompile(self) -> None:
        try:
            r = requests.get('http://localhost:10242/decompile/' + self.ui.lineEditFunctionName.text())
            if r.status_code != 200:
                self.api.show_error('CExplore Bridge', r.text)
                return
            result = r.text
            code = improve_decompilation(result)
            self.server_worker.slot_add_c_code(code)
        except requests.exceptions.RequestException as e:
            self.api.show_error('CExplore Bridge', 'Could not reach Ghidra server. Did you start the script?')

    def slot_upload_and_decompile(self) -> None:
        # Upload, but don't include the function.
        if self.upload_function(False):
            # Now add the decompiled function.
            self.slot_decompile()

    def slot_global_types(self) -> None:
        globals = find_globals()
        success = True
        for (type, name) in globals:
            if not self.apply_global_type(name, type):
                success = False
                break
        if success:
            self.api.show_message('CExplore Bridge', 'Applied all global types.')

    def apply_global_type(self, name: str, type: str) -> bool:
        try:
            print('http://localhost:10242/globalType/' + name + '/' + type)
            r = requests.get('http://localhost:10242/globalType/' + name + '/' + type)
            if r.status_code != 200:
                self.api.show_error('CExplore Bridge', r.text)
                return False
            return True
        except requests.exceptions.RequestException as e:
            self.api.show_error('CExplore Bridge', 'Could not reach Ghidra server. Did you start the script?')
            return False

    def apply_function_type(self, name: str, signature: str) -> bool:
        try:
            r = requests.get('http://localhost:10242/functionType/' + name + '/' + signature)
            if r.status_code != 200:
                self.api.show_error('CExplore Bridge', r.text)
                return False
            return True
        except requests.exceptions.RequestException as e:
            self.api.show_error('CExplore Bridge', 'Could not reach Ghidra server. Did you start the script?')
            return False

    def slot_extract_data(self, text: str) -> None:
        if self.symbols is None:
            # First need to load symbols
            self.symbols = get_symbol_database().get_symbols(RomVariant.CUSTOM)
            if self.symbols is None:
                self.server_worker.slot_extracted_data({'status': 'error', 'text': 'No symbols for rom CUSTOM loaded'})
                return

        if self.data_extractor_plugin is None:
            self.data_extractor_plugin = get_plugin('data_extractor', 'DataExtractorPlugin')
            if self.data_extractor_plugin is None:
                self.server_worker.slot_extracted_data({'status': 'error', 'text': 'Data Extractor plugin not loaded'})
                return

        if self.rom is None:
            self.rom = get_rom(RomVariant.CUSTOM)
            if self.rom is None:
                self.server_worker.slot_extracted_data({'status': 'error', 'text': 'CUSTOM rom could not be loaded'})
                return

        try:
            result = self.data_extractor_plugin.instance.extract_data(text, self.symbols, self.rom)
            if result is not None:
                self.server_worker.slot_extracted_data({'status': 'ok', 'text': result})
        except Exception as e:
            traceback.print_exc()
            self.server_worker.slot_extracted_data({'status': 'error', 'text': str(e)}) 


class ReceivedDialog(QDialog):
    signal_matching = Signal(str, str, str)
    signal_nonmatching = Signal(str, str, str)

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.ui = Ui_ReceivedCodeDialog()
        self.ui.setupUi(self)
        self.ui.buttonBox.button(QDialogButtonBox.Yes).clicked.connect(lambda: self.signal_matching.emit(
            self.ui.plainTextEditIncludes.toPlainText(),
            self.ui.plainTextEditHeaders.toPlainText(),
            self.ui.plainTextEditCode.toPlainText()))
        self.ui.buttonBox.button(QDialogButtonBox.No).clicked.connect(lambda: self.signal_nonmatching.emit(
            self.ui.plainTextEditIncludes.toPlainText(),
            self.ui.plainTextEditHeaders.toPlainText(),
            self.ui.plainTextEditCode.toPlainText()))

    def show_code(self, includes: str, header: str, code: str) -> None:
        self.ui.plainTextEditIncludes.setPlainText(includes)
        self.ui.plainTextEditHeaders.setPlainText(header)
        self.ui.plainTextEditCode.setPlainText(code)
        self.show()
