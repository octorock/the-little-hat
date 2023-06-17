from tlh.hexviewer.diff_calculator import LinkedDiffCalculator
from PySide6.QtCore import QObject, QThread, Signal
from tlh.const import ROM_SIZE
from tlh.plugin.api import PluginApi

class CountDiffBytesPlugin:
    name = 'Count Diff Bytes'
    description = 'Count the bytes that are different between the\nlinked hex viewers'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_count_diff = self.api.register_menu_entry('Count diff bytes', self.slot_count_diff)
    
    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_count_diff)

    def slot_count_diff(self) -> None:
        # TODO do as worker and show progress bar

        progress_dialog = self.api.get_progress_dialog(self.name, 'Counting diff bytes...', False)
        progress_dialog.show()



        diff_calculator = self.api.get_linked_diff_calculator()

        self.thread = QThread()
        self.worker = CountDiffWorker(diff_calculator)
        self.worker.moveToThread(self.thread)

        self.worker.signal_progress.connect(lambda progress: progress_dialog.set_progress(progress))
        self.worker.signal_done.connect(lambda count: (
            self.thread.quit(),
            progress_dialog.close(),
            self.api.show_message(self.name, f'There are {count} bytes differing between the linked hex views.')
        ))

        self.thread.started.connect(self.worker.process)
        self.thread.start()
        

class CountDiffWorker(QObject):
    signal_progress = Signal(int)
    signal_done = Signal(int)

    diff_calculator: LinkedDiffCalculator

    def __init__(self, diff_calculator) -> None:
        super().__init__()
        self.diff_calculator = diff_calculator
    
    def process(self) -> None:
        progress = 0

        # TODO actually calculate the virtual address for the last used byte in all linked roms
        count = 0
        for i in range(0, ROM_SIZE):
            if self.diff_calculator.is_diffing(i):
                count += 1
            new_progress = (i*100) // ROM_SIZE
            if new_progress != progress:
                progress = new_progress
                self.signal_progress.emit(new_progress)

        print(count)
        self.signal_done.emit(count)