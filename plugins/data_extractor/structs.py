import json
import sys
import typing
from dataclasses import dataclass
from typing import Dict, Optional, List
from weakref import ReferenceType, ref

import pycparser
import pycparser.c_ast

from tlh import settings
import os
import subprocess

from tlh.data.database import get_file_in_database

class Type:
    def to_json_data(self):
        return str(self)


@dataclass
class Struct:
    name: str
    members: Dict[str, Type]

    def to_json_data(self):
        members = {name: type.to_json_data() for name, type in self.members.items()}
        return {'type': 'struct', 'members': members}


@dataclass
class Union:
    name: str
    members: Dict[str, Type]

    def to_json_data(self):
        members = {name: type.to_json_data() for name, type in self.members.items()}
        return {'type': 'union', 'members': members}


@dataclass
class IdentifierType(Type):
    name: str

    def __str__(self):
        return self.name


@dataclass
class BitfieldType(Type):
    type: Type
    size: int

    def __str__(self):
        return f'{self.type} : {self.size}'


@dataclass
class ArrayType(Type):
    type: Type
    size: int

    def __str__(self):
        return f'{self.type}[{self.size}]'


@dataclass
class PointerType(Type):
    type: Type

    def __str__(self):
        return f'{self.type}*'


@dataclass
class FunctionPointerType(Type):
    return_type: Type
    parameter_types: List[Type]

    def __str__(self):
        return f'{self.return_type}(*)({", ".join([str(s) for s in self.parameter_types] if self.parameter_types else "")})'

@dataclass
class FunctionDeclType(Type):
    return_type: Type
    parameter_types: List[Type]

    def __str__(self):
        return f'{self.return_type}()({", ".join([str(s) for s in self.parameter_types] if self.parameter_types else "")})'


@dataclass
class StructType(Type):
    name: str
    _struct: ReferenceType = None

    def get_struct(self) -> Optional[Struct]:
        if self._struct is None:
            return None
        return self._struct()

    def set_struct(self, struct: Struct):
        self._struct = ref(struct)

    struct = property(get_struct, set_struct)

    def __str__(self):
        if self.struct:
            return f'{self.struct.name}'
        return self.name

    def to_json_data(self):
        if self.struct:
            return self.struct.to_json_data()
        return str(self)


@dataclass
class UnionType(Type):
    name: str
    _union: ReferenceType = None

    def get_struct(self) -> Optional[Union]:
        if self._union is None:
            return None
        return self._union()

    def set_struct(self, struct: Struct):
        self._union = ref(struct)

    union = property(get_struct, set_struct)

    def __str__(self):
        if self.union:
            return f'{self.union.name}'
        return self.name

    def to_json_data(self):
        if self.union:
            return self.union.to_json_data()
        return str(self)


def get_anon_name(decl):
    if isinstance(decl, pycparser.c_ast.Struct):
        return f'anon_struct_{decl.coord}'
    if isinstance(decl, pycparser.c_ast.Union):
        return f'anon_union_{decl.coord}'
    raise ValueError('anon of non struct or union')


def get_type_str(type):
    if isinstance(type, pycparser.c_ast.TypeDecl):
        return get_type_str(type.type)
    if isinstance(type, pycparser.c_ast.IdentifierType):
        return IdentifierType(' '.join(type.names))
    if isinstance(type, pycparser.c_ast.ArrayDecl):
        return ArrayType(get_type_str(type.type), int(type.dim.value, 0))
    if isinstance(type, pycparser.c_ast.PtrDecl):
        if isinstance(type.type, pycparser.c_ast.FuncDecl):
            ftype = type.type
            return_type = get_type_str(ftype.type)
            parameter_types = None
            if ftype.args is not None:
                parameter_types = [get_type_str(x.type) for x in ftype.args.params]
            return FunctionPointerType(return_type, parameter_types)
        return PointerType(get_type_str(type.type))
    if isinstance(type, pycparser.c_ast.Union):
        name = type.name
        if name is None:
            name = get_anon_name(type)
        return UnionType(name)
    if isinstance(type, pycparser.c_ast.Struct):
        name = type.name
        if name is None:
            name = get_anon_name(type)
        return StructType(name)
    if isinstance(type, pycparser.c_ast.Enum):
        return None
    if isinstance(type, pycparser.c_ast.FuncDecl):
        return_type = get_type_str(type.type)
        parameter_types = None
        if type.args is not None:
            parameter_types = [get_type_str(x.type) for x in type.args.params]
        return FunctionDeclType(return_type, parameter_types)
    print(type.coord)
    raise ValueError('bad type')


