from PySide6.QtGui import QColor, QPalette


def apply_dark_theme(app):  # https://stackoverflow.com/a/56851493
    # Force the style to be the same on all OSs:
    app.setStyle("Fusion")

    # Now use a palette to switch to dark colors:
    palette = QPalette()
    palette.setColor(QPalette.WindowText, QColor(180, 180, 180))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.Light, QColor(180, 180, 180))
    palette.setColor(QPalette.Midlight, QColor(90, 90, 90))
    palette.setColor(QPalette.Dark, QColor(35, 35, 35))
    palette.setColor(QPalette.Text, QColor(180, 180, 180))
    palette.setColor(QPalette.BrightText, QColor(180, 180, 180))
    palette.setColor(QPalette.ButtonText, QColor(180, 180, 180))
    palette.setColor(QPalette.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(180, 180, 180))
    palette.setColor(QPalette.Link, QColor(56, 252, 196))
    palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ToolTipBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipText, QColor(180, 180, 180))
    palette.setColor(QPalette.LinkVisited, QColor(80, 80, 80))

    # disabled
    palette.setColor(QPalette.Disabled, QPalette.WindowText,
                     QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Text,
                     QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText,
                     QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Highlight,
                     QColor(80, 80, 80))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText,
                     QColor(127, 127, 127))
    app.setPalette(palette)
