"""Bounded RGB PNG validation and immutable image assets."""
from __future__ import annotations
import dataclasses
import hashlib
import struct
import zlib

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 4 * 1024 * 1024


def validate_png(payload: bytes) -> tuple[int, int]:
    """Accept bounded, metadata-free RGB PNGs used by this controlled pilot."""
    if type(payload) is not bytes or not 57 <= len(payload) <= MAX_IMAGE_BYTES:
        raise ValueError('Image byte bound')
    if payload[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('PNG required')
    offset, chunks, dimensions, compressed = 8, [], None, []
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise ValueError('Truncated PNG')
        size = struct.unpack('!I', payload[offset:offset+4])[0]
        kind = payload[offset+4:offset+8]
        end = offset+12+size
        if end > len(payload) or kind not in {b'IHDR', b'IDAT', b'IEND'}:
            raise ValueError('Unsupported PNG structure or metadata')
        content = payload[offset+8:offset+8+size]
        crc = struct.unpack('!I', payload[offset+8+size:end])[0]
        if zlib.crc32(kind+content) & 0xffffffff != crc:
            raise ValueError('PNG checksum')
        chunks.append(kind)
        if kind == b'IDAT':
            compressed.append(content)
        if kind == b'IHDR':
            if len(chunks) != 1 or len(content) != 13:
                raise ValueError('PNG header')
            width, height, depth, color, compression, filtering, interlace = struct.unpack('!IIBBBBB', content)
            if not (width > 0 and height > 0 and width*height <= MAX_IMAGE_PIXELS):
                raise ValueError('Image pixel bound')
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise ValueError('Only noninterlaced eight-bit RGB PNGs are supported')
            dimensions = width, height
        if kind == b'IEND' and (size != 0 or end != len(payload)):
            raise ValueError('PNG trailing content')
        offset = end
    if chunks[0] != b'IHDR' or chunks[-1] != b'IEND' or not chunks[1:-1] or any(c != b'IDAT' for c in chunks[1:-1]):
        raise ValueError('PNG chunk order')
    # CRC-valid IDAT is not sufficient: extra zlib streams, trailing compressed
    # payloads and oversized decoded data would also cross in the data URL.
    width, height = dimensions
    stride = 1+3*width
    expected = height*stride
    inflater = zlib.decompressobj()
    try:
        pixels = inflater.decompress(b''.join(compressed), expected+1)
    except zlib.error as exc:
        raise ValueError('PNG compression stream') from exc
    if len(pixels) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError('PNG decoded length or trailing compression data')
    if any(pixels[row*stride] > 4 for row in range(height)):
        raise ValueError('PNG row filter')
    return dimensions


@dataclasses.dataclass(frozen=True)
class ImageAsset:
    payload: bytes = dataclasses.field(repr=False)
    sha256: str
    width: int
    height: int

    @classmethod
    def from_bytes(cls, payload):
        width, height = validate_png(payload)
        return cls(payload, hashlib.sha256(payload).hexdigest(), width, height)

