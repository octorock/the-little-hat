# Patterns for commonly used bitfields


# spriteOrientation
spriteOrientation = spriteOrientation & 0x3f
    spriteOrientation.flipY = 0

spriteOrientation = spriteOrientation & 0x3f | 0x40
    spriteOrientation.flipY = 1

spriteOrientation = spriteOrientation & 0x3f | 0x80
    spriteOrientation.flipY = 2

spriteOrientation = spriteOrientation | 0xc0
    spriteOrientation.flipY = 3

# spritePriority
spritePriority & 0xf8
    spritePriority.b0 = 0

spritePriority & 0xf8 | 1
    spritePriority.b0 = 1

spritePriority \| 7
    spritePriority.b0 = 7

spritePriority & 199
    spritePriority.b1 = 0

spritePriority & 199 | 8
    spritePriority.b1 = 1

spritePriority & 199 | 0x10
    spritePriority.b1 = 2

spritePriority & 199 | 0x18
    spritePriority.b1 = 3

# spriteRendering
spriteRendering | 3
    spriteRendering.b0 = 3

spriteRendering & 0xf3
    spriteRendering.alphaBlend = 0

spriteRendering & 0xf3 | 4
    spriteRendering.alphaBlend = 1

spriteRendering & 0x3f
    spriteRendering.b3 = 0

spriteRendering & 0x3f | 0x40
    spriteRendering.b3 = 1

spriteRendering & 0x3f | 0x80
    spriteRendering.b3 = 2

spriteRendering | 0xc0
    spriteRendering.b3 = 3


# spriteSettings
spriteSettings & 0xfc | 1
    spriteSettings.draw = 1

spriteSettings & 0xfc | 2
    spriteSettings.draw = 2

spriteSettings & 0xfc | spriteSettings & 3 ^ 1
    spriteSettings.draw ^= 1

spriteSettings | 3
    spriteSettings.draw = 3

spriteSettings | 0x40
    spriteSettings.flipX = 1

spriteSettings | 0x80
    spriteSettings.flipY = 1

 spriteSettings & 0xcf | 0x10
    spriteSettings.shadow = 1