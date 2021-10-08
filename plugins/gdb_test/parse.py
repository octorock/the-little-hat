from pprint import pprint


def parse_array(data):
    array = []
    while True:
        val, data = parse_any(data)
        array.append(val)
        if data[0] == ',':
            data = data[2:]
            continue
        elif data[0] == '}':
            data = data[1:]
            break
        else:
            assert(False)
    return array, data

def parse_key(data):
    split = 0
    for i in range(len(data)):
        if data[i] in [' ', ',', '}']:
            return data[0:i], data[i:]
    return data, ''

def parse_value(data):
    val, data = _parse_value(data)
    # Remove unnecessary char conversion from value
    if val[0] != '\'' and '\'' in val:
        val = val.split('\'')[0]
    return val, data
def _parse_value(data):
    split = 0
    in_quotes = False
    for i in range(len(data)):
        if data[i] == '\'' and (data[i-1] != '\\' or data[i-2] =='\\'):
            in_quotes = not in_quotes
        if data[i] in [',', '}'] and not in_quotes:
            return data[0:i], data[i:]
    return data, ''

def parse_object(data):
    #print(data)
    object = {}
    while True:
        if data[0] == '<':
            # ignore  <incomplete sequence \340>,
            i = data.find(',')+2
            data = data[i:]

        key, data = parse_key(data)
        #print('K', key)
        assert data[0:3] == ' = ', 'Data: ' + data
        data = data[3:]
        #print(data)
        value, data = parse_any(data)
        object[key] = value
        #print(len(data))
        if data[0] == ',':
            data = data[2:]
            continue
        elif data[0] == '}':
            data = data[1:]
            break
        else:
            print(data[0:10])
            print(data)
            assert(False)
    #print('OBJ', data)
    return object, data


def parse_any(data):
    if data[0] == '{':
        if data[1] == '{' or data.find('=') > data[1:].find('}'):
            return parse_array(data[1:])
        else:
            return parse_object(data[1:])
    else:
        return parse_value(data)

def parse_result(data):
    print('PARSE', data)
    res, data = parse_any(data)
    #print('not parsed', data, len(data))
    assert(len(data) == 0) # Parsed everything
    return res


