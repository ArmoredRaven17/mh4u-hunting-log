"""Decode the two uncompressed MH4U .tex v0xA5 formats the build reads:

    format 16, LA4: one byte per texel, luminance in the high nibble, alpha in the low -- the
               cmn_icon equipment atlas;
    format 1, RGBA4444: one little-endian u16 per texel, R in the top nibble -- the cmn_micon
               monster icon atlas.

TEX v0xA5 header (as 3U): 'TEX\\0'; u32 version 0xA5 in the low 12 bits; u32 mips (6 bits) |
width (13) << 6 | height (13) << 19; u32 count (8) | format (8) << 8; mips x u32 offsets; data.
PICA200 layout: 8x8 tiles left to right, top to bottom, texels in Morton (Z) order inside a tile,
memory row 0 at the top.
"""
import struct
import numpy as np


def _morton8():
    m = np.zeros(64, np.int32)
    for i in range(64):
        x = (i & 1) | ((i >> 1) & 2) | ((i >> 2) & 4)
        y = ((i >> 1) & 1) | ((i >> 2) & 2) | ((i >> 3) & 4)
        m[i] = y * 8 + x
    return m


MORTON = _morton8()


def _header(d, fmt):
    assert d[:4] == b'TEX\0', 'not a TEX'
    w1, w2, w3 = struct.unpack_from('<III', d, 4)
    assert w1 & 0xFFF == 0xA5, hex(w1)
    mips, w, h = w2 & 0x3F, (w2 >> 6) & 0x1FFF, (w2 >> 19) & 0x1FFF
    assert (w3 >> 8) & 0xFF == fmt, 'format %d, expected %d' % ((w3 >> 8) & 0xFF, fmt)
    return w, h, 16 + 4 * mips


def _untile(px, w, h):
    out = np.zeros((h, w, 4), np.uint8)
    t = 0
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            blk = np.zeros((64, 4), np.uint8)
            blk[MORTON] = px[t * 64:(t + 1) * 64]
            out[ty:ty + 8, tx:tx + 8] = blk.reshape(8, 8, 4)
            t += 1
    return out


def decode_la4(d):
    w, h, off = _header(d, 16)
    v = np.frombuffer(d[off:off + w * h], np.uint8).astype(np.uint32)
    lum, alpha = (v >> 4) * 17, (v & 15) * 17
    return _untile(np.stack([lum, lum, lum, alpha], 1).astype(np.uint8), w, h)


def decode_rgba4(d):
    w, h, off = _header(d, 1)
    v = np.frombuffer(d[off:off + 2 * w * h], '<u2').astype(np.uint32)
    px = np.stack([(v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15], 1) * 17
    return _untile(px.astype(np.uint8), w, h)
