from dataclasses import dataclass
import json
from typing import Any, List, Optional, Union
import PySide6
from PySide6.QtCore import QThread, Qt, QAbstractListModel, QObject, Signal
from PySide6.QtWidgets import QDockWidget, QFileDialog
from tlh.common.ui.close_dock import CloseDock
from tlh.plugin.api import PluginApi
from tlh.ui.ui_plugin_entity_explorer_bridge_dock import Ui_BridgeDock
from plugins.entity_explorer_bridge.server import ServerWorker
import requests
import tlh.settings as settings
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import threading
import os
from datetime import datetime
import subprocess

class EntityExplorerPlugin:
    name = 'Entity Explorer'
    description = 'Connects to Entity Explorer instance for\nsave state transfer'

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.dock = None

    def load(self) -> None:
        self.action_show_bridge = self.api.register_menu_entry(
            'Entity Explorer Bridge', self.slot_show_bridge)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_show_bridge)
        if self.dock is not None:
            self.dock.close()

    def slot_show_bridge(self) -> None:
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
        self.ui.toolButtonLoadFolder.clicked.connect(self.slot_edit_load_folder)
        self.ui.toolButtonSaveFolder.clicked.connect(self.slot_edit_save_folder)

        self.ui.labelConnectionStatus.setText('Server not yet running.')

        # Initially load from repo folder
        self.ui.lineEditLoadFolder.setText(settings.get_repo_location())

        self.signal_closed.connect(self.slot_close)


    def slot_close(self) -> None:
        self.slot_stop_server()

    def slot_server_running(self, running: bool) -> None:
        if running:
            self.ui.pushButtonStartServer.setVisible(False)
            self.ui.pushButtonStopServer.setVisible(True)
        else:
            self.ui.pushButtonStartServer.setVisible(True)
            self.ui.pushButtonStopServer.setVisible(False)

    def slot_start_server(self) -> None:

        if self.ui.checkBoxCopySaves.isChecked() and self.ui.lineEditSaveFolder.text().strip() == '':
            self.api.show_error('Entity Explorer Bridge', 'You need to set the folder where to store the copies.')
            return

        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.signal_connected.connect(self.slot_connected)
        self.server_worker.signal_disconnected.connect(self.slot_disconnected)
        self.server_worker.signal_error.connect(self.slot_error)
        self.server_worker.signal_started.connect(self.slot_server_started)
        self.server_worker.signal_shutdown.connect(self.slot_server_stopped)
        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.process)
        self.server_thread.start()
        self.slot_server_running(True)
        self.set_folders_active(False)

    def set_folders_active(self, active: bool) -> None:
        self.ui.lineEditLoadFolder.setEnabled(active)
        self.ui.toolButtonLoadFolder.setEnabled(active)
        self.ui.checkBoxCopySaves.setEnabled(active)
        self.ui.lineEditSaveFolder.setEnabled(active)
        self.ui.toolButtonSaveFolder.setEnabled(active)

    def slot_stop_server(self) -> None:
        # Shutdown needs to be triggered by the server thread, so send a request
        requests.get('http://localhost:10243/shutdown')
        self.set_folders_active(True)

    def slot_connected(self) -> None:
        self.ui.labelConnectionStatus.setText(
            'Connected to Entity Explorer instance.')

    def slot_disconnected(self) -> None:
        self.ui.labelConnectionStatus.setText(
            'Disconnected from Entity Explorer instance.')

    def slot_server_started(self) -> None:
        self.slot_server_running(True)
        self.ui.labelConnectionStatus.setText(
            'Server running. Please connect Entity Explorer instance.')
        self.start_watchdog()

    def slot_server_stopped(self) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.ui.labelConnectionStatus.setText('Server stopped.')
        self.stop_watchdog()

    def slot_error(self, error: str) -> None:
        self.slot_server_running(False)
        self.server_thread.terminate()
        self.api.show_error('Entity Explorer Bridge', error)

    def slot_edit_load_folder(self):
        dir = QFileDialog.getExistingDirectory(
            self, 'Folder in which the save states are stored by mGBA', self.ui.lineEditLoadFolder.text())
        print(dir)
        if dir is not None:
            self.ui.lineEditLoadFolder.setText(dir)

    def slot_edit_save_folder(self):
        dir = QFileDialog.getExistingDirectory(
            self, 'Folder in which all save states should be copied', self.ui.lineEditSaveFolder.text())
        if dir is not None:
            self.ui.lineEditSaveFolder.setText(dir)

    def start_watchdog(self):
        if self.observer is not None:
            print('Already observing')
            return
        patterns = ['*.ss0', '*.ss1', '*.ss2', '*.ss3', '*.ss4', '*.ss5', '*.ss6', '*.ss7', '*.ss8', '*.ss9', '*.State']
        ignore_patterns = None
        ignore_directories = False
        case_sensitive = True
        self.event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)
        self.event_handler.on_modified = self.on_file_modified

        path = self.ui.lineEditLoadFolder.text()
        self.observer = Observer()
        self.observer.schedule(self.event_handler, path, recursive=False)
        self.observer.start()

    def stop_watchdog(self):
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    # https://stackoverflow.com/a/66907107
    def debounce(wait_time):
        """
        Decorator that will debounce a function so that it is called after wait_time seconds
        If it is called multiple times, will wait for the last call to be debounced and run only this one.
        """

        def decorator(function):
            def debounced(*args, **kwargs):
                def call_function():
                    debounced._timer = None
                    return function(*args, **kwargs)
                # if we already have a call to the function currently waiting to be executed, reset the timer
                if debounced._timer is not None:
                    debounced._timer.cancel()

                # after wait_time, call the function provided to the decorator with its arguments
                debounced._timer = threading.Timer(wait_time, call_function)
                debounced._timer.start()

            debounced._timer = None
            return debounced

        return decorator

    @debounce(0.1)
    def on_file_modified(self, event):
        with open(event.src_path, 'rb') as file:
            bytes = file.read()
            self.server_worker.slot_send_save_state(event.src_path, bytes)


            if self.ui.checkBoxCopySaves.isChecked() and self.ui.lineEditSaveFolder.text():
                name = os.path.basename(event.src_path)
                name = datetime.now().strftime('%Y-%m-%d_%H_%M_%S_%f_') + name
                with open(os.path.join(self.ui.lineEditSaveFolder.text(), name), 'wb') as output:
                    output.write(bytes)