class StructVisitor(pycparser.c_ast.NodeVisitor):
    structs: Dict[str, typing.Union[Struct, Union]]
    typedefs: Dict[str, Type]

    def __init__(self):
        self.structs = {}
        self.typedefs = {}

    def visit_Struct(self, node):
        name = node.name
        if name is None:
            name = get_anon_name(node)
        members = {}
        if not node.decls:
            return
        for member in node.decls:
            member_type = get_type_str(member.type)
            if member.bitsize:
                member_type = BitfieldType(member_type, member.bitsize.value)
            members[member.name] = member_type
        self.structs[name] = Struct(name, members)
        self.generic_visit(node)

    def visit_Union(self, node):
        name = node.name
        if name is None:
            name = get_anon_name(node)
        members = {}
        if not node.decls:
            return
        for member in node.decls:
            member_type = get_type_str(member.type)
            if member.bitsize:
                member_type = BitfieldType(member_type, member.bitsize.value)
            members[member.name] = member_type
        self.structs[name] = Union(name, members)
        self.generic_visit(node)

    def visit_Typedef(self, node):
        name = node.name
        type = get_type_str(node.type)
        self.typedefs[name] = type
        self.generic_visit(node)


def link_structs(data):
    for name in data:
        for member_name, member_type in data[name].members.items():
            if isinstance(member_type, StructType):
                member_type.struct = data[member_type.name]
            if isinstance(member_type, UnionType):
                member_type.union = data[member_type.name]


def dump_json(data, filename, drop_anon=True):
    jsondata = {name: type.to_json_data() for name, type in data.items() if
                not drop_anon or not name.startswith('anon_')}
    with open(filename, 'w') as jsonfile:
        json.dump(jsondata, jsonfile, indent=2)


def typedef_structs(data, typedefs):
    for name, type in typedefs.items():
        if isinstance(type, StructType):
            anon_name = type.name
        elif isinstance(type, UnionType):
            anon_name = type.name
        else:
            continue
        data[name] = data[anon_name]
        data[name].name = name


def main():
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = 'test.i'

    parse_to_json(filename, 'test.json')
    print('ok')

def parse_to_json(input_filename, output_filename) -> None:
    with open(input_filename) as input_file:
        text = input_file.read()
        text = text.replace('__attribute__((packed))', '')
        text = text.replace('__attribute__((packed, aligned(2)))', '')
        ast = pycparser.CParser().parse(text, input_filename)
        v = StructVisitor()
        v.visit(ast)
        data = v.structs
        typedef_structs(data, v.typedefs)
        link_structs(data)
        dump_json(data, output_filename)

if __name__ == '__main__':
    main()


def generate_struct_definitions() -> None:
    with open('tmp/test.c', 'w') as file:
        file.write(
'''
#include "sound.h"
#include "coord.h"
#include "effects.h"
#include "enemy.h"
#include "entity.h"
#include "fileselect.h"
#include "flags.h"
#include "functions.h"
#include "game.h"
#include "global.h"
#include "item.h"
#include "main.h"
#include "manager.h"
#include "menu.h"
#include "npc.h"
#include "object.h"
#include "player.h"
#include "room.h"
#include "save.h"
#include "screen.h"
#include "script.h"
#include "sprite.h"
#include "structures.h"
#include "message.h"
#include "tiles.h"
#include "common.h"
'''
)
    repo_location = settings.get_repo_location()
    # Preprocess file
    subprocess.check_call(['cc', '-E', '-I',  os.path.join(repo_location, 'tools/agbcc'), '-I', os.path.join(repo_location, 'tools/agbcc/include'), '-iquote', os.path.join(repo_location, 'include'), '-nostdinc', '-undef', '-DUSA', '-DREVISION=0', '-DENGLISH', 'tmp/test.c', '-o', 'tmp/test.i'])

    parse_to_json('tmp/test.i', get_file_in_database(os.path.join('data_extractor', 'structs.json')))

