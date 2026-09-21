"""Reproduce the outlined artwork and local raster exports. See README.md."""
from pathlib import Path
from html import escape
import io
import sys
import xml.etree.ElementTree as ET

import cairosvg
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'src'))
from ctxr.cli import render

INK, PAPER, ACCENT = '#242722', '#F4EEDF', '#C65336'
FONT = ROOT / 'source/AzeretMono.ttf'
FONTS = {w: instantiateVariableFont(TTFont(FONT), {'wght': w}) for w in (400, 500, 600)}
MARK = 'M8 16H64L58 28H20V68H38L32 80H8Z M72 16H88V28H66Z M60 42H88V54H54Z M48 68H76V80H42Z'
SAMPLE = render('VIDEOID', {'title': 'ctxr output example'}, 'illustrative narration',
                [{'t': 32, 'file': '0005_00m32s.jpg', 'segments': [{'text': 'The folder is the state; there is no database.'}]}])


def rect(x, y, w, h, fill):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def text(value, x, y, size, fill=INK, weight=400, tracking=0):
    font = FONTS[weight]
    glyphs, cmap, upem = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm
    result, cursor = [], 0
    for char in value:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        if pen.getCommands():
            result.append(f'<path transform="translate({cursor:g} 0)" d="{pen.getCommands()}"/>')
        cursor += font['hmtx'][name][0] + tracking * upem / size
    return f'<g aria-label="{escape(value, quote=True)}" fill="{fill}" transform="translate({x} {y}) scale({size/upem} {-size/upem})">' + ''.join(result) + '</g>'


def mark(x, y, size, fill=ACCENT):
    return f'<path fill="{fill}" transform="translate({x} {y}) scale({size/96})" d="{MARK}"/>'


def wordmark(x, y, scale=1, fill=INK):
    # Optical advances replace the font's fixed pitch; x is original cut geometry.
    c = text('c', 0, 0, 100, fill, 600)
    t = text('t', 62, 0, 100, fill, 600)
    r = text('r', 188, 0, 100, fill, 600)
    cut_x = '<path d="M0 -54H15L27 -37L18 -27Z M29 -17L38 -27L57 0H42Z M42 -54H57L15 0H0Z"/>'
    return f'<g transform="translate({x} {y}) scale({scale})">{c}{t}<g fill="{fill}" transform="translate(127 0)">{cut_x}</g>{r}</g>'


def svg(w, h, body, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title, quote=True)}"><title>{escape(title)}</title>{body}</svg>\n'


def save_svg(name, w, h, body, title):
    value = svg(w, h, body, title)
    (ROOT / name).write_text(value)
    return value


def png(value, name, width, height):
    data = cairosvg.svg2png(bytestring=value.encode(), output_width=width, output_height=height)
    image = Image.open(io.BytesIO(data))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Source', 'Locally rasterized vector artwork; assets/generate.py; Azeret Mono under SIL OFL 1.1.')
    image.save(ROOT / name, optimize=True, pnginfo=metadata)


def frame(x, y, width):
    # Exact excerpt emitted by ctxr's renderer, with typographic line wrapping.
    scale = width / 560
    heading = next(line for line in SAMPLE.splitlines() if line.startswith('### '))
    image_line = next(line for line in SAMPLE.splitlines() if line.startswith('!['))
    narration = SAMPLE.splitlines()[-1]
    content = rect(0, 0, 560, 266, PAPER)
    content += text('## Walkthrough', 28, 42, 20, INK, 600)
    content += text(heading, 28, 100, 14, INK, 500)
    content += text(image_line, 28, 135, 18, INK)
    first, second = narration.split('; ')
    content += text(first + ';', 28, 196, 21, INK)
    content += text(second, 28, 228, 21, INK)
    return f'<g transform="translate({x} {y}) scale({scale})">{content}</g>'


