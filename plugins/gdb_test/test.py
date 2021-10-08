from pygdbmi.gdbcontroller import GdbController
from pprint import pprint
import os
from parse import parse_result
from stats import show_entity_lists
import pyperclip

# Start gdb process
gdbmi = GdbController(['/opt/devkitpro/devkitARM/bin/arm-none-eabi-gdb', '-interpreter=mi3'])
print(gdbmi.command)  # print actual command run as subprocess

def gdb(cmd):
    print(' > ' + cmd)
    response = gdbmi.write(cmd)
    pprint(response)
    return response

gdb('-file-exec-and-symbols ~/git/tmc/tmc.elf')
gdb('-target-select remote localhost:2345')
#gdb('-enable-pretty-printing')
#gdb('-data-evaluate-expression gEntityLists')
gdb('-exec-continue ')


def read_var(var):
    messages = gdbmi.write('-data-evaluate-expression ' + var)
    for message in messages:
        if message['type'] == 'result':
            return parse_result(message['payload']['value'])
    return None

def read_entity_lists():
    lists = []

    list_addr = 0x3003d70


    entity_lists = read_var('gEntityLists')

    for i in range(len(entity_lists)):
        lists.append([])
        first = int(entity_lists[i]['first'], 16)
        if first != 0 and first != list_addr + 8*i:
            # There are elements in this list
            entity = read_var('*(Entity*)' + hex(first))
            lists[i].append(entity)
            next = int(entity['next'], 16)
            while next != list_addr + 8*i:
                entity = read_var('*(Entity*)' + hex(next))
                lists[i].append(entity)
                next = int(entity['next'], 16)

    #print(read_var('gEntCount'))
    #print(entity_lists)
    return lists



while True:
    line = input('> ')
    if line == 'end':
        break
    elif line == 'list':
        os.kill(gdbmi.gdb_process.pid, 2) # SIGINT

        lists = read_entity_lists()
        #show_entity_lists(lists)
        roomControls = read_var('gRoomControls')
        data = 'lists=' + str(lists) + ';\n'
        data += 'roomControls=' + str(roomControls) + ';'
        pyperclip.copy(data)

        #gdb('-exec-continue')
    else:
        gdb(line)
gdb('-target-disconnect')



"""
Issues:
- mgba's gdb-server does not support non-stop mode
"""

gdbmi.exit()