"""Check the published brand files without regenerating them."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from PIL import Image

A = Path(__file__).resolve().parent
for name, size in {
    'banner.png': (1600, 400), 'banner-light.png': (1600, 400),
    'social-preview.png': (1280, 640), 'social-preview-light.png': (1280, 640),
    'icon.png': (512, 512), 'favicon.png': (32, 32),
}.items():
    with Image.open(A / name) as im:
        assert im.size == size, name
        im.verify()
assert (A / 'social-preview.png').stat().st_size < 1_000_000
assert Image.open(A / 'favicon.ico').ico.sizes() == {(n, n) for n in (16, 32, 48, 64, 128, 256)}
ns = {'s': 'http://www.w3.org/2000/svg'}
for file in A.glob('*.svg'):
    root = ET.parse(file).getroot()
    assert not root.findall('.//s:text', ns), file
    for image in root.findall('.//s:image', ns):
        assert image.attrib['{http://www.w3.org/1999/xlink}href'].startswith('data:image/jpeg;base64,')
assert not list(A.glob('logo-mark*'))
meta = json.loads((A / 'source/sample.json').read_text())
assert meta['frame_seconds'] <= meta['transcript']['start'] < meta['next_frame_seconds']
assert hashlib.sha256((A / 'source/frame.jpg').read_bytes()).hexdigest() == meta['frame_sha256']
readme = (A.parent / 'README.md').read_text()
for path in re.findall(r'(?:src|srcset)="(assets/[^\"]+)"', readme):
    assert (A.parent / path.split("?", 1)[0]).is_file(), path
assert 'prefers-color-scheme: dark' in readme and 'prefers-color-scheme: light' in readme
print('Brand dimensions, upload size, outlines, embedded frame, source alignment, favicon sizes and README links verified.')
