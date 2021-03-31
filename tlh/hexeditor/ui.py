# Inspired by https://github.com/PetterS/sexton
# Paint custom widget https://blog.rburchell.com/2010/02/pyside-tutorial-custom-widget-painting.html

from tlh.const import ROM_OFFSET
from tlh.data.rom import Rom
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QResizeEvent
from PySide6.QtWidgets import QScrollBar, QWidget

class HexEditorWidget (QWidget):
    def __init__(self, parent, rom: Rom, rom2: Rom, scroll_bar: QScrollBar):
        super().__init__(parent=parent)
        self.rom = rom
        self.rom2 = rom2
        self._number = 1
        self.line_height = 18
        self.byte_width = 25
        self.bytes_per_line = 16
        self.start_offset = 0
        self.label_offset_x = 5
        self.label_length = 100
        self.font = QFont("DejaVu Sans Mono, Courier, Monospace", 12) # TODO make configurable
        self.label_color = QColor(128,128,128)
        self.byte_color = QColor(210,210,210)
        self.scroll_bar = scroll_bar
        self.setup_scroll_bar()
        self.scroll_bar.valueChanged.connect(self.on_scroll_bar_changed)

    def setup_scroll_bar(self):
        # TODO call this again once the hex view has it's size / changes it's size
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.setMaximum(self.number_of_rows() - self.number_of_lines_on_screen()+1)
        self.scroll_bar.setPageStep(self.number_of_lines_on_screen())

    def on_scroll_bar_changed(self, value):
        self.start_offset = value * self.bytes_per_line
        self.update()

    def wheelEvent(self, event):
        # TODO make scroll speed configurable
        lines_delta = - int( event.angleDelta().y() / self.line_height) * self.bytes_per_line
        if lines_delta <= 0:
            self.update_start_offset(max(self.start_offset + lines_delta, 0))
        else:
            self.update_start_offset(min(self.start_offset + lines_delta,
			                     (self.number_of_rows() - self.number_of_lines_on_screen() + 1)*self.bytes_per_line))

        self.update()

    def update_start_offset(self, offset):
        self.start_offset = offset
        self.scroll_bar.setValue(offset//self.bytes_per_line)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.setup_scroll_bar()
        return super().resizeEvent(event)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(self.font)
        #p.fillRect(self.rect(), QBrush(Qt.blue))


        num_rows = self.number_of_lines_on_screen()

        data = self.rom.get_bytes(self.start_offset, self.start_offset + num_rows * self.bytes_per_line)
        data2 = self.rom2.get_bytes(self.start_offset, self.start_offset + num_rows * self.bytes_per_line)
        length = len(data)
        
        # Reduce to the number of lines that are available in the data
        num_rows = length // self.bytes_per_line
        if length % self.bytes_per_line > 0:
            num_rows += 1

        for l in range(num_rows):
            p.setPen(self.label_color)
            # Draw address label
            position_string = '%08X' % (self.start_offset + l * self.bytes_per_line + ROM_OFFSET)
            p.drawText(QPoint(self.label_offset_x, (l + 1) * self.line_height), position_string)

            p.setPen(self.byte_color)
            for i in range(0, min(self.bytes_per_line, length - self.bytes_per_line * l)):

                byte1 = data[i + l*self.bytes_per_line]
                byte2 = data2[i + l*self.bytes_per_line]

                if byte1 != byte2:
                    #p.setPen(QColor(255,0,0))
                    p.setBackground(QColor(128,40,40))
                    p.setBackgroundMode(Qt.OpaqueMode)
                #else:
                    #p.setPen(self.byte_color)

                p.drawText(QPoint(self.label_length + i * self.byte_width,(l+1)*self.line_height), '%02X' % data[i + l*self.bytes_per_line])
                p.setBackgroundMode(Qt.TransparentMode)

    def number_of_lines_on_screen(self):
        return int (self.height() // self.line_height) + 1 # +1 to draw cutof lines as well

    def number_of_rows(self):
        num_rows = self.rom.length() // self.bytes_per_line
        if self.rom.length() % self.bytes_per_line > 0:
            num_rows += 1
        return num_rows