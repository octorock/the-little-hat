from PySide6.QtGui import QWindow
from common.ui.dark_theme import apply_dark_theme
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from builder.ui import BuilderWidget
import signal

def main():
    # Be able to close with Ctrl+C in the terminal once Qt is started https://stackoverflow.com/a/5160720
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    apply_dark_theme(app)
    
    window = QMainWindow()
    window.setWindowTitle('The Little Hat')

    widget = BuilderWidget(window)
    window.setCentralWidget(widget)

    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()

