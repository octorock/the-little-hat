
from enum import Enum
from tlh.hexviewer.display_byte import DisplayByte
from tlh.data.constraints import Constraint
from tlh.data.annotations import Annotation
from tlh.data.database import get_annotation_database, get_constraint_database, get_pointer_database
from tlh.data.pointer import Pointer
from tlh.const import ROM_OFFSET
from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QFont, QKeyEvent, QKeySequence, QMouseEvent, QPainter, QPen, QResizeEvent, QShortcut
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QToolTip, QWidget
from tlh.hexviewer.edit_annotation_dialog import EditAnnotationDialog
from tlh.hexviewer.edit_constraint_dialog import EditConstraintDialog
from tlh.hexviewer.edit_pointer_dialog import EditPointerDialog
from tlh import settings
from typing import Optional


class KeyType(Enum):
    UP = 1
    DOWN = 2
    LEFT = 3
    RIGHT = 4
    PAGE_UP = 5
    PAGE_DOWN = 6


class HexAreaWidget (QWidget):
    '''
    Responsible for painting the area that actually containts the hex display
    '''

    signal_resized = Signal()
    signal_scroll_wheel_changed = Signal(int)
    signal_cursor_changed = Signal(int)
    signal_selection_updated = Signal(int)
    signal_key_cursor_pressed = Signal(KeyType)
    signal_key_selection_pressed = Signal(KeyType)
    signal_context_menu_shown = Signal(QPoint)
    signal_show_tooltip_at_offset = Signal(int, QPoint)
    signal_go_to_pointer_at_offset = Signal(int)

    def __init__(self, parent: QWidget):
        # , scroll_bar: QScrollBar, statusBar: QLabel
        super().__init__(parent=parent)

        self.line_height = 18
        self.byte_width = 25
        self.bytes_per_line = 16

        self.label_offset_x = 5
        self.label_length = 100
        self.is_dragging_to_select = False

        self.display_data: list[DisplayByte] = []
        self.display_labels: list[str] = []

        # TODO make configurable
        self.font = QFont('DejaVu Sans Mono, Courier, Monospace', 12)
        self.label_color = QColor(128, 128, 128)
        self.byte_color = QColor(210, 210, 210)
        self.selection_color = QPen(QColor(97, 175, 239))
        self.selection_color.setWidth(2)

        # Make this widget focussable on click, so that we can reduce the context of the shortcut, so that multiple shortcuts are possible in the same window
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event):
        # TODO make scroll speed configurable
        lines_delta = - int(event.angleDelta().y() /
                            self.line_height) * self.bytes_per_line

        self.signal_scroll_wheel_changed.emit(lines_delta)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.signal_resized.emit()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setFont(self.font)
        #p.fillRect(self.rect(), QBrush(Qt.blue))

        length = len(self.display_data)

        # Reduce to the number of lines that are available in the data
        num_rows = length // self.bytes_per_line
        if length % self.bytes_per_line > 0:
            num_rows += 1

        for l in range(num_rows):
            p.setPen(self.label_color)
            # Draw address label
            # self.instance.get_local_label(self.start_offset + l * self.bytes_per_line)
            position_string = self.display_labels[l]
            p.drawText(QPoint(self.label_offset_x, (l + 1)
                       * self.line_height), position_string)

            for i in range(0, min(self.bytes_per_line, length - self.bytes_per_line * l)):

                #virtual_address = self.start_offset + l*self.bytes_per_line + i

                p.setPen(self.byte_color)

                current_byte = self.display_data[i + l*self.bytes_per_line]
                if current_byte.background is not None:
                    p.setBackground(current_byte.background)
                    p.setBackgroundMode(Qt.OpaqueMode)

                p.drawText(QPoint(self.label_length + i * self.byte_width, (l+1)
                           * self.line_height), current_byte.text)
                p.setBackgroundMode(Qt.TransparentMode)

                if current_byte.is_selected:
                    p.setPen(self.selection_color)
                    p.drawRect(
                        # TODO make these offsets configurable/dependent on font?
                        self.label_length + i * self.byte_width - 3,
                        (l) * self.line_height + 3,
                        self.byte_width,
                        self.line_height
                    )

    def number_of_lines_on_screen(self):
        # +1 to draw cutof lines as well
        return int(self.height() // self.line_height) + 1

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.signal_context_menu_shown.emit(event.globalPos())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:

            # TODO handle click on label, etc
            offset = self.xy_to_offset(event.x(), event.y())
            if offset is not None:

                ctrl = event.modifiers() & Qt.ControlModifier == Qt.ControlModifier

                if ctrl:
                    # Go to pointer
                    self.signal_go_to_pointer_at_offset.emit(offset)
                    return

                self.signal_cursor_changed.emit(offset)
                self.is_dragging_to_select = True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.is_dragging_to_select:
            offset = self.xy_to_offset(event.x(), event.y())
            if offset is not None:
                self.signal_selection_updated.emit(offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.is_dragging_to_select = False

    def xy_to_offset(self, x, y) -> Optional[int]:
        '''
        Returns offsets in bytes from the start_offset or None if not clicked on a byte
        '''
        line = y // self.line_height
        start = self.label_offset_x + self.label_length
        if x < start or x > start + self.bytes_per_line * self.byte_width:
            return None
        col = (x - start) // (self.byte_width)
        return line * self.bytes_per_line + col

    def keyPressEvent(self, event: QKeyEvent) -> None:
        shift = event.modifiers() & Qt.ShiftModifier == Qt.ShiftModifier
        key = event.key()
        if key == Qt.Key_Up:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.UP)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.UP)
        elif key == Qt.Key_Down:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.DOWN)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.DOWN)
        elif key == Qt.Key_Left:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.LEFT)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.LEFT)
        elif key == Qt.Key_Right:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.RIGHT)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.RIGHT)
        elif key == Qt.Key_PageUp:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.PAGE_UP)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.PAGE_UP)
        elif key == Qt.Key_PageDown:
            if shift:
                self.signal_key_selection_pressed.emit(KeyType.PAGE_DOWN)
            else:
                self.signal_key_cursor_pressed.emit(KeyType.PAGE_DOWN)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.ToolTip:
            offset = self.xy_to_offset(
                event.pos().x(), event.pos().y())
            if offset is None:
                QToolTip.hideText()
                return True
            self.signal_show_tooltip_at_offset.emit(offset, event.globalPos())
            return True

        return super().event(event)
