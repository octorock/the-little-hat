from flask import Flask, request
from PySide6.QtCore import QObject, Signal
import logging

class ServerWorker(QObject):
    '''
    Server worker running in the background that starts a http server on port 10244 that mGBA uses to tell us interesting facts.
    '''
    signal_started = Signal()
    signal_error = Signal(str)
    signal_shutdown = Signal()
    signal_connected = Signal()
    signal_script_addr = Signal(int)

    def process(self) -> None:
        try:
            # Reduce logging messages
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)

            app = Flask(__name__)

            @app.route('/connect', methods=['GET'])
            def connect():
                self.signal_connected.emit()
                return 'ok'

            @app.route('/script', methods=['GET'])
            def script():
                print('GOT SCRIPT_CALL', request.args['addr'])
                self.signal_script_addr.emit(int(request.args['addr']))
                return 'ok'

            @app.route('/shutdown', methods=['GET'])
            def shutdown():
                # TODO deprecated, use better server? https://github.com/pallets/werkzeug/issues/1752
                func = request.environ.get('werkzeug.server.shutdown')
                if func is None:
                    raise RuntimeError('Not running with the Werkzeug Server')
                func()
                self.signal_shutdown.emit()
                return ''

            self.signal_started.emit()

            app.run(host='localhost', port=10244)
        except Exception as e:
            self.signal_error.emit(str(e))