def build():
    logo = save_svg('logo.svg', 360, 96, mark(0, 0, 96) + wordmark(106, 75, .96, ACCENT), 'ctxr: context from video, for agents')
    symbol = save_svg('logo-mark.svg', 96, 96, mark(0, 0, 96), 'ctxr cut-frame mark')
    for width in (512, 1024):
        png(logo, f'logo-{width}.png', width, round(width * 96 / 360))
        png(symbol, f'logo-mark-{width}.png', width, width)
    icon = svg(512, 512, rect(0, 0, 512, 512, PAPER) + mark(40, 40, 432), 'ctxr icon')
    png(icon, 'icon.png', 512, 512)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    Image.open(ROOT / 'icon.png').save(ROOT / 'favicon.ico', sizes=[(n, n) for n in sizes])

    # An editorial diptych: the identity on paper, the walkthrough on ink.
    social = rect(0, 0, 1280, 640, INK)
    social += f'<path d="M0 0H736L416 640H0Z" fill="{PAPER}"/>'
    social += mark(54, 55, 120)
    social += wordmark(48, 330, 1.95)
    social += text('Context from', 62, 422, 33, INK, 500, -0.3)
    social += text('video, for agents.', 62, 468, 33, INK, 500, -0.3)
    # The excerpt itself is the composition; no browser shell or footer bar.
    social += text('00:32', 764, 160, 112, PAPER, 400, -2)
    social += frame(678, 224, 548)
    social += text('Illustrative walkthrough', 678, 552, 20, PAPER)
    social_svg = save_svg('source/social-preview.svg', 1280, 640, social, 'ctxr. Context from video, for agents. Sample walkthrough at 00:32 with Markdown frame and narration.')
    png(social_svg, 'social-preview.png', 1280, 640)

    banner = rect(0, 0, 1600, 400, INK)
    banner += f'<path d="M0 0H720L520 400H0Z" fill="{PAPER}"/>'
    banner += mark(42, 35, 96)
    banner += wordmark(158, 165, 1.78)
    banner += text('Context from video,', 56, 280, 34, INK, 500, -.3)
    banner += text('for agents.', 56, 327, 34, INK, 500, -.3)
    banner += text('00:32', 700, 131, 64, PAPER, 400, -1)
    banner += rect(704, 157, 48, 5, ACCENT)
    banner += text('Illustrative', 704, 225, 20, PAPER)
    banner += text('walkthrough', 704, 257, 20, PAPER)
    banner += frame(1010, 90, 542)
    banner_svg = save_svg('source/banner.svg', 1600, 400, banner, 'ctxr. Context from video, for agents. Sample walkthrough at 00:32: The folder is the state; there is no database.')
    png(banner_svg, 'banner.png', 1600, 400)

    (ROOT / 'source/frames').mkdir(exist_ok=True)
    sample_frame = svg(560, 266, frame(0, 0, 560), 'ctxr example output folder')
    data = cairosvg.svg2png(bytestring=sample_frame.encode(), output_width=1280, output_height=608)
    Image.open(io.BytesIO(data)).convert('RGB').save(ROOT / 'source/frames/0005_00m32s.jpg', quality=95)
    (ROOT / 'source/walkthrough.md').write_text(SAMPLE)
    verify()


def verify():
    expected = {'social-preview.png': (1280, 640), 'banner.png': (1600, 400), 'icon.png': (512, 512)}
    expected.update({f'logo-mark-{n}.png': (n, n) for n in (512, 1024)})
    expected.update({f'logo-{n}.png': (n, round(n * 96 / 360)) for n in (512, 1024)})
    for name, size in expected.items():
        with Image.open(ROOT / name) as image:
            assert image.size == size, (name, image.size, size)
            image.verify()
    for name in ('logo.svg', 'logo-mark.svg', 'source/banner.svg', 'source/social-preview.svg'):
        tree = ET.parse(ROOT / name)
        assert not tree.findall('.//{http://www.w3.org/2000/svg}text'), name
        assert not tree.findall('.//{http://www.w3.org/2000/svg}image'), name
    with Image.open(ROOT / 'favicon.ico') as image:
        assert image.ico.sizes() == {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)}
    assert '### 00:32' in (ROOT / 'source/walkthrough.md').read_text()
    print('Verified all dimensions, seven ICO sizes, self-contained outlined SVGs, and sample timestamp.')


if __name__ == '__main__':
    verify() if '--check' in sys.argv else build()
