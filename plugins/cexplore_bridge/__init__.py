from PySide6.QtGui import QClipboard
from plugins.cexplore_bridge.code import get_code, split_code, store_code
from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QDockWidget
from tlh.plugin.api import PluginApi
from tlh.ui.ui_plugin_cexplore_bridge_dock import Ui_BridgeDock
from plugins.cexplore_bridge.server import ServerWorker
import requests
from tlh.ui.ui_plugin_cexplore_bridge_received_code_dialog import Ui_ReceivedCodeDialog


class CExploreBridgePlugin:
    name = 'CExplore Bridge'
    description = 'Connects to CExplore instance for simple transfer of source code'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_show_bridge = self.api.register_menu_entry(
            'CExplore Bridge', self.slot_show_bridge)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_bridge)

    def slot_show_bridge(self) -> None:
        dock = BridgeDock(self.api.main_window, self.api)
        self.api.main_window.addDockWidget(Qt.LeftDockWidgetArea, dock)


class BridgeDock(QDockWidget):

    def __init__(self, parent, api: PluginApi) -> None:
        super().__init__('', parent)
        self.api = api
        self.ui = Ui_BridgeDock()
        self.ui.setupUi(self)

        self.slot_server_running(False)

        self.ui.pushButtonStartServer.clicked.connect(self.slot_start_server)
        self.ui.pushButtonStopServer.clicked.connect(self.slot_stop_server)
        self.ui.pushButtonUpload.clicked.connect(self.slot_upload_function)
        self.ui.pushButtonDownload.clicked.connect(self.slot_download_function)
        self.ui.pushButtonCopyJs.clicked.connect(self.slot_copy_js_code)

        self.enable_function_group(False)
        self.ui.labelConnectionStatus.setText('Server not yet running.')

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
        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.process)
        self.server_thread.start()
        self.slot_server_running(True)

    def enable_function_group(self, enabled: bool) -> None:
        self.ui.lineEditFunctionName.setEnabled(enabled)
        self.ui.pushButtonUpload.setEnabled(enabled)
        self.ui.pushButtonDownload.setEnabled(enabled)

    def slot_stop_server(self) -> None:
        # Shutdown needs to be triggered by the server thread, so send a request
        requests.get('http://localhost:10241/shutdown')

    def slot_upload_function(self) -> None:
        (err, asm, src) = get_code(self.ui.lineEditFunctionName.text())
        if err:
            self.api.show_error('CExplore Bridge', asm)
            return

        self.server_worker.slot_send_asm_code(asm)
        self.server_worker.slot_send_c_code(src)
        self.api.show_message(
            'CExplore Bridge', f'Uploaded code of {self.ui.lineEditFunctionName.text()}.')

    def slot_download_function(self) -> None:
        self.enable_function_group(False)
        self.server_worker.slot_request_c_code()

    def slot_received_c_code(self, code: str) -> None:

        self.enable_function_group(True)
        (header, src) = split_code(code)
        dialog = ReceivedDialog(self)
        dialog.signal_matching.connect(self.slot_store_matching)
        dialog.signal_nonmatching.connect(self.slot_store_nonmatching)
        dialog.show_code(header, src)

    def slot_store_matching(self, header: str, code: str) -> None:
        self.store(header, code, True)

    def slot_store_nonmatching(self, header: str, code: str) -> None:
        self.store(header, code, False)

    def store(self, header: str, code: str, matching: bool) -> None:
        (err, msg) = store_code(
            self.ui.lineEditFunctionName.text(), header, code, matching)
        if err:
            self.api.show_error('CExplore Bridge', msg)
            return
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
            'Server running. Place connect CExplore instance.')

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


class ReceivedDialog(QDialog):
    signal_matching = Signal(str, str)
    signal_nonmatching = Signal(str, str)

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.ui = Ui_ReceivedCodeDialog()
        self.ui.setupUi(self)
        self.ui.buttonBox.button(QDialogButtonBox.Yes).clicked.connect(lambda: self.signal_matching.emit(
            self.ui.plainTextEditHeaders.toPlainText(), self.ui.plainTextEditCode.toPlainText()))
        self.ui.buttonBox.button(QDialogButtonBox.No).clicked.connect(lambda: self.signal_nonmatching.emit(
            self.ui.plainTextEditHeaders.toPlainText(), self.ui.plainTextEditCode.toPlainText()))

    def show_code(self, header: str, code: str) -> None:
        self.ui.plainTextEditHeaders.setPlainText(header)
        self.ui.plainTextEditCode.setPlainText(code)
        self.show()
