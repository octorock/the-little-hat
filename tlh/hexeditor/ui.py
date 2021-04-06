# Inspired by https://github.com/PetterS/sexton
# Paint custom widget https://blog.rburchell.com/2010/02/pyside-tutorial-custom-widget-painting.html

from tlh.hexeditor.edit_annotation_dialog import EditAnnotationDialog
from tlh.data.annotations import Annotation
from tlh.data.database import get_annotation_database, get_pointer_database
from tlh import settings
from tlh.data.pointer import Pointer
from tlh.hexeditor.edit_pointer_dialog import EditPointerDialog
import PySide6
from tlh.hexeditor.manager import HexEditorInstance
from tlh.const import ROM_OFFSET
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QKeySequence, QPainter, QPen, QResizeEvent, QShortcut
from PySide6.QtWidgets import QApplication, QInputDialog, QLabel, QMenu, QMessageBox, QScrollBar, QWidget
from tlh.ui.ui_hexeditor import Ui_HexEditor

class HexEditorDock (QWidget):
    def __init__(self, parent, instance: HexEditorInstance) -> None:
        super().__init__(parent)
        self.ui = Ui_HexEditor()
        self.ui.setupUi(self)
        self.widget = HexEditorWidget(self, instance, self.ui.scrollBar, self.ui.labelStatusBar)
        self.ui.horizontalLayout_2.insertWidget(0, self.widget)
        

