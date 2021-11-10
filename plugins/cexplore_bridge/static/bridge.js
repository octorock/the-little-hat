function main() {
    createIndicator();
    loadSocketIo();
    if (window.hub == undefined) {
        findMonacoEditorsLegacy();
    } else {
        // Find monaco editors via the exposed hub object.
        findMonacoEditors();
        registerShortcut();
    }
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

let socket;

function startSocketIo() {
    socket = io('http://localhost:10241');
    socket.on('disconnect', function () {
        connect_error('Disconnected');
    });
    socket.on('connect_error', function () {
        connect_error('Connection failed');
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
            connect_error('asm editor not yet found');
        }
    });
    socket.on('c_code', (data) => {
        if (cEditorModel != null) {
            cEditorModel.setValue(data);
            setStatus('Received code', color_green)
        } else {
            connect_error('c editor not yet found');
        }
    });
    socket.on('add_c_code', (data) => {
        if (cEditorModel != null) {
            cEditorModel.setValue(cEditorModel.getValue() + data);
            setStatus('Received code', color_green)
        } else {
            connect_error('c editor not yet found');
        }
    });
    socket.on('request_c_code', () => {
        if (cEditorModel != null) {
            socket.emit('c_code', cEditorModel.getValue());
            setStatus('Sent code', color_green)
        } else {
            connect_error('c editor not yet found');
        }
    });
    socket.on('extracted_data', (data) => {
        console.log(data);
        // TODO return error somehow?
        if (data['status'] === 'ok') {
            cEditor.editor.executeEdits("CExploreBridge", [
                { range: cEditor.editor.getSelection(), text: data['text'] }
        ]);
        } else if (data['status'] === 'error') {
            error(data['text']);
        }
    });
}

function connect_error(message) {
    console.error(message);
    setStatus('Error: ' + message, color_red);
}

function error(message) {
    console.error(message)
    // TODO less obtrusive error toast
    alert(message)
}

let asmEditor = null;
let asmEditorModel = null;
let cEditor = null;
let cEditorModel = null;

function findMonacoEditorsLegacy() {
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
                connect_error('Found more than one asm editor.');
                console.log(asmEditorUri);
                console.log(placeholder);
                return;
            }
            asmEditorUri = placeholder.children[0].dataset.uri;
            ignoreNextAsm = true;
        } else if (mode == 'nc') {
            if (cEditorUri != null) {
                connect_error('Found more than one c editor.');
                return;
            }
            cEditorUri = placeholder.children[0].dataset.uri;
            // The next asm editor belongs to this 
            ignoreNextAsm = true;
        }
    }

    if (asmEditorUri == null || cEditorUri == null) {
        connect_error('Could not find both asm and c editor.');
        return;
    }

    asmEditorModel = monaco.editor.getModel(asmEditorUri);
    cEditorModel = monaco.editor.getModel(cEditorUri);

    console.log('asmEditorModel', asmEditorModel);
    console.log('cEditorModel', cEditorModel);
}

function findMonacoEditors() {
    for (const editor of hub.editors) {
        switch (editor.editor.getModel().getModeId()) {
            case 'asm':
                if (asmEditor != null) {
                    connect_error('There are two asm editors open.')
                    return;
                }
                asmEditor = editor;
                asmEditorModel = editor.editor.getModel();
                break;
            case 'nc':
                if (cEditor != null) {
                    connect_error('There are two c editors open.')
                    return;
                }
                cEditor = editor;
                cEditorModel = editor.editor.getModel();
                break;
            default:
                // ignore other editors if there were any for some reason?
                break;
        }
    }
}

function registerShortcut() {
    document.onkeyup = function(e) {
        if (e.ctrlKey && e.key == 'b') {
            let selectedText = cEditorModel.getValueInRange(cEditor.editor.getSelection());
            if (selectedText.length == 0) {
                error('Nothing selected in c editor.');
                return;
            }

            socket.emit('extract_data', selectedText);
        }
    };
}

main();