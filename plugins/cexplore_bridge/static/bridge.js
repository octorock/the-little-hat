function main() {
    createIndicator();
    loadSocketIo();
    findMonacoEditors();
}

function createIndicator() {
    let div = document.createElement('div');
    div.innerHTML = '<div><img src="https://raw.githubusercontent.com/octorock/the-little-hat/main/resources/icon.png" height="40"><span style="vertical-align:middle;margin-left:5px" id="bridge_status">Loading bridge to TLH...</span><div style="display:inline-block;width:20px;height:20px;border-radius:10px;vertical-align:middle;background: #efdf00;margin-right:30px;margin-left:10px;" id="bridge_indicator"></div></div>'
    let navbar = document.getElementById('navbarContent');
    navbar.insertBefore(div, navbar.lastChild);
}

function setStatus(text, color) {
    document.getElementById('bridge_status').innerText = text;
    document.getElementById('bridge_indicator').style.backgroundColor = color;
}

function loadSocketIo() {
    var script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js';
    script.onload = startSocketIo;
    document.body.appendChild(script);
}

color_green = '#67c52a';
color_red = '#ec2f19';
color_yellow = '#efdf00';

function startSocketIo() {
    var socket = io('http://localhost:10241');
    socket.on('disconnect', function () {
        error('Disconnected');
    });
    socket.on('connect_error', function () {
        error('Connection failed');
    });
    socket.on('connect', () => {
        setStatus('Connected', color_green);
        socket.emit('client_connected');
    });
    socket.on('asm_code', (data) => {
        if (asmEditorModel != null) {
            asmEditorModel.setValue(data);
            setStatus('Received code', color_green)
        } else {
            error('asm editor not yet found');
        }
    });
    socket.on('c_code', (data) => {
        if (cEditorModel != null) {
            cEditorModel.setValue(data);
            setStatus('Received code', color_green)
        } else {
            error('c editor not yet found');
        }
    });
    socket.on('add_c_code', (data) => {
        if (cEditorModel != null) {
            cEditorModel.setValue(cEditorModel.getValue() + data);
            setStatus('Received code', color_green)
        } else {
            error('c editor not yet found');
        }
    });
    socket.on('request_c_code', () => {
        if (cEditorModel != null) {
            socket.emit('c_code', cEditorModel.getValue());
            setStatus('Sent code', color_green)
        } else {
            error('c editor not yet found');
        }
    });
}

function error(message) {
    console.error(message);
    setStatus('Error: ' + message, color_red);
}

asmEditorModel = null;
cEditorModel = null;

function findMonacoEditors() {
    placeholders = document.getElementsByClassName('monaco-placeholder');
    let cEditorUri = null;
    let asmEditorUri = null;

    let ignoreNextAsm = false;

    for (const placeholder of placeholders) {
        mode = placeholder.dataset.modeId;
        if (mode == 'asm') {
            if (ignoreNextAsm) {
                ignoreNextAsm = false;
                continue;
            }

            if (asmEditorUri != null) {
                error('Found more than one asm editor.');
                console.log(asmEditorUri);
                console.log(placeholder);
                return;
            }
            asmEditorUri = placeholder.children[0].dataset.uri;
            ignoreNextAsm = true;
        } else if (mode == 'nc') {
            if (cEditorUri != null) {
                error('Found more than one c editor.');
                return;
            }
            cEditorUri = placeholder.children[0].dataset.uri;
            // The next asm editor belongs to this 
            ignoreNextAsm = true;
        }
    }

    if (asmEditorUri == null || cEditorUri == null) {
        error('Could not find both asm and c editor.');
        return;
    }

    asmEditorModel = monaco.editor.getModel(asmEditorUri);
    cEditorModel = monaco.editor.getModel(cEditorUri);
}

main();