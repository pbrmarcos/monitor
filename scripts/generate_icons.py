"""Generate original geometric Monitor icons without external image tooling."""
import struct
import zlib
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'app/desktop/src-tauri/icons'
root.mkdir(parents=True, exist_ok=True)

def pixels(size):
    result = bytearray()
    for y in range(size):
        for x in range(size):
            a, b = x / size, y / size
            mark = (0.23 < a < 0.46 and 0.44 < b < 0.73) or (0.49 < a < 0.73 and 0.23 < b < 0.51)
            result.extend((0, 215, 236, 255) if mark else (13, 33, 58, 255))
    return bytes(result)

def chunk(kind, payload):
    return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)

size = 256
rgba = pixels(size)
raw = b''.join(b'\0' + rgba[y*size*4:(y+1)*size*4] for y in range(size))
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size,size,8,6,0,0,0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND',b'')
(root / 'icon.png').write_bytes(png)
(root / 'icon.ico').write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
(root / 'tray.rgba').write_bytes(pixels(32))
