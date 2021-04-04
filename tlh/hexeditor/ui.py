# Inspired by https://github.com/PetterS/sexton
# Paint custom widget https://blog.rburchell.com/2010/02/pyside-tutorial-custom-widget-painting.html

import PySide6
from tlh.hexeditor.manager import ByteStatus, HexEditorInstance
from tlh.const import ROM_OFFSET
from tlh.data.rom import Rom
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QPainter, QPen, QResizeEvent, QShortcut
from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox, QScrollBar, QWidget


class HexEditorWidget (QWidget):
    def __init__(self, parent, instance: HexEditorInstance, scroll_bar: QScrollBar):
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

        # TODO make configurable
        self.font = QFont("DejaVu Sans Mono, Courier, Monospace", 12)
        self.label_color = QColor(128, 128, 128)
        self.byte_color = QColor(210, 210, 210)
        self.diff_color = QColor(158, 80, 88)#QColor(244, 108, 117)
        self.selection_color = QPen(QColor(97, 175, 239))
        self.selection_color.setWidth(2)
        self.scroll_bar = scroll_bar
        self.setup_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.on_scroll_bar_changed)
        instance.cursor_moved_externally.connect(self.update_start_offset_from_external)
        # Make this widget focussable on click, so that we can reduce the context of the shortcut, so that multiple shortcuts are possible in the same window
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        QShortcut(QKeySequence(Qt.CTRL + Qt.Key_G), parent, self.show_goto_dialog, context=Qt.WidgetWithChildrenShortcut)


    def setup_scroll_bar(self):
        # TODO call this again once the hex view has it's size / changes it's size
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.setMaximum(
            self.number_of_rows() - self.number_of_lines_on_screen()+1)
        self.scroll_bar.setPageStep(self.number_of_lines_on_screen())

    def on_scroll_bar_changed(self, value):
        self.start_offset = value * self.bytes_per_line
        self.instance.cursor_moved.emit(self.start_offset)
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
        self.instance.cursor_moved.emit(offset)
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

                if virtual_address == self.cursor:
                    p.setPen(self.selection_color)
                    p.drawRect(
                        self.label_length + i * self.byte_width - 3, # TODO make these offsets configurable/dependent on font?
                        (l)* self.line_height + 3,
                        self.byte_width,
                        self.line_height
                        )

                p.setPen(self.byte_color)


                current_byte = data[i + l*self.bytes_per_line]
                if current_byte.status == ByteStatus.DIFFERING:
                    p.setBackground(self.diff_color)
                    p.setBackgroundMode(Qt.OpaqueMode)    

                # if byte1 != byte2:
                #     # p.setPen(QColor(255,0,0))
                #     p.setBackground(QColor(128, 40, 40))
                #     p.setBackgroundMode(Qt.OpaqueMode)
                # # else:
                #     # p.setPen(self.byte_color)

                

                p.drawText(QPoint(self.label_length + i * self.byte_width, (l+1)
                           * self.line_height), current_byte.text)
                p.setBackgroundMode(Qt.TransparentMode)

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

            self.instance.jump_to_local_address(local_address)

    def contextMenuEvent(self, event: PySide6.QtGui.QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.addAction('Goto', self.show_goto_dialog)
        menu.exec_(event.globalPos())