class HexEditorWidget (QWidget):
    def __init__(self, parent, instance: HexEditorInstance, scroll_bar: QScrollBar, statusBar: QLabel):
        super().__init__(parent=parent)
        self.instance = instance
        self._number = 1
        self.line_height = 18
        self.byte_width = 25
        self.bytes_per_line = 16
        self.start_offset = 0
        self.label_offset_x = 5
        self.label_length = 100
        self.cursor = 100
        self.selected_bytes = 0
        self.is_dragging_to_select = False

        # TODO make configurable
        self.font = QFont('DejaVu Sans Mono, Courier, Monospace', 12)
        self.label_color = QColor(128, 128, 128)
        self.byte_color = QColor(210, 210, 210)
        self.selection_color = QPen(QColor(97, 175, 239))
        self.selection_color.setWidth(2)
        self.default_annotation_color = QColor(50,180,50)
        self.scroll_bar = scroll_bar
        self.setup_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.on_scroll_bar_changed)
        self.statusBar = statusBar
        instance.start_offset_moved_externally.connect(self.update_start_offset_from_external)
        instance.cursor_moved_externally.connect(self.update_cursor_from_external)
        instance.selection_updated_externally.connect(self.update_selection_from_external)
        instance.repaint_requested.connect(self.update)
        # Make this widget focussable on click, so that we can reduce the context of the shortcut, so that multiple shortcuts are possible in the same window
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_G), parent, self.show_goto_dialog, context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_C), parent, self.copy_selected_bytes, context = Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_A), parent, self.mark_as_all_pointer, context = Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_4), parent, self.select_four_bytes, context = Qt.WidgetWithChildrenShortcut)
        self.update_status_bar()

    def setup_scroll_bar(self):
        # TODO call this again once the hex view has it's size / changes it's size
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.setMaximum(
            self.number_of_rows() - self.number_of_lines_on_screen()+1)
        self.scroll_bar.setPageStep(self.number_of_lines_on_screen())

    def on_scroll_bar_changed(self, value):
        self.start_offset = value * self.bytes_per_line
        self.instance.start_offset_moved.emit(self.start_offset)
        self.update()

    def wheelEvent(self, event):
        # TODO make scroll speed configurable
        lines_delta = - int(event.angleDelta().y() /
                            self.line_height) * self.bytes_per_line
        if lines_delta <= 0:
            self.update_start_offset(max(self.start_offset + lines_delta, 0))
        else:
            self.update_start_offset(min(self.start_offset + lines_delta,
                                         (self.number_of_rows() - self.number_of_lines_on_screen() + 1)*self.bytes_per_line))

        self.update()

    def update_start_offset_from_external(self, virtual_address):
        self.start_offset = virtual_address
        self.scroll_bar.setValue(virtual_address//self.bytes_per_line)

    def update_start_offset(self, offset):
        self.instance.start_offset_moved.emit(offset)
        #self.start_offset = offset
        #self.scroll_bar.setValue(offset//self.bytes_per_line)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.setup_scroll_bar()
        return super().resizeEvent(event)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(self.font)
        #p.fillRect(self.rect(), QBrush(Qt.blue))

        num_rows = self.number_of_lines_on_screen()

        data = self.instance.get_bytes(
            self.start_offset, self.start_offset + num_rows * self.bytes_per_line)
        # data2 = self.rom2.get_bytes(
        #     self.start_offset, self.start_offset + num_rows * self.bytes_per_line)
        length = len(data)

        # Reduce to the number of lines that are available in the data
        num_rows = length // self.bytes_per_line
        if length % self.bytes_per_line > 0:
            num_rows += 1

        for l in range(num_rows):
            p.setPen(self.label_color)
            # Draw address label
            position_string = self.instance.get_local_label(self.start_offset + l * self.bytes_per_line)
            p.drawText(QPoint(self.label_offset_x, (l + 1)
                       * self.line_height), position_string)

            for i in range(0, min(self.bytes_per_line, length - self.bytes_per_line * l)):

                virtual_address = self.start_offset + l*self.bytes_per_line + i


                p.setPen(self.byte_color)


                current_byte = data[i + l*self.bytes_per_line]
                if current_byte.background is not None:
                    p.setBackground(current_byte.background)
                    p.setBackgroundMode(Qt.OpaqueMode)    


                p.drawText(QPoint(self.label_length + i * self.byte_width, (l+1)
                           * self.line_height), current_byte.text)
                p.setBackgroundMode(Qt.TransparentMode)

                if self.is_selected(virtual_address):
                    p.setPen(self.selection_color)
                    p.drawRect(
                        self.label_length + i * self.byte_width - 3, # TODO make these offsets configurable/dependent on font?
                        (l)* self.line_height + 3,
                        self.byte_width,
                        self.line_height
                        )


    def number_of_lines_on_screen(self):
        # +1 to draw cutof lines as well
        return int(self.height() // self.line_height) + 1

    def number_of_rows(self):
        num_rows = self.instance.length() // self.bytes_per_line
        if self.instance.length() % self.bytes_per_line > 0:
            num_rows += 1
        return num_rows

    def show_goto_dialog(self):
        (local_address, res) = QInputDialog.getText(
        self, 'Goto', 'Enter local address to jump to')
        if res:
            # Parse as hex (TODO maybe as decimal, if no 0x and no)
            # TODO handle errors
            local_address = int(local_address, 16)

            if local_address > ROM_OFFSET:
                local_address -= ROM_OFFSET
            # TODO error for everything that is not in [0x00000000, 0x00FFFFFF] or [0x08000000, 0x08FFFFFF]
            self.update_cursor(self.instance.to_virtual(local_address))

    def contextMenuEvent(self, event: PySide6.QtGui.QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.addAction('Copy cursor address', self.copy_cursor_address)
        menu.addAction('Copy selected bytes', self.copy_selected_bytes)
        
        if abs(self.selected_bytes) == 4:
            menu.addAction('Copy selected as pointer address', self.copy_selected_pointer_address)
            menu.addSeparator()
            menu.addAction('Only mark as pointer', self.mark_as_pointer)
            menu.addAction('Mark as pointer in all linked editors and add constraint', self.mark_as_all_pointer)

        # General actions
        menu.addSeparator()
        menu.addAction('Add annotation at cursor', self.open_new_annotation_dialog)

        menu.addAction('Goto', self.show_goto_dialog)
        menu.exec_(event.globalPos())


    def copy_cursor_address(self):
        QApplication.clipboard().setText(self.instance.get_local_address_str(self.cursor).upper().replace('0X', '0x'))

    def copy_selected_bytes(self):
        QApplication.clipboard().setText(self.instance.get_bytes_str(self.get_selected_range()))

    def copy_selected_pointer_address(self):
        address = self.cursor
        if self.selected_bytes == -4:
            address -= 3           
        points_to = self.instance.get_as_pointer(address)
        QApplication.clipboard().setText(hex(points_to))

    def get_selected_range(self) -> range:
        if self.selected_bytes < 0:
            return range(self.cursor + self.selected_bytes + 1, self.cursor + 1)
        else:
            return range(self.cursor, self.cursor + self.selected_bytes)

    def get_new_pointer_dialog(self):
        address = self.cursor
        if self.selected_bytes == -4:
            address -= 3           
        points_to = self.instance.get_as_pointer(address)

        pointer = Pointer(self.instance.rom_variant, address, points_to, 5, settings.get_username())

        return EditPointerDialog(self, pointer)
        

    def mark_as_pointer(self):
        if abs(self.selected_bytes) != 4:
            return
        dialog = self.get_new_pointer_dialog()
        dialog.pointer_changed.connect(self.add_new_pointer)
        dialog.show()

    def add_new_pointer(self, pointer: Pointer) -> None:
        get_pointer_database().add_pointer(pointer)

    def mark_as_all_pointer(self):
        if abs(self.selected_bytes) != 4:
            return
        dialog = self.get_new_pointer_dialog()
        dialog.pointer_changed.connect(self.add_new_pointer_and_constraints)
        dialog.show()

    def add_new_pointer_and_constraints(self, pointer: Pointer) -> None:
        self.instance.pointer_discovered.emit(pointer)

    
    def open_new_annotation_dialog(self):
        address = self.cursor
        length = abs(self.selected_bytes)
        if self.selected_bytes < 0:
            address += self.selected_bytes + 1
        annotation = Annotation(self.instance.rom_variant, address, length, self.default_annotation_color, settings.get_username())
        dialog = EditAnnotationDialog(self, annotation)
        dialog.annotation_changed.connect(self.add_new_annotation)
        dialog.show()

    def add_new_annotation(self, annotation: Annotation) -> None:
        get_annotation_database().add_annotation(annotation)

    def select_four_bytes(self) -> None:
        self.instance.selection_updated.emit(4)

    def mousePressEvent(self, event: PySide6.QtGui.QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            # TODO handle click on label, etc
            cursor = self.xy_to_cursor(event.x(), event.y())
            if cursor is not None:
                self.update_cursor(cursor)
                self.is_dragging_to_select = True

    def mouseMoveEvent(self, event: PySide6.QtGui.QMouseEvent) -> None:
        if self.is_dragging_to_select:
            cursor = self.xy_to_cursor(event.x(), event.y())
            if cursor is not None:
                selection = cursor-self.cursor
                if selection < 0:
                    selection -= 1
                else:
                    selection += 1
                self.instance.selection_updated.emit(selection)

    def mouseReleaseEvent(self, event: PySide6.QtGui.QMouseEvent) -> None:
        self.is_dragging_to_select = False
    

    def xy_to_cursor(self, x, y):
        line = y // self.line_height
        start = self.label_offset_x + self.label_length
        if x < start or x > start + self.bytes_per_line * self.byte_width:
            return None
        col = (x - start) // (self.byte_width)
        return line * self.bytes_per_line + col + self.start_offset
        
    def keyPressEvent(self, event: QKeyEvent) -> None:
        shift = event.modifiers() & Qt.ShiftModifier == Qt.ShiftModifier
        key = event.key()
        if key == Qt.Key_Up:
            if shift:
                self.move_selection_up()
            else:
                self.move_cursor_up()
        elif key == Qt.Key_Down:
            if shift:
                self.move_selection_down()
            else:
                self.move_cursor_down()
        elif key == Qt.Key_Left:
            if shift:
                self.move_selection_left()
            else:
                self.move_cursor_left()
        elif key == Qt.Key_Right:
            if shift:
                self.move_selection_right()
            else:
                self.move_cursor_right()
        elif key == Qt.Key_PageUp:
            if shift:
                pass # TODO
            else:
                self.move_cursor_page_up()
        elif key == Qt.Key_PageDown:
            if shift:
                pass # TODO
            else:
                self.move_cursor_page_down()

    def move_cursor_up(self):
        if self.cursor >= self.bytes_per_line:
            self.update_cursor(self.cursor - self.bytes_per_line)

    def move_cursor_down(self):
        # TODO check bounds
        self.update_cursor(self.cursor + self.bytes_per_line)

    def move_cursor_left(self):
        self.update_cursor(max(0, self.cursor - 1))

    def move_cursor_right(self):
        # TODO check bounds
        self.update_cursor(self.cursor + 1)

    def move_cursor_page_up(self):
        page_bytes = (self.number_of_lines_on_screen()-1) * self.bytes_per_line
        if self.cursor >= page_bytes:
            self.update_cursor(self.cursor - page_bytes)
        elif self.cursor >= self.bytes_per_line:
            self.update_cursor(self.cursor % self.bytes_per_line)

    def move_cursor_page_down(self):
        # TODO check bounds
        page_bytes = (self.number_of_lines_on_screen()-1) * self.bytes_per_line
        self.update_cursor(self.cursor + page_bytes)


    def move_selection_up(self):
        pass

    def move_selection_down(self):
        pass

    def move_selection_left(self):
        selection = self.selected_bytes-1
        if selection == 0:
            selection = -2
        # TODO file bounds
        self.instance.selection_updated.emit(selection)

    def move_selection_right(self):
        selection = self.selected_bytes+1
        if selection == -1:
            selection = 1
        # TODO file bounds
        self.instance.selection_updated.emit(selection)


    def update_cursor(self, cursor):
        self.cursor = cursor
        self.scroll_to_cursor()
        self.instance.cursor_moved.emit(cursor)
        self.instance.selection_updated.emit(1)

    def update_cursor_from_external(self, cursor):
        self.cursor = cursor
        self.update_status_bar()
        self.update()

    def update_selection_from_external(self, selected_bytes):
        self.selected_bytes = selected_bytes
        self.update_status_bar()
        self.update()

    def update_status_bar(self):
        text = f'Cursor: {self.instance.get_local_address_str(self.cursor)}'

        if (self.selected_bytes != 0):
            text += f' Bytes selected: {self.selected_bytes}'
        self.statusBar.setText(text)



    def scroll_to_cursor(self):
        full_lines = self.number_of_lines_on_screen()-2
        # Is the cursor too far down?
        if (self.cursor - self.start_offset) // self.bytes_per_line >= full_lines:
            # Move to the cursor.
            self.update_start_offset((self.cursor//self.bytes_per_line - full_lines)*self.bytes_per_line)#(self.cursor // self.bytes_per_line - self.number_of_lines_on_screen() -3) * self.bytes_per_line)

        # Is the cursor too far up?
        elif (self.cursor - self.start_offset) // self.bytes_per_line < 0:
            # Move to the cursor.
            self.update_start_offset((self.cursor//self.bytes_per_line)*self.bytes_per_line)


    def is_selected(self, virtual_address: int) -> bool:
        if self.selected_bytes < 0:
            return virtual_address > self.cursor + self.selected_bytes and virtual_address <= self.cursor
        else:
            return virtual_address >= self.cursor and virtual_address < self.cursor + self.selected_bytes
