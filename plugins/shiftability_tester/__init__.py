from tlh import settings
from tlh.const import RomVariant
from tlh.data.rom import Rom, get_rom
from PySide6.QtCore import QObject, QThread, Signal
from tlh.plugin.api import PluginApi
from os import path
from tlh.data.database import get_pointer_database

class ShiftabilityTesterPlugin:
    name = 'Shiftability Tester'
    description = 'Tests whether a rom with .space inside it was\nshifted correctly.'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        self.action_test_shiftability = self.api.register_menu_entry('Test Shiftability', self.slot_test_shiftability)

    def unload(self) -> None:
        self.api.remove_menu_entry(self.action_test_shiftability)

    def slot_test_shiftability(self) -> None:
        progress_dialog = self.api.get_progress_dialog('Shiftability Tester', 'Testing shiftability...', False)
        progress_dialog.show()
        
        self.thread = QThread()
        self.worker = TestShiftabilityWorker()
        self.worker.moveToThread(self.thread)

        self.worker.signal_progress.connect(lambda progress: progress_dialog.set_progress(progress))
        self.worker.signal_done.connect(lambda: ( 
            self.thread.quit(),
            progress_dialog.close(),
            self.api.show_message('Shiftability Tester', 'Test complete. See console for more information.')
        ))
        self.worker.signal_fail.connect(lambda message: (
            self.thread.quit(),
            progress_dialog.close(),
            self.api.show_error('Shiftability Tester', message)
        ))
        
        self.thread.started.connect(self.worker.process)
        self.thread.start()

class TestShiftabilityWorker(QObject):
    signal_progress = Signal(int)
    signal_done = Signal()
    signal_fail = Signal(str)

    def process(self) -> None:
        try:
            print('start')
            # Load shifted rom
            rom_original = get_rom(RomVariant.USA)
            print('Load shifted')
            rom_path = path.join(settings.get_repo_location(), 'tmc.gba')
            print(rom_path)
            if not path.isfile(rom_path):
                self.signal_fail.emit(f'Shifted rom expected at {rom_path}')
                return
            self.signal_progress.emit(10)            
            rom_shifted = Rom(rom_path)
            print('Shifted rom loaded')


            pointerlist = get_pointer_database().get_pointers(RomVariant.USA)

            END_OF_USED_DATA = 0xde7da4

            errors = []

            shift_location = 0x108
            shift_length = 0x10000

            progress = 0
            for i in range(END_OF_USED_DATA):
                orig = rom_original.get_byte(i)
                shifted_i = i
                if i >= shift_location:
                    #print('SHIFT')
                    shifted_i += shift_length
                #print(i, shifted_i)
                shifted = rom_shifted.get_byte(shifted_i)

                if orig != shifted:
                    pointers = pointerlist.get_pointers_at(i)

                    # Test if pointer
                    if len(pointers) > 0:
                        # TODO parse the full pointer
                        continue
                    
                    print(f'{hex(i-2)}\t{orig}\t{shifted}')
                    errors.append((i, orig, shifted))
                    #self.signal_fail.emit(f'Failed at {hex(i)}: {orig} {shifted}')
                    #break
                else:
                    pass
                    #if len(pointers) > 0:
                        # TODO test that pointer was shifted
                        #pass

                new_progress = i * 100 // END_OF_USED_DATA
                if new_progress != progress:
                    progress = new_progress
                    self.signal_progress.emit(new_progress)



            if len(errors) == 0:
                self.signal_done.emit()
            else:
                self.signal_fail.emit(f'{len(errors)} errors found.')
        except Exception as e:
            print(e)
            self.signal_fail.emit('Caught exception')