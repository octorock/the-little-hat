from PySide6.QtCore import QProcess, QSize, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget

class BuilderWidget (QWidget):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.verticalLayout = QVBoxLayout(self)

        self.compileButton = QPushButton('Compile', self)
        self.compileButton.setMinimumSize(QSize(200, 50))
        self.verticalLayout.addWidget(self.compileButton, 0, Qt.AlignHCenter)

        self.tidyButton = QPushButton('Tidy', self)
        self.verticalLayout.addWidget(self.tidyButton, 0, Qt.AlignHCenter)


        self.splitter = QSplitter(self)
        self.splitter.setOrientation(Qt.Vertical)

        self.widget = QWidget(self.splitter)
        self.widget.setObjectName(u"widget")
        self.verticalLayout2 = QVBoxLayout(self.widget)
        self.stdoutLabel = QLabel(self.widget)
        self.stdoutLabel.setText('stdout:')

        self.verticalLayout2.addWidget(self.stdoutLabel)

        self.stdoutText = QTextEdit(self.widget)
        self.stdoutText.setEnabled(False)
        self.stdoutText.setReadOnly(True)
        self.stdoutText.setPlainText("Output will appear here")

        self.verticalLayout2.addWidget(self.stdoutText)

        self.splitter.addWidget(self.widget)

        self.widget1 = QWidget(self.splitter)

        self.verticalLayout3 = QVBoxLayout(self.widget1)
        self.stderrLabel = QLabel(self.widget1)
        self.stderrLabel.setText('stderr:')

        self.verticalLayout3.addWidget(self.stderrLabel)

        self.stderrText = QTextEdit(self.widget1)
        self.stderrText.setEnabled(False)
        self.stderrText.setReadOnly(True)
        self.stderrText.setPlainText('Errors will appear here')

        self.verticalLayout3.addWidget(self.stderrText)

        self.splitter.addWidget(self.widget1)

        self.verticalLayout.addWidget(self.splitter)


        # Logic

        # Use QProcess to start a program and get its outputs https://stackoverflow.com/a/22110924
        self.process = QProcess(self)

        self.process.setWorkingDirectory('../github') # TODO make configurable

        self.process.readyReadStandardOutput.connect(self.readStdout)
        self.process.readyReadStandardError.connect(self.readStderr)
        self.process.started.connect(self.processStarted)
        self.process.finished.connect(self.processFinished)
        self.process.errorOccurred.connect(self.errorOccurred)
        self.compileButton.clicked.connect(self.doCompile)
        self.tidyButton.clicked.connect(self.doTidy)
        

    def doCompile(self):
        self.process.start('make', ['-j', '8']) # TODO run nproc once and store the result?

    def doTidy(self):
        self.process.start('make', ['tidy'])

    def readStdout(self):
        line = self.process.readAllStandardOutput().data().decode()[:-1]
        if line == 'tmc.gba: FAILED':
            line = 'tmc.gba: <b style="color:red">FAILED</b>'
        elif line == 'tmc.gba: OK':
            line = 'tmc.gba: <b style="color: green">OK</b>'
        self.stdoutText.append(line)
 
    def readStderr(self):
        line = self.process.readAllStandardError().data().decode()[:-1]
        if 'error' in line:
            line = f'<span style="color:red">{line}</span>'
        elif 'warning' in line:
            line = f'<span style="color:orange">{line}</span>'

        self.stderrText.append(line)
        

    def processStarted(self):
        self.stdoutText.setEnabled(True)
        self.stderrText.setEnabled(True)
        self.stdoutText.setPlainText('')
        self.stderrText.setPlainText('')
        self.compileButton.setEnabled(False)
        self.tidyButton.setEnabled(False)
        print('started')

    def processFinished(self):
        self.compileButton.setEnabled(True)
        self.tidyButton.setEnabled(True)
        print('finished')

    def errorOccurred(self):
        self.stderrText.insertPlainText(self.process.errorString())
