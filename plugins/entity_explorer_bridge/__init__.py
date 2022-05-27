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

# PATHS for the entity search. TODO Make configurable
MGBA_PATH = '/home/octorock/git/mgba/build/qt/mgba-qt'
SAVES_PATH = '/home/octorock/save_games'
JSON_PATH = '/home/octorock/save_games_json'

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

        # Entity search
        self.ui.pushButtonSearchEntity.clicked.connect(self.slot_search_entity)
        self.ui.lineEditType.returnPressed.connect(self.slot_search_entity)
        self.ui.listViewFoundEntities.setVisible(False)
        self.ui.listViewFoundEntities.doubleClicked.connect(self.slot_start_mgba)

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


    def slot_search_entity(self) -> None:
        kinds = [3, 4, 6, 7 ,8 ,9]
        kind = kinds[self.ui.comboBoxKind.currentIndex()]
        type = 0
        try:
            type = int(self.ui.lineEditType.text(), 0)
        except ValueError:
            self.api.show_error(EntityExplorerPlugin.name, 'Need to enter a number for the entity type.')
            return

        save_games:List[SaveGame] = []

        self.progress_dialog = self.api.get_progress_dialog(EntityExplorerPlugin.name, 'Searching for entity...', True)
        self.progress_dialog.show()
        self.progress_dialog.get_abort_signal().connect(lambda : (self.worker.abort(), self.thread.quit()))

        self.thread = QThread()
        self.worker = SearchEntityWorker(kind, type)
        self.worker.moveToThread(self.thread)

        self.worker.signal_progress.connect(lambda progress: self.progress_dialog.set_progress(progress))
        self.worker.signal_done.connect(self.slot_found_entities)
        self.worker.signal_fail.connect(lambda message: (
            self.thread.quit(),
            self.progress_dialog.close(),
            self.api.show_error(EntityExplorerPlugin.name, message)
        ))

        self.thread.started.connect(self.worker.process)
        self.thread.start()

    def slot_found_entities(self) -> None:
        self.thread.quit()
        self.progress_dialog.close()
        self.save_games = self.worker.save_games
        self.ui.listViewFoundEntities.setModel(SaveGameModel(self.save_games, self))
        self.ui.listViewFoundEntities.setVisible(len(self.save_games) > 0)
        self.api.show_message(EntityExplorerPlugin.name, f'{len(self.save_games)} entities found.')


    def slot_start_mgba(self) -> None:

        elf_path = os.path.join(settings.get_repo_location(), 'tmc.elf')
        save_game = self.save_games[self.ui.listViewFoundEntities.currentIndex().row()]
        print(save_game)
        subprocess.Popen([MGBA_PATH, '-t', save_game.save_path, elf_path], cwd=os.path.dirname(MGBA_PATH))

class SearchEntityWorker(QObject):
    signal_progress = Signal(int)
    signal_done = Signal()
    signal_fail = Signal()

    def __init__(self, kind, id):
        super().__init__()
        self.kind = kind
        self.id = id
        self.is_aborted = False

    def process(self) -> None:
        try:

            self.save_games: List[SaveGame] = []
            print(f'Searching for kind {self.kind} id {self.id}')

            json_files = []

            for root, dirs, files in os.walk(JSON_PATH):
                for file in files:
                    file_path = os.path.join(root, file)
                    json_files.append((file,file_path))

            count = len(json_files)
            i = 0
            progress = 0
            for (file, file_path) in json_files:
                if self.is_aborted:
                    return
                data = json.load(open(file_path, 'r'))
                times = 0
                for list in data:
                    for entity in list:
                        if self.kind == 9: # Manager
                            if 'subtype' in entity and entity['type'] == 9 and entity['subtype'] == self.id:
                                times += 1
                        else:
                            if 'kind' in entity and entity['kind'] == self.kind and entity['id'] == self.id:
                                times += 1

                if times > 0:
                    save_path = file_path.replace('save_games_json', 'save_games').replace('.json', '.ss1')
                    name = os.path.join(os.path.basename(os.path.dirname(file_path)), file.replace('.json', '')) + ' ' + str(times)
                    self.save_games.append(SaveGame(name, save_path, times))
                i += 1
                new_progress = (i*100) // count
                if new_progress != progress:
                    progress = new_progress
                    self.signal_progress.emit(new_progress)

            self.save_games.sort(key = lambda x:x.name)
            self.signal_done.emit()
        except Exception as e:
            print(e)
            self.signal_fail.emit('Caught exception')

    def abort(self):
        self.is_aborted = True

@dataclass
class SaveGame:
    name: str
    save_path: str
    times: int

class SaveGameModel(QAbstractListModel):
    def __init__(self, save_games: List[SaveGame], parent: Optional[PySide6.QtCore.QObject] = ...) -> None:
        super().__init__(parent)
        self.save_games = save_games

    def rowCount(self, parent: Union[PySide6.QtCore.QModelIndex, PySide6.QtCore.QPersistentModelIndex] = ...) -> int:
        return len(self.save_games)

    def data(self, index: Union[PySide6.QtCore.QModelIndex, PySide6.QtCore.QPersistentModelIndex], role: int = ...) -> Any:
        if role == Qt.DisplayRole:
            return self.save_games[index.row()].name
        return None