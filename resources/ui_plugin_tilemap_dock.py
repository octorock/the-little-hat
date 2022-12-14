# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'plugin_tilemap_dock.ui'
##
## Created by: Qt User Interface Compiler version 6.2.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QDockWidget, QGraphicsView, QGridLayout,
    QLabel, QSizePolicy, QSpinBox, QWidget)

class Ui_TilemapDock(object):
    def setupUi(self, TilemapDock):
        if not TilemapDock.objectName():
            TilemapDock.setObjectName(u"TilemapDock")
        TilemapDock.resize(321, 331)
        self.dockWidgetContents = QWidget()
        self.dockWidgetContents.setObjectName(u"dockWidgetContents")
        self.gridLayout_2 = QGridLayout(self.dockWidgetContents)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.graphicsView = QGraphicsView(self.dockWidgetContents)
        self.graphicsView.setObjectName(u"graphicsView")

        self.gridLayout_2.addWidget(self.graphicsView, 2, 0, 1, 1)

        self.labelImageView = QLabel(self.dockWidgetContents)
        self.labelImageView.setObjectName(u"labelImageView")

        self.gridLayout_2.addWidget(self.labelImageView, 0, 0, 1, 1)

        self.graphicsView_2 = QGraphicsView(self.dockWidgetContents)
        self.graphicsView_2.setObjectName(u"graphicsView_2")

        self.gridLayout_2.addWidget(self.graphicsView_2, 2, 1, 1, 1)

        self.graphicsView_3 = QGraphicsView(self.dockWidgetContents)
        self.graphicsView_3.setObjectName(u"graphicsView_3")

        self.gridLayout_2.addWidget(self.graphicsView_3, 3, 0, 1, 2)

        self.spinBoxRoomWidth = QSpinBox(self.dockWidgetContents)
        self.spinBoxRoomWidth.setObjectName(u"spinBoxRoomWidth")

        self.gridLayout_2.addWidget(self.spinBoxRoomWidth, 1, 0, 1, 1)

        self.spinBoxRoomHeight = QSpinBox(self.dockWidgetContents)
        self.spinBoxRoomHeight.setObjectName(u"spinBoxRoomHeight")
        self.spinBoxRoomHeight.setEnabled(False)

        self.gridLayout_2.addWidget(self.spinBoxRoomHeight, 1, 1, 1, 1)

        TilemapDock.setWidget(self.dockWidgetContents)

        self.retranslateUi(TilemapDock)

        QMetaObject.connectSlotsByName(TilemapDock)
    # setupUi

    def retranslateUi(self, TilemapDock):
        TilemapDock.setWindowTitle(QCoreApplication.translate("TilemapDock", u"Metasprite Viewer", None))
        self.labelImageView.setText(QCoreApplication.translate("TilemapDock", u"TextLabel", None))
    # retranslateUi