#print(parse_result('{{last = 0x30016b0, first = 0x3001628}, {last = 0x3001160, first = 0x3001160}, {last = 0x3003d80, first = 0x3003d80}, {last = 0x3003d88, first = 0x3003d88}, {last = 0x3001848, first = 0x3001848}, {last = 0x3003d98, first = 0x3003d98}, {last = 0x3001c88, first = 0x2033290}, {last = 0x3001b78, first = 0x3001958}, {last = 0x20333d0, first = 0x20333d0}}'))
#print(parse_result('26 \'\\032\''))
#pprint(parse_result(r"""{prev = 0x3003d70, next = 0x30016b0, kind = 6 '\006', id = 56 '8', type = 200 '\310', type2 = 0 '\000', action = 1 '\001', subAction = 0 '\000', actionDelay = 0 '\000', field_0xf = 0 '\000', flags = 129 '\201', scriptedScene = 1 '\001', scriptedScene2 = 1 '\001', spriteIndex = 127, animationState = 0 '\000', direction = 0 '\000', field_0x16 = 0 '\000', field_0x17 = 0 '\000', spriteSettings = {raw = 1 '\001', b = {draw = 1, ss2 = 0, ss3 = 0, shadow = 0, flipX = 0, flipY = 0}}, spriteRendering = {b0 = 0, alphaBlend = 0, b2 = 0, b3 = 1}, palette = {raw = 17 '\021', b = {b0 = 1 '\001', b4 = 1 '\001'}}, spriteOrientation = {b0 = 0, b1 = 0, flipY = 1}, field_0x1c = 0 '\000', field_0x1d = 0 '\000', frameIndex = 0 '\000', lastFrameIndex = 0 '\000', field_0x20 = 0, speed = 0, spriteAnimation = "\004\001", spritePriority = {b0 = 4 '\004', b1 = 0 '\000', b2 = 0 '\000'}, collisions = 0, x = {WORD = 121634816, HALF = {LO = 0, HI = 1856}, HALF_U = {LO = 0, HI = 1856}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 64 '@', byte3 = 7 '\a'}}, y = {WORD = 103677952, HALF = {LO = 0, HI = 1582}, HALF_U = {LO = 0, HI = 1582}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 46 '.', byte3 = 6 '\006'}}, height = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, collisionLayer = 2 '\002', interactType = 0 '\000', field_0x3a = 0 '\000', flags2 = 128 '\200', field_0x3c = 71 'G', iframes = 0 '\000', field_0x3e = 0 '\000', damageType = 1 '\001', field_0x40 = 68 'D', bitfield = 0 '\000', field_0x42 = 0 '\000', field_0x43 = 0 '\000', field_0x44 = 0 '\000', currentHealth = 0 '\000', field_0x46 = 0, hitbox = 0x80fd180 <gUnk_080FD180>, field_0x4c = 0x0, parent = 0x0, attachedEntity = 0x0, animIndex = 0 '\000', frameDuration = 255 '\377', frames = {all = 128 '\200', b = {f0 = 0 '\000', f1 = 0 '\000', f2 = 0 '\000', f3 = 1 '\001'}}, frameSpriteSettings = 0 '\000', animPtr = 0x812148c <gUnk_08121488+4>, spriteVramOffset = 384, spriteOffsetX = 0 '\000', spriteOffsetY = 0 '\000', myHeap = 0x0, field_0x68 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6c = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6e = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x70 = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x74 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x76 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x78 = {HWORD = 6, HALF = {LO = 6 '\006', HI = 0 '\000'}}, field_0x7a = {HWORD = 51256, HALF = {LO = 56 '8', HI = 200 '\310'}}, field_0x7c = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x80 = {HWORD = 368, HALF = {LO = 112 'p', HI = 1 '\001'}}, field_0x82 = {HWORD = 62, HALF = {LO = 62 '>', HI = 0 '\000'}}, cutsceneBeh = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x86 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}}"""))
#pprint(parse_result(r"""{prev = 0x30016b0, next = 0x3001628, kind = 96 '`', id = 17 '\021', type = 0 '\000', type2 = 3 '\003', action = 96 '`', subAction = 17 '\021', actionDelay = 0 '\000', field_0xf = 3 '\003', flags = 128 '\200', scriptedScene = 13 '\r', scriptedScene2 = 3 '\003', spriteIndex = 768, animationState = 128 '\200', direction = 61 '=', field_0x16 = 0 '\000', field_0x17 = 3 '\003', spriteSettings = {raw = 136 '\210', b = {draw = 0, ss2 = 0, ss3 = 1, shadow = 0, flipX = 0, flipY = 1}}, spriteRendering = {b0 = 1, alphaBlend = 3, b2 = 3, b3 = 0}, palette = {raw = 0 '\000', b = {b0 = 0 '\000', b4 = 0 '\000'}}, spriteOrientation = {b0 = 1, b1 = 1, flipY = 0}, field_0x1c = 136 '\210', field_0x1d = 61 '=', frameIndex = 0 '\000', lastFrameIndex = 3 '\003', field_0x20 = 50337864, speed = 6216, spriteAnimation = "\000\003\230", spritePriority = {b0 = 5 '\005', b1 = 7 '\a', b2 = 0 '\000'}, collisions = 768, x = {WORD = 50347416, HALF = {LO = 15768, HI = 768}, HALF_U = {LO = 15768, HI = 768}, BYTES = {byte0 = 152 '\230', byte1 = 61 '=', byte2 = 0 '\000', byte3 = 3 '\003'}}, y = {WORD = 50338680, HALF = {LO = 7032, HI = 768}, HALF_U = {LO = 7032, HI = 768}, BYTES = {byte0 = 120 'x', byte1 = 27 '\033', byte2 = 0 '\000', byte3 = 3 '\003'}}, height = {WORD = 33763984, HALF = {LO = 12944, HI = 515}, HALF_U = {LO = 12944, HI = 515}, BYTES = {byte0 = 144 '\220', byte1 = 50 '2', byte2 = 3 '\003', byte3 = 2 '\002'}}, collisionLayer = 240 '\360', interactType = 26 '\032', field_0x3a = 0 '\000', flags2 = 3 '\003', field_0x3c = 88 'X', iframes = 25 '\031', field_0x3e = 0 '\000', damageType = 3 '\003', field_0x40 = 208 '\320', bitfield = 51 '3', field_0x42 = 3 '\003', field_0x43 = 2 '\002', field_0x44 = 208 '\320', currentHealth = 51 '3', field_0x46 = 515, hitbox = 0x4, field_0x4c = 0x10, parent = 0x0, attachedEntity = 0x0, animIndex = 0 '\000', frameDuration = 0 '\000', frames = {all = 0 '\000', b = {f0 = 0 '\000', f1 = 0 '\000', f2 = 0 '\000', f3 = 0 '\000'}}, frameSpriteSettings = 0 '\000', animPtr = 0x0, spriteVramOffset = 9908, spriteOffsetX = 0 '\000', spriteOffsetY = 8 '\b', myHeap = 0x3003db8, field_0x68 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6c = {HWORD = 32444, HALF = {LO = 188 '\274', HI = 126 '~'}}, field_0x6e = {HWORD = 768, HALF = {LO = 0 '\000', HI = 3 '\003'}}, field_0x70 = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x74 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x76 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x78 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7c = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x80 = {HWORD = 1, HALF = {LO = 1 '\001', HI = 0 '\000'}}, field_0x82 = {HWORD = 65280, HALF = {LO = 0 '\000', HI = 255 '\377'}}, cutsceneBeh = {HWORD = 49152, HALF = {LO = 0 '\000', HI = 192 '\300'}}, field_0x86 = {HWORD = 2065, HALF = {LO = 17 '\021', HI = 8 '\b'}}}"""))
#print(parse_result(r"""{prev = 0x3003d78, next = 0x3003d78, kind = 1 '\001', id = 0 '\000', type = 0 '\000', type2 = 0 '\000', action = 1 '\001', subAction = 0 '\000', actionDelay = 4 '\004', field_0xf = 0 '\000', flags = 160 '\240', scriptedScene = 1 '\001', scriptedScene2 = 1 '\001', spriteIndex = 1, animationState = 6 '\006', direction = 255 '\377', field_0x16 = 32 ' ', field_0x17 = 0 '\000', spriteSettings = {raw = 83 'S', b = {draw = 3, ss2 = 0, ss3 = 0, shadow = 1, flipX = 1, flipY = 0}}, spriteRendering = {b0 = 0, alphaBlend = 0, b2 = 0, b3 = 2}, palette = {raw = 102 'f', b = {b0 = 6 '\006', b4 = 6 '\006'}}, spriteOrientation = {b0 = 0, b1 = 0, flipY = 2}, field_0x1c = 0 '\000', field_0x1d = 0 '\000', frameIndex = 1 '\001', lastFrameIndex = 1 '\001', field_0x20 = 0, speed = 320, spriteAnimation = "\002\000\001", spritePriority = {b0 = 4 '\004', b1 = 1 '\001', b2 = 0 '\000'}, collisions = 0, x = {WORD = 138056704, HALF = {LO = -27648, HI = 2106}, HALF_U = {LO = 37888, HI = 2106}, BYTES = {byte0 = 0 '\000', byte1 = 148 '\224', byte2 = 58 ':', byte3 = 8 '\b'}}, y = {WORD = 119155712, HALF = {LO = 11264, HI = 1818}, HALF_U = {LO = 11264, HI = 1818}, BYTES = {byte0 = 0 '\000', byte1 = 44 ',', byte2 = 26 '\032', byte3 = 7 '\a'}}, height = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, collisionLayer = 1 '\001', interactType = 0 '\000', field_0x3a = 0 '\000', flags2 = 8 '\b', field_0x3c = 0 '\000', iframes = 0 '\000', field_0x3e = 0 '\000', damageType = 121 'y', field_0x40 = 0 '\000', bitfield = 0 '\000', field_0x42 = 0 '\000', field_0x43 = 0 '\000', field_0x44 = 0 '\000', currentHealth = 34 '"', field_0x46 = 0, hitbox = 0x8114f88 <gUnk_08114F88>, field_0x4c = 0x0, parent = 0x0, attachedEntity = 0x0, animIndex = 3 '\003', frameDuration = 11 '\v', frames = {all = 128 '\200', b = {f0 = 0 '\000', f1 = 0 '\000', f2 = 0 '\000', f3 = 1 '\001'}}, frameSpriteSettings = 64 '@', animPtr = 0x8004af1 <gUnk_08004AF1>, spriteVramOffset = 352, spriteOffsetX = 0 '\000', spriteOffsetY = 0 '\000', myHeap = 0x0, field_0x68 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6c = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6e = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x70 = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x74 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x76 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x78 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7c = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x80 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x82 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, cutsceneBeh = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x86 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}}"""))
#print(parse_result(r"""{prev = 0x3001958, next = 0x3001a68, kind = 3 '\003', id = 0 '\000', type = 1 '\001', type2 = 0 '\000', action = 2 '\002', subAction = 0 '\000', actionDelay = 39 '\'', field_0xf = 0 '\000', flags = 129 '\201', scriptedScene = 0 '\000', scriptedScene2 = 0 '\000', spriteIndex = 174, animationState = 3 '\003', direction = 24 '\030', field_0x16 = 0 '\000', field_0x17 = 0 '\000', spriteSettings = {raw = 17 '\021', b = {draw = 1, ss2 = 0, ss3 = 0, shadow = 1, flipX = 0, flipY = 0}}, spriteRendering = {b0 = 0, alphaBlend = 0, b2 = 0, b3 = 2}, palette = {raw = 17 '\021', b = {b0 = 1 '\001', b4 = 1 '\001'}}, spriteOrientation = {b0 = 0, b1 = 0, flipY = 2}, field_0x1c = 18 '\022', field_0x1d = 0 '\000', frameIndex = 5 '\005', lastFrameIndex = 4 '\004', field_0x20 = 0, speed = 96, spriteAnimation = "\004\001", spritePriority = {b0 = 4 '\004', b1 = 3 '\003', b2 = 0 '\000'}, collisions = 0, x = {WORD = 71622656, HALF = {LO = -8192, HI = 1092}, HALF_U = {LO = 57344, HI = 1092}, BYTES = {byte0 = 0 '\000', byte1 = 224 '\340', byte2 = 68 'D', byte3 = 4 '\004'}}, y = {WORD = 123322368, HALF = {LO = -16384, HI = 1881}, HALF_U = {LO = 49152, HI = 1881}, BYTES = {byte0 = 0 '\000', byte1 = 192 '\300', byte2 = 89 'Y', byte3 = 7 '\a'}}, height = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, collisionLayer = 1 '\001', interactType = 0 '\000', field_0x3a = 0 '\000', flags2 = 15 '\017', field_0x3c = 0 '\000', iframes = 0 '\000', field_0x3e = 0 '\000', damageType = 25 '\031', field_0x40 = 65 'A', bitfield = 0 '\000', field_0x42 = 0 '\000', field_0x43 = 0 '\000', field_0x44 = 0 '\000', currentHealth = 3 '\003', field_0x46 = 0, hitbox = 0x80fd150 <gUnk_080FD150>, field_0x4c = 0x0, parent = 0x0, attachedEntity = 0x0, animIndex = 3 '\003', frameDuration = 12 '\f', frames = {all = 192 '\300', b = {f0 = 0 '\000', f1 = 0 '\000', f2 = 1 '\001', f3 = 1 '\001'}}, frameSpriteSettings = 64 '@', animPtr = 0x80ca19b <gUnk_080CA19B>, spriteVramOffset = 384, spriteOffsetX = 0 '\000', spriteOffsetY = 0 '\000', myHeap = 0x0, field_0x68 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6c = {HWORD = 1160, HALF = {LO = 136 '\210', HI = 4 '\004'}}, field_0x6e = {HWORD = 4114, HALF = {LO = 18 '\022', HI = 16 '\020'}}, field_0x70 = {WORD = 115344384, HALF = {LO = 1024, HI = 1760}, HALF_U = {LO = 1024, HI = 1760}, BYTES = {byte0 = 0 '\000', byte1 = 4 '\004', byte2 = 224 '\340', byte3 = 6 '\006'}}, field_0x74 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x76 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x78 = {HWORD = 3843, HALF = {LO = 3 '\003', HI = 15 '\017'}}, field_0x7a = {HWORD = 256, HALF = {LO = 0 '\000', HI = 1 '\001'}}, field_0x7c = {WORD = 269615104, HALF = {LO = 0, HI = 4114}, HALF_U = {LO = 0, HI = 4114}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 18 '\022', byte3 = 16 '\020'}}, field_0x80 = {HWORD = 104, HALF = {LO = 104 'h', HI = 0 '\000'}}, field_0x82 = {HWORD = 648, HALF = {LO = 136 '\210', HI = 2 '\002'}}, cutsceneBeh = {HWORD = 16, HALF = {LO = 16 '\020', HI = 0 '\000'}}, field_0x86 = {HWORD = 560, HALF = {LO = 48 '0', HI = 2 '\002'}}}"""))
#print(parse_result(r"""{prev = 0x3001a68, next = 0x3003da0, kind = 9 '\t', id = 40 '(', type = 1 '\001', type2 = 0 '\000', action = 1 '\001', subAction = 0 '\000', actionDelay = 3 '\003', field_0xf = 95 '_', flags = 0 '\000', scriptedScene = 1 '\001', scriptedScene2 = 1 '\001', spriteIndex = 0, animationState = 0 '\000', direction = 0 '\000', field_0x16 = 0 '\000', field_0x17 = 0 '\000', spriteSettings = {raw = 0 '\000', b = {draw = 0, ss2 = 0, ss3 = 0, shadow = 0, flipX = 0, flipY = 0}}, spriteRendering = {b0 = 0, alphaBlend = 0, b2 = 0, b3 = 0}, palette = {raw = 0 '\000', b = {b0 = 0 '\000', b4 = 0 '\000'}}, spriteOrientation = {b0 = 0, b1 = 0, flipY = 0}, field_0x1c = 0 '\000', field_0x1d = 0 '\000', frameIndex = 0 '\000', lastFrameIndex = 0 '\000', field_0x20 = 50338000, speed = 6488, spriteAnimation = "\000", <incomplete sequence \340>, spritePriority = {b0 = 1 '\001', b1 = 3 '\003', b2 = 0 '\000'}, collisions = 768, x = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, y = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, height = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, collisionLayer = 0 '\000', interactType = 0 '\000', field_0x3a = 0 '\000', flags2 = 0 '\000', field_0x3c = 0 '\000', iframes = 0 '\000', field_0x3e = 0 '\000', damageType = 0 '\000', field_0x40 = 0 '\000', bitfield = 0 '\000', field_0x42 = 0 '\000', field_0x43 = 0 '\000', field_0x44 = 0 '\000', currentHealth = 0 '\000', field_0x46 = 0, hitbox = 0x0, field_0x4c = 0x0, parent = 0x0, attachedEntity = 0x0, animIndex = 0 '\000', frameDuration = 0 '\000', frames = {all = 0 '\000', b = {f0 = 0 '\000', f1 = 0 '\000', f2 = 0 '\000', f3 = 0 '\000'}}, frameSpriteSettings = 0 '\000', animPtr = 0x0, spriteVramOffset = 0, spriteOffsetX = 0 '\000', spriteOffsetY = 0 '\000', myHeap = 0x0, field_0x68 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6c = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x6e = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x70 = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x74 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x76 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x78 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7a = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x7c = {WORD = 0, HALF = {LO = 0, HI = 0}, HALF_U = {LO = 0, HI = 0}, BYTES = {byte0 = 0 '\000', byte1 = 0 '\000', byte2 = 0 '\000', byte3 = 0 '\000'}}, field_0x80 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x82 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, cutsceneBeh = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}, field_0x86 = {HWORD = 0, HALF = {LO = 0 '\000', HI = 0 '\000'}}}"""))