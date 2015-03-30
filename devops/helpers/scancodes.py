#    Copyright 2013 - 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# Based on http://www.win.tue.nl/~aeb/linux/kbd/scancodes-1.html
# Scancodes < 0x80 - key presses, > 0x80 - key releases
SCANCODES = {
    '1': 0x02,
    '2': 0x03,
    '3': 0x04,
    '4': 0x05,
    '5': 0x06,
    '6': 0x07,
    '7': 0x08,
    '8': 0x09,
    '9': 0x0a,
    '0': 0x0b,
    '-': 0x0c,
    '=': 0x0d,

    'q': 0x10,
    'w': 0x11,
    'e': 0x12,
    'r': 0x13,
    't': 0x14,
    'y': 0x15,
    'u': 0x16,
    'i': 0x17,
    'o': 0x18,
    'p': 0x19,

    'Q': (0x2a, 0x10),
    'W': (0x2a, 0x11),
    'E': (0x2a, 0x12),
    'R': (0x2a, 0x13),
    'T': (0x2a, 0x14),
    'Y': (0x2a, 0x15),
    'U': (0x2a, 0x16),
    'I': (0x2a, 0x17),
    'O': (0x2a, 0x18),
    'P': (0x2a, 0x19),

    'a': 0x1e,
    's': 0x1f,
    'd': 0x20,
    'f': 0x21,
    'g': 0x22,
    'h': 0x23,
    'j': 0x24,
    'k': 0x25,
    'l': 0x26,

    'A': (0x2a, 0x1e),
    'S': (0x2a, 0x1f),
    'D': (0x2a, 0x20),
    'F': (0x2a, 0x21),
    'G': (0x2a, 0x22),
    'H': (0x2a, 0x23),
    'J': (0x2a, 0x24),
    'K': (0x2a, 0x25),
    'L': (0x2a, 0x26),

    ';': 0x27,
    '"': (0x2a, 0x28),
    '\'': 0x28,

    '\\': 0x2b,
    '|': (0x2a, 0x2b),

    '[': 0x1a,
    ']': 0x1b,
    '<': (0x2a, 0x33),
    '>': (0x2a, 0x34),
    '?': (0x2a, 0x35),
    '$': (0x2a, 0x05),
    '+': (0x2a, 0x0d),

    'z': 0x2c,
    'x': 0x2d,
    'c': 0x2e,
    'v': 0x2f,
    'b': 0x30,
    'n': 0x31,
    'm': 0x32,

    'Z': (0x2a, 0x2c),
    'X': (0x2a, 0x2d),
    'C': (0x2a, 0x2e),
    'V': (0x2a, 0x2f),
    'B': (0x2a, 0x30),
    'N': (0x2a, 0x31),
    'M': (0x2a, 0x32),

    ',': 0x33,
    '.': 0x34,
    '/': 0x35,
    ':': (0x2a, 0x27),
    '%': (0x2a, 0x06),
    '_': (0x2a, 0x0c),
    '&': (0x2a, 0x08),
    '(': (0x2a, 0x0a),
    ')': (0x2a, 0x0b),

    ' ': 0x39
}

SPECIALS = {
    '<Enter>': 0x1c,
    '<Return>': 0x1c,
    '<Backspace>': 0x0e,
    '<Spacebar>': 0x39,
    '<Esc>': 0x01,
    '<Tab>': 0x0f,
    '<KillX>': (0x1d, 0x38, 0x0e),
    '<Wait>': ('wait', ),

    '<PageUp>': 0x49,
    '<PageDown>': 0x51,
    '<Home>': 0x47,
    '<End>': 0x4f,
    '<Insert>': 0x52,
    '<Delete>': 0x53,
    '<Left>': 0x4b,
    '<Right>': 0x4d,
    '<Up>': 0x48,
    '<Down>': 0x50,

    '<F1>': 0x3b,
    '<F2>': 0x3c,
    '<F3>': 0x3d,
    '<F4>': 0x3e,
    '<F5>': 0x3f,
    '<F6>': 0x40,
    '<F7>': 0x41,
    '<F8>': 0x42,
    '<F9>': 0x43,
    '<F10>': 0x44,
    '<F11>': 0x57,
    '<F12>': 0x58
}

__all__ = ['from_string']


def iterable(a):
    if a is None:
        return tuple()
    return a if isinstance(a, (tuple, list)) else (a,)


def from_string(s):
    "from_string(s) - Convert string of chars into string of scancodes."

    scancodes = []

    while len(s) > 0:
        if s[0] == '<' and s.find('>') > 0:
            special_end = s.find('>') + 1
            special = s[0:special_end]
            s = s[special_end:]

            codes = SPECIALS.get(special)
        else:
            key = s[0]
            s = s[1:]

            codes = SCANCODES.get(key)

        codes = iterable(codes)
        if len(codes) > 0:
            scancodes.append(codes)

    return scancodes