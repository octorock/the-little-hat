import socketio
from flask import Flask, request
from PySide6.QtCore import QObject, Signal
import logging

class ServerWorker(QObject):
    '''
    Server worker running in the background that starts a socket.io server on port 10241.
    The JavaScript code that is injected into the CExplore instance can then connect to this port to exchange code and asm snippets.
    '''
    signal_started = Signal()
    signal_connected = Signal()
    signal_disconnected = Signal()
    signal_error = Signal(str)
    signal_shutdown = Signal()
    signal_c_code = Signal(str)
    signal_extract_data = Signal(str)
    signal_fetch_decompilation = Signal(str)
    signal_upload_function = Signal(str)

    def process(self) -> None:
        try:
            # Reduce logging messages
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)

            sio = socketio.Server(async_mode='threading', cors_allowed_origins=[
                                  'https://cexplore.henny022.eu.ngrok.io',
                                  'http://localhost:10240',
                                  'http://localhost:3000',
                                  'https://nonmatch.netlify.app'
                                  ])
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

            @sio.event
            def extract_data(sid, data):
                self.signal_extract_data.emit(data)

            @sio.event
            def fetch_decompilation(sid, data):
                self.signal_fetch_decompilation.emit(data)

            @sio.event
            def upload_function(sid, data):
                self.signal_upload_function.emit(data)

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

            app.run(host='localhost', port=10241)
        except Exception as e:
            self.signal_error.emit(str(e))

    def slot_send_asm_code(self, code: str) -> None:
        self.sio.emit('asm_code', code)

    def slot_send_c_code(self, code: str) -> None:
        self.sio.emit('c_code', code)

    def slot_add_c_code(self, code: str) -> None:
        self.sio.emit('add_c_code', code)

    def slot_request_c_code(self) -> None:
        self.sio.emit('request_c_code')

    def slot_extracted_data(self, data) -> None:
        self.sio.emit('extracted_data', data)