from pathlib import Path
from html import escape
from functools import lru_cache
import json, base64, shutil
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
import cairosvg
from PIL import Image
A=Path(__file__).resolve().parent
INK='#151714'; PAPER='#F5F7F2'; ACCENT='#C4F25A'
@lru_cache(None)
def font(weight):
    return instantiateVariableFont(TTFont(A/'source/AzeretMono.ttf'),{'wght':weight})
@lru_cache(None)
def glyph(c,weight):
    f=font(weight); gs=f.getGlyphSet(); name=f.getBestCmap()[ord(c)]
    pen=SVGPathPen(gs); gs[name].draw(pen)
    return pen.getCommands(), gs[name].width

def text(s,x,y,size,color=INK,weight=400,tracking=0):
    paths=[]; offset=0
    for c in s:
        d,w=glyph(c,weight)
        paths.append(f'<path transform="translate({offset:.3f} 0)" d="{d}"/>')
        offset+=w+tracking*1000/size
    return f'<g aria-label="{escape(s)}" fill="{color}" transform="translate({x} {y}) scale({size/1000} {-size/1000})">'+''.join(paths)+'</g>'

def wordmark(x,y,size,color):
    # Optical spacing in font units; the x has a 48-unit vertical cut.
    offsets=[0,594,1194,1824]; paths=[]
    for c,offset in zip('ctxr',offsets):
        d,w=glyph(c,650)
        if c=='x':
            # Two outlined halves preserve the crossing silhouette with a transparent slit.
            pts=[(413.417,285.833),(599.833,0),(435.583,0),(399.667,52.583),(322.25,178.5),(244.75,52.5),(208.833,0),(49.333,0),(233.75,283),(56.75,555),(220,555),(246.417,517.083),(323.917,390.333),(401.417,517.167),(427.833,555),(588.25,555)]
            def half(bound,left):
                result=[]
                for p,q in zip(pts,pts[1:]+pts[:1]):
                    inside=lambda v: v[0]<=bound if left else v[0]>=bound
                    if inside(p): result.append(p)
                    if inside(p)!=inside(q):
                        t=(bound-p[0])/(q[0]-p[0]); result.append((bound,p[1]+t*(q[1]-p[1])))
                return 'M'+'L'.join(f'{a:.3f} {b:.3f}' for a,b in result)+'Z'
            d=half(298,True)+half(346,False)
        paths.append(f'<path transform="translate({offset} 0)" d="{d}"/>')
    return f'<g aria-label="ctxr" fill="{color}" transform="translate({x} {y}) scale({size/1000} {-size/1000})">'+''.join(paths)+'</g>'

def svg(w,h,body,title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{body}</svg>\n'

def export(name,w,h,body,title='ctxr',sizes=None):
    s=svg(w,h,body,title); (A/f'{name}.svg').write_text(s)
    for width in sizes or [w]:
        suffix=f'-{width}' if sizes else ''
        cairosvg.svg2png(bytestring=s.encode(),write_to=str(A/f'{name}{suffix}.png'),output_width=width)
    return s

def rect(x,y,w,h,color):
    return f'<path fill="{color}" d="M{x} {y}h{w}v{h}h{-w}Z"/>'

for theme,fg in [('light',INK),('dark',PAPER),('accent',ACCENT)]:
    name='logo' if theme=='light' else f'logo-{theme}'
    export(name,512,180,wordmark(8,143,210,fg),sizes=[512,1024])
export('icon',512,512,rect(0,0,512,512,ACCENT)+wordmark(41,314,180,INK))
fav=svg(32,32,rect(0,0,32,32,ACCENT)+wordmark(1,20,12.5,INK),'ctxr')
(A/'favicon.svg').write_text(fav)
cairosvg.svg2png(bytestring=fav.encode(),write_to=str(A/'favicon.png'),output_width=32)
from io import BytesIO
large=cairosvg.svg2png(bytestring=fav.encode(),output_width=256)
Image.open(BytesIO(large)).save(A/'favicon.ico',sizes=[(n,n) for n in (16,32,48,64,128,256)])
data='data:image/jpeg;base64,'+base64.b64encode((A/'source/frame.jpg').read_bytes()).decode()
timestamp=json.loads((A/'source/sample.json').read_text())['timestamp']
def frame(x,y,w,h):
    return f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="160 0 960 720"><image width="1280" height="720" xlink:href="{data}"/></svg>'
def stamp(x,y):
    return rect(x,y,108,36,ACCENT)+text(timestamp,x+14,y+25,20,INK,500)
for theme,bg,fg in [('dark',INK,PAPER),('light',PAPER,INK)]:
    body=rect(0,0,1280,640,bg)
    body+=text('Context from video,',60,125,38,fg,400,-1.0)+text('for agents.',60,177,38,fg,400,-1.0)
    body+=wordmark(42,564,260,ACCENT if theme=='dark' else INK)
    body+=frame(704,48,512,384)
    body+=stamp(704,451)+text('README.md',1088,476,18,fg,400)
    body+=text('Never gonna',704,548,32,fg,400,-.6)+text('give you up',704,591,32,fg,400,-.6)
    export('social-preview' if theme=='dark' else 'social-preview-light',1280,640,body,'ctxr: Context from video, for agents.')
    body=rect(0,0,1600,400,bg)
    body+=wordmark(42,236,208,ACCENT if theme=='dark' else INK)
    body+=text('Context from video,',56,303,25,fg,400,-.6)+text('for agents.',56,342,25,fg,400,-.6)
    body+=frame(688,40,416,312)
    body+=stamp(1148,64)
    body+=text('Never gonna',1148,194,31,fg,400,-.6)+text('give you up',1148,237,31,fg,400,-.6)
    body+=text('README.md',1148,337,17,fg,400)
    export('banner' if theme=='dark' else 'banner-light',1600,400,body,'ctxr: Context from video, for agents.')
