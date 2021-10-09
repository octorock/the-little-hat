import socketio
from flask import Flask, request
from PySide6.QtCore import QObject, Signal
import logging

class ServerWorker(QObject):
    '''
    Server worker running in the background that starts a socket.io server on port 10243 to communicate with entity explorer.
    '''
    signal_started = Signal()
    signal_connected = Signal()
    signal_disconnected = Signal()
    signal_error = Signal(str)
    signal_shutdown = Signal()
    signal_c_code = Signal(str)

    def process(self) -> None:
        try:
            # Reduce logging messages
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)

            sio = socketio.Server(async_mode='threading', cors_allowed_origins=[
                                  'https://octorock.github.io', 'http://localhost:1234'])
            self.sio = sio
            app = Flask(__name__)
            app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

            @sio.event
            def connect(sid, environ):
                self.signal_connected.emit()

            @sio.event
            def c_code(sid, data):
                self.signal_c_code.emit(data)

            @sio.event
            def disconnect(sid):
                self.signal_disconnected.emit()

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

            app.run(host='localhost', port=10243)
        except Exception as e:
            self.signal_error.emit(str(e))

    def slot_send_save_state(self, path:str, data: bytes) -> None:
        if path.endswith('.State'):
            self.sio.emit('load_bizhawk', data)
        else:
            self.sio.emit('load_mgba', data)
