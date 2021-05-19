from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMessageBox
from tlh.const import RomVariant
from tlh.data.constraints import ConstraintManager, InvalidConstraintError
from tlh.plugin.api import PluginApi
from tlh.data.database import get_constraint_database

class ConstraintCleanerPlugin:
    name = 'Constraint Cleaner'
    description = 'Cleans up duplicate constraints\nand disables redundant constraints'

    def __init__(self, api: PluginApi) -> None:
        self.api = api

    def load(self) -> None:
        #self.action_remove_duplicate = self.api.register_menu_entry('Remove duplicate constraints', self.slot_remove_duplicate)
        self.action_remove_redundant = self.api.register_menu_entry('Remove redundant constraints', self.slot_remove_redundant)

    def unload(self) -> None:
        #self.api.remove_menu_entry(self.action_remove_duplicate)
        self.api.remove_menu_entry(self.action_remove_redundant)

    def slot_remove_duplicate(self) -> None:
        # TODO
        pass

    def slot_remove_redundant(self) -> None:
        '''
        Disables all constraints that only contain redundant information and don't create more relations
        '''

        progress_dialog = self.api.get_progress_dialog('Constraint Cleaner', 'Removing redundant constraints...', False)
        progress_dialog.show()

        self.thread = QThread()
        self.worker = RemoveRedundantWorker()
        self.worker.moveToThread(self.thread)

        self.worker.signal_progress.connect(lambda progress: progress_dialog.set_progress(progress))
        self.worker.signal_done.connect(lambda: ( # https://stackoverflow.com/a/13672943
            self.thread.quit(),
            progress_dialog.close(),
            QMessageBox.information(self.api.main_window, 'Constraint Cleaner', 'All redundant constraints are removed.')
        ))
        self.worker.signal_fail.connect(lambda: (
            self.thread.quit(),
            progress_dialog.close(),
            QMessageBox.critical(self.api.main_window, 'Constraint Cleaner', 'Failed to add a constraint.\nSee console for more information.')
        ))
        
        self.thread.started.connect(self.worker.process)
        self.thread.start()
        


class RemoveRedundantWorker(QObject):
    signal_progress = Signal(int)
    signal_done = Signal()
    signal_fail = Signal()
    
    def process(self) -> None:
        print('Start processing')

        progress = 0

        # Test using a constraint manager with all variations
        manager = ConstraintManager(
            {RomVariant.USA, RomVariant.JP, RomVariant.EU, RomVariant.DEMO})
        constraint_database = get_constraint_database()
        constraints = constraint_database.get_constraints()

        i = 0
        count = len(constraints)


        for constraint in constraints:
            if not constraint.enabled:
                i = i + 1
                continue

            # test if constraint is redundant
            va_a = manager.to_virtual(constraint.romA, constraint.addressA)
            va_b = manager.to_virtual(constraint.romB, constraint.addressB)
            if va_a == va_b:
                print(f'Disable {constraint}')
                constraint.enabled = False
            else:
                #print(f'Keep {constraint}')
                manager.add_constraint(constraint)
                try:
                    manager.rebuild_relations()
                except InvalidConstraintError as e:
                    print(e)
                    print(constraint)
                    self.signal_fail.emit()
                    return

        

            i = i + 1
            new_progress = (i*50) // count
            if new_progress != progress:
                progress = new_progress
                self.signal_progress.emit(new_progress)

        self.signal_progress.emit(50)

        i = 0
        # Test that there are no disabled constraints that are still needed
        for constraint in constraints:
            if constraint.enabled:
                i = i + 1
                continue

            # test if constraint is redundant
            va_a = manager.to_virtual(constraint.romA, constraint.addressA)
            va_b = manager.to_virtual(constraint.romB, constraint.addressB)
            if va_a != va_b:
                print(f'Need to reenable {constraint}')
                constraint.enabled = True
                manager.add_constraint(constraint)
                try:
                    manager.rebuild_relations()
                except InvalidConstraintError as e:
                    print(e)
                    print(constraint)
                    self.signal_fail.emit()
                    return

        

            i = i + 1
            new_progress = (i*50) // count + 50
            if new_progress != progress:
                progress = new_progress
                self.signal_progress.emit(new_progress)

        constraint_database._write_constraints() # TODO add a public method to update changed constraints in the database?
        constraint_database.constraints_changed.emit()

        self.signal_done.emit()

