import struct
import zlib


def png(width=8, height=8, color=(30, 110, 180)):
    def chunk(kind, raw):
        return struct.pack('!I', len(raw)) + kind + raw + struct.pack('!I', zlib.crc32(kind + raw) & 0xffffffff)
    pixels = b''.join(b'\x00' + bytes(color) * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


class Judge:
    def __init__(self, score=1.0, error=None):
        self.score, self.error, self.calls = score, error, 0

    def __call__(self, context, observation):
        from jev_gtw import Assessment
        self.calls += 1
        if self.error:
            raise self.error
        return Assessment(self.score)
