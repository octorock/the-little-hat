# Inspired by https://github.com/PetterS/sexton
# Paint custom widget https://blog.rburchell.com/2010/02/pyside-tutorial-custom-widget-painting.html

from tlh.data.rom import Rom
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

class HexEditorWidget (QWidget):
    def __init__(self, parent, rom: Rom):
        super().__init__(parent=parent)
        self.rom = rom
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

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(self.font)
        #p.fillRect(self.rect(), QBrush(Qt.blue))


        num_rows = self.number_of_lines_on_screen()

        data = self.rom.get_bytes(self.start_offset, self.start_offset + num_rows * self.bytes_per_line)
        length = len(data)
        
        # Reduce to the number of lines that are available in the data
        num_rows = length // self.bytes_per_line
        if length % self.bytes_per_line > 0:
            num_rows += 1

        for l in range(num_rows):
            p.setPen(self.label_color)
            # Draw address label
            position_string = '%08X' % (self.start_offset + l * self.bytes_per_line)
            p.drawText(QPoint(self.label_offset_x, (l + 1) * self.line_height), position_string)

            p.setPen(self.byte_color)
            for i in range(0, min(self.bytes_per_line, length - self.bytes_per_line * l)):
                p.drawText(QPoint(self.label_length + i * self.byte_width,(l+1)*self.line_height), '%02X' % data[i + l*self.bytes_per_line])

    def number_of_lines_on_screen(self):
        return int (self.height() // self.line_height) + 1 # +1 to draw cutof lines as well