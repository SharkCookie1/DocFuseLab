"""Original editable scientific schematics based on the manuscript mechanism.

Scene coordinates are final publication points. Formulas retain both TeX and
structured math trees for native Office Math export.
"""
from pathlib import Path
import json, math, html, hashlib
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['mathtext.fontset']='stix'
from matplotlib.mathtext import MathTextParser
from matplotlib.font_manager import FontProperties

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'figures'
OUT.mkdir(exist_ok=True,parents=True)
FONTS=ROOT/'figure_sources/fonts'
for suffix,name in [('', 'DejaVuSans'),('-Bold','DejaVuSans-Bold')]:
    pdfmetrics.registerFont(TTFont(name,str(FONTS/f'DejaVuSans{suffix}.ttf')))
INK='#161616'; WHITE='#FFFFFF'; BLUE='#DAE2F5'; GREEN='#E1EFD9'; PEACH='#F8CDAC'; PINK='#F5B7BE'; YELLOW='#FDE694'; PURPLE='#B1AFD4'; GRAY='#E7E6E6'; BLUSH='#F7EAE9'; CREAM='#FAE4D5'
PARSER=MathTextParser('path')

def t(text,normal=False):return {'type':'run','text':text,'normal':normal}
def sub(base,idx):return {'type':'sub','base':base,'sub':idx}
def sup(base,idx):return {'type':'sup','base':base,'sup':idx}
def big(op,low,body):return {'type':'nary','op':op,'sub':low,'body':body}
def f(name,arg):return [t(name),t('('),arg,t(')')]

class Scene:
    def __init__(self,stem,title,h,note):self.stem=stem;self.title=title;self.width=468;self.height=h;self.items=[];self.note=note
    def add(self,kind,**a):a.update(kind=kind,id=f'{self.stem}-{len(self.items)+1:03d}');self.items.append(a);return a
    def text(self,x,y,txt,size=7.3,w=None,bold=False,align='left',color=INK):
        for j,ln in enumerate(txt.split('\n')):
            real=pdfmetrics.stringWidth(ln,'DejaVuSans-Bold' if bold else 'DejaVuSans',size)
            width=real+1.5 if w is None else w
            if real>width+.3:raise ValueError(f'{self.stem} text too wide: {ln}: {real:.1f}>{width}')
            self.add('text',x=x,y=y+j*size*1.28,w=width,h=size*1.4,text=ln,size=size,bold=bold,align=align,color=color)
    def box(self,x,y,w,h,fill=WHITE,r=4,stroke=INK,width=.9,dashed=False):
        self.add('rect',x=x,y=y,w=w,h=h,fill=fill,color=stroke,width=width,r=r,dashed=dashed)
    def path(self,pts,width=2,color=INK,dashed=False,fill='none',closed=False):
        self.add('path',points=pts,width=width,color=color,dashed=dashed,fill=fill,closed=closed)
    def line(self,x1,y1,x2,y2,width=2,color=INK,dashed=False):self.path([[x1,y1],[x2,y2]],width,color,dashed)
    def arrow(self,pts,width=2,color=INK,dashed=False,head=4):
        self.path(pts,width,color,dashed)
        x,y=pts[-1];x0,y0=pts[-2];a=math.atan2(y-y0,x-x0)
        l=[x-head*math.cos(a)+head*.44*math.sin(a),y-head*math.sin(a)-head*.44*math.cos(a)]
        r=[x-head*math.cos(a)-head*.44*math.sin(a),y-head*math.sin(a)+head*.44*math.cos(a)]
        self.path([[x,y],l,r],0,color,fill=color,closed=True)
    def circle(self,x,y,r=6,fill=WHITE,width=.9):self.add('circle',x=x-r,y=y-r,w=r*2,h=r*2,fill=fill,color=INK,width=width)
    def label(self,letter,title,x,y,w):self.text(x,y,letter,8.8,w=10,bold=True);self.text(x+13,y+.5,title,8,w=w-13,bold=True)
    def math(self,x,y,latex,ast,size=8.3,w=None,h=None,align='left'):
        p=PARSER.parse('$'+latex+'$',dpi=72,prop=FontProperties(size=size))
        width=float(p.width)+2 if w is None else w; height=float(p.height)+2 if h is None else h
        if p.width>width+1:raise ValueError(f'{self.stem}: formula {latex} needs {p.width}>{width}')
        if p.height>height+1:raise ValueError(f'{self.stem}: formula {latex} needs height {p.height}>{height}')
        self.add('math',x=x,y=y,w=width,h=height,size=size,latex=latex,ast=ast,align=align,color=INK)
    def stack(self,x,y,w,h,label,fill=BLUE,layers=3):
        for k in reversed(range(layers)):
            self.box(x+3*k,y-3*k,w,h,fill,2,width=.8)
        self.text(x+3,y+h/2-4,label,7.2,w=w-6,align='center')
    def card(self,x,y,w,h,id,lines,fill=BLUE):
        self.box(x,y,w,h,WHITE,3,width=.8)
        self.box(x,y,19,h,fill,3,width=.8)
        self.text(x+1,y+h/2-4,id,7.1,w=17,align='center',bold=True)
        self.text(x+24,y+6,lines,7.0,w=w-29)
    def cells(self,x,y,labels,colors,cw=23,ch=20,gap=3,depth=2):
        for j,(label,col) in enumerate(zip(labels,colors)):
            xx=x+j*(cw+gap)
            if depth:
                self.path([[xx, y],[xx+depth,y-depth],[xx+cw+depth,y-depth],[xx+cw,y]],.65,fill=WHITE,closed=True)
                self.path([[xx+cw,y],[xx+cw+depth,y-depth],[xx+cw+depth,y+ch-depth],[xx+cw,y+ch]],.65,fill=GRAY,closed=True)
            self.box(xx,y,cw,ch,col,0,width=.8)
            self.text(xx,y+ch/2-3.7,label,7.1,w=cw,align='center')
    def export(self):
        data={'stem':self.stem,'title':self.title,'width':468,'height':self.height,'note':self.note,'items':self.items}
        (OUT/f'{self.stem}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        c=canvas.Canvas(str(OUT/f'{self.stem}.pdf'),pagesize=(468,self.height));c.setTitle(self.title);c.setAuthor('')
        svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="468pt" height="{self.height}pt" viewBox="0 0 468 {self.height}">',f'<title>{html.escape(self.title)}</title>','<rect width="100%" height="100%" fill="white"/>']
        for a in self.items:
            k=a['kind'];sw=a.get('width',.9);col=a.get('color',INK);fill=a.get('fill','none')
            c.setStrokeColor(HexColor(col));c.setFillColor(HexColor(fill if fill!='none' else WHITE));c.setLineWidth(sw);c.setDash([3,2] if a.get('dashed') else [])
            dash=' stroke-dasharray="3 2"' if a.get('dashed') else ''
            if k=='rect':
                c.roundRect(a['x'],self.height-a['y']-a['h'],a['w'],a['h'],a['r'],stroke=int(sw>0),fill=int(fill!='none'))
                svg.append(f'<rect id="{a["id"]}" x="{a["x"]}" y="{a["y"]}" width="{a["w"]}" height="{a["h"]}" rx="{a["r"]}" fill="{fill}" stroke="{col}" stroke-width="{sw}"{dash}/>')
            elif k=='circle':
                c.ellipse(a['x'],self.height-a['y']-a['h'],a['x']+a['w'],self.height-a['y'],fill=1,stroke=1)
                svg.append(f'<ellipse id="{a["id"]}" cx="{a["x"]+a["w"]/2}" cy="{a["y"]+a["h"]/2}" rx="{a["w"]/2}" ry="{a["h"]/2}" fill="{fill}" stroke="{col}" stroke-width="{sw}"/>')
            elif k=='path':
                p=c.beginPath();p.moveTo(a['points'][0][0],self.height-a['points'][0][1])
                for x,y in a['points'][1:]:p.lineTo(x,self.height-y)
                if a.get('closed'):p.close()
                c.drawPath(p,stroke=int(sw>0),fill=int(fill!='none'))
                d='M '+' L '.join(f'{x},{y}' for x,y in a['points'])+(' Z' if a.get('closed') else '')
                svg.append(f'<path id="{a["id"]}" d="{d}" fill="{fill}" stroke="{col}" stroke-width="{sw}" stroke-linejoin="round"{dash}/>')
            elif k=='text':
                font='DejaVuSans-Bold' if a['bold'] else 'DejaVuSans';c.setFont(font,a['size']);c.setFillColor(HexColor(col));x=a['x'];yy=a['y']+.82*a['size']
                anchor={'left':'start','center':'middle','right':'end'}[a['align']]
                if a['align']=='center':x+=a['w']/2;c.drawCentredString(x,self.height-yy,a['text'])
                elif a['align']=='right':x+=a['w'];c.drawRightString(x,self.height-yy,a['text'])
                else:c.drawString(x,self.height-yy,a['text'])
                svg.append(f'<text id="{a["id"]}" x="{x}" y="{yy}" font-family="DejaVu Sans" font-size="{a["size"]}" font-weight="{"bold" if a["bold"] else "normal"}" text-anchor="{anchor}" fill="{col}">{html.escape(a["text"])}</text>')
            elif k=='math':
                p=PARSER.parse('$'+a['latex']+'$',dpi=72,prop=FontProperties(size=a['size']))
                ox=a['x']+(a['w']-p.width)/2 if a['align']=='center' else a['x']
                oy=self.height-a['y']-(a['h']-p.height)/2-p.height+p.depth
                svg.append(f'<g id="{a["id"]}" data-latex="{html.escape(a["latex"],quote=True)}">')
                for ff,size,code,gx,gy in p.glyphs:
                    fn='M'+hashlib.sha256(ff.fname.encode()).hexdigest()[:12]
                    if fn not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(fn,ff.fname))
                    c.setFont(fn,size);c.setFillColor(HexColor(INK));c.drawString(ox+gx,oy+gy,chr(code))
                    ital='italic' if 'Italic' in ff.fname or 'Oblique' in ff.fname else 'normal'
                    svg.append(f'<text x="{ox+gx}" y="{self.height-oy-gy}" font-family="{ff.family_name}" font-size="{size}" font-style="{ital}" fill="{INK}">{html.escape(chr(code))}</text>')
                for xx,yy,ww,hh in p.rects:c.rect(ox+xx,oy+yy,ww,hh,stroke=0,fill=1);svg.append(f'<rect x="{ox+xx}" y="{self.height-oy-yy-hh}" width="{ww}" height="{hh}" fill="{INK}"/>')
                svg.append('</g>')
        c.showPage();c.save();svg.append('</svg>');(OUT/f'{self.stem}.svg').write_text('\n'.join(svg),encoding='utf-8')
        return data

scenes=[]

# Figure 1: a concrete source-selection problem, with paired budgeted routes.
s=Scene('Figure_1_Evidence_Selection','Evidence paths exposed by two equal-budget selections',302,'Illustrative names and selections. Source blocks represent original text units, not neural feature tensors. Both displayed packets have three units of equal cost c. The paths show supported information, not observed model outputs.')
s.box(5,5,458,26,GREEN,5);s.text(14,13,'Question: Where was the author of Riverbank born?',8.1,w=445,bold=True)
s.label('a','Candidate sources',7,42,147)
s.box(5,60,147,232,BLUSH,6,width=.8)
for y,ii,tx,col in [(73,'S1','Riverbank was written\nby Lin Zhou.',BLUE),(113,'S2','Lin Zhou was born\nin Haicheng.',GREEN),(153,'S3','Lin Zhou was born\nin Shancheng.',PINK),(193,'S4','Riverbank is a novel.',GRAY),(233,'S5','Lin Zhou received\na literary award.',GRAY)]:s.card(12,y,132,33,ii,tx,col)
s.text(16,276,'Original source units with IDs',7,w=132)
s.label('b','Budgeted packets and retained paths',170,42,290)
s.box(178,60,285,103,BLUE,6,width=.9)
s.box(178,179,285,113,CREAM,6,width=.9)
s.line(154,169,165,169);s.line(165,110,165,234)
s.arrow([[165,110],[177,110]]);s.arrow([[165,234],[177,234]])
s.text(187,69,'Plain set',7.9,w=87,bold=True)
s.math(370,67,r'B=3c',[t('B'),t('='),t('3'),t('c')],9,w=82,h=15,align='center')
s.cells(188,94,['S1','S2','S4'],[BLUE,GREEN,GRAY],cw=24,ch=20)
s.arrow([[270,104],[286,104]],1.8)
s.text(293,94,'One complete path',7.3,w=157)
s.box(188,130,70,22,WHITE,3);s.text(191,137,'Riverbank',7.1,w=64,align='center')
s.arrow([[259,141],[278,141]],1.8)
s.box(281,130,69,22,WHITE,3);s.text(284,137,'Lin Zhou',7.1,w=63,align='center')
s.arrow([[351,141],[370,141]],1.8)
s.box(373,130,80,22,GREEN,3);s.text(376,137,'Haicheng',7.1,w=74,align='center')
s.text(187,188,'Joint preservation',7.9,w=175,bold=True)
s.math(370,186,r'B=3c',[t('B'),t('='),t('3'),t('c')],9,w=82,h=15,align='center')
s.cells(188,214,['S1','S2','S3'],[BLUE,GREEN,PINK],cw=24,ch=20)
s.arrow([[270,224],[286,224]],1.8)
s.text(293,214,'Two complete opposing paths',7.1,w=157)
s.box(188,257,70,22,WHITE,3);s.text(191,264,'Riverbank',7.1,w=64,align='center')
s.arrow([[259,268],[278,268]],1.8);s.box(281,257,69,22,WHITE,3);s.text(284,264,'Lin Zhou',7.1,w=63,align='center')
s.line(351,268,361,268,1.8);s.line(361,247,361,278,1.8)
s.arrow([[361,247],[370,247]],1.8);s.arrow([[361,278],[370,278]],1.8)
s.box(373,236,80,22,GREEN,3);s.text(376,243,'Haicheng',7.1,w=74,align='center')
s.box(373,267,80,22,PINK,3);s.text(376,274,'Shancheng',7.1,w=74,align='center')
scenes.append(s.export())

# Figure 2: top-level architecture plus a genuine expanded structural module.
s=Scene('Figure_2_Method','Source-grounded construction and structural selection',330,'Architecture of the implemented selector. Proposal uses the full pool and up to two existing Document blocks. Accepted witnesses are checked for complete support and pairwise relations. The expanded module retains conservative family unions, enumerates up to 64 family-union seeds, applies budget and active balance constraints, fills by the common priority and ranks the constructed feasible packets. Only original selected source text reaches the reader.')
s.label('a','Source-grounded evidence construction',7,4,454)
s.box(5,24,458,92,BLUSH,6,width=.8)
s.stack(14,51,49,34,'Sources',BLUE,3);s.text(15,92,'Question q',7.2,w=64)
s.arrow([[69,67],[84,67]],1.8)
s.box(89,34,101,71,CREAM,5)
s.text(96,41,'Witness proposals',7.4,w=89,bold=True,align='center')
s.box(96,57,86,18,WHITE,3,width=.7);s.text(98,62,'Whole pool: up to 4',6.9,w=82,align='center')
s.box(96,80,86,18,WHITE,3,width=.7);s.text(98,85,'Up to 2 source blocks',6.8,w=82,align='center')
s.arrow([[192,67],[205,67]],1.8)
s.box(210,34,105,71,GREEN,5);s.text(215,41,'Source checks',7.4,w=95,bold=True,align='center')
s.text(218,59,'Complete support',7.0,w=89);s.text(218,73,'Answer equivalence',7.0,w=89);s.text(218,87,'Pairwise opposition',7.0,w=89)
s.arrow([[317,67],[332,67]],1.8)
s.box(337,34,116,71,PURPLE,5);s.text(342,41,'Accepted family graph',7.3,w=106,bold=True,align='center')
s.circle(366,76,11,BLUE);s.text(361,72,'a',8,w=10,align='center')
s.circle(425,76,11,PINK);s.text(420,72,'b',8,w=10,align='center')
s.line(378,76,413,76,1.7);s.line(393,72,398,80,1.1);s.line(393,80,398,72,1.1)
s.text(349,93,'Unresolved incompatibility',6.7,w=94,align='center')
s.arrow([[395,107],[395,120],[459,120],[459,140],[81,140],[81,151]],1.4)
s.label('b','Expanded structural selection',7,126,432)
s.box(5,145,458,135,WHITE,5,width=1,dashed=True)
s.box(12,153,145,115,BLUE,4,width=.8);s.text(19,160,'Family closure',7.6,w=131,bold=True)
for j,tx in enumerate(['v1','v2','v3','v4']):s.text(65+j*20,179,tx,6.8,w=18,align='center')
for y,tx,bits,col in [(197,'a: W1',[1,1,0,0],BLUE),(213,'a: W2',[1,0,1,0],BLUE),(229,'b: W3',[1,0,0,1],PINK)]:
    s.text(20,y+2,tx,6.9,w=43)
    for j,b in enumerate(bits):s.box(68+j*20,y,11,11,PURPLE if b and col==BLUE else PINK if b else WHITE,0,width=.55)
s.math(21,244,r'U_a=\bigcup_{W\in\mathcal{W}_a}W',[sub(t('U'),t('a')),t('='),big('⋃',[t('W'),t('∈'),sub(t('𝒲'),t('a'))],t('W'))],8.6,w=126,h=22,align='center')
s.arrow([[159,212],[170,212]],1.6)
s.box(175,153,127,115,GREEN,4,width=.8);s.text(182,160,'Feasible union seeds',7.4,w=114,bold=True)
s.text(182,179,'At most 64 seed unions',7,w=114)
s.math(186,197,r'C(S)\leq B',[*f('C',t('S')),t('≤'),t('B')],9,w=105,h=18,align='center')
s.math(180,219,r'z_a(S)=z_b(S)',[sub(t('z'),t('a')),t('(S)='),sub(t('z'),t('b')),t('(S)')],8.7,w=117,h=18,align='center')
s.text(184,246,'Balance when active',7,w=109,align='center')
s.arrow([[304,212],[315,212]],1.6)
s.box(320,153,135,115,YELLOW,4,width=.8);s.text(327,160,'Priority fill and ranking',7.2,w=121,bold=True)
s.text(327,180,'Scan the shared priority',6.9,w=121)
s.cells(329,199,['i1','i2','…','in'],[WHITE,WHITE,WHITE,WHITE],cw=25,ch=16,gap=3,depth=0)
s.text(327,225,'Keep feasible additions',6.9,w=121)
s.text(327,241,'Select by lexicographic rank',6.8,w=121)
s.math(327,251,r'(K,H,R_\pi,-C)',[t('('),t('K'),t(','),t('H'),t(','),sub(t('R'),t('π')),t(','),t('−'),t('C'),t(')')],8.5,w=121,h=16,align='center')
s.label('c','Source-only reading',7,291,162)
s.stack(180,292,104,26,'Selected original text',BLUE,2)
s.arrow([[290,305],[305,305]],1.8)
s.box(310,292,76,26,GREEN,4);s.text(313,301,'Frozen reader',7.4,w=70,align='center')
s.arrow([[388,305],[402,305]],1.8)
s.text(408,288,'Answer /',6.8,w=54);s.text(408,298,'CONFLICT /',6.8,w=54);s.text(408,308,'UNKNOWN',6.8,w=54)
s.arrow([[440,280],[440,285],[234,285],[234,289]],1.4,head=3)
scenes.append(s.export())

# Figure 3: source-level construction rather than a list of cohort counts.
s=Scene('Figure_3_Controlled_Construction','Source-level construction of the confirmation conditions',310,'Illustrative film, person and date. Eligibility uses connected official evidence triples and supporting facts in distinct documents. Original candidate documents remain in each pool. The conflict condition appends a terminal sentence with year shifted by seven; ordinary controls append an unchanged copy. Source titles and presentation status are matched. Conditions contain distinct assigned questions, not paired copies of every question.')
s.label('a','Frozen confirmation construction',7,4,454)
s.box(6,23,92,33,BLUE,4);s.text(12,30,'2WikiMultihopQA',7.1,w=80,align='center');s.text(12,41,'unused questions',6.9,w=80,align='center')
s.arrow([[100,40],[113,40]],1.8)
s.box(118,23,111,33,GREEN,4);s.text(122,30,'Two connected hops',7.1,w=103,align='center');s.text(122,41,'Distinct support documents',6.6,w=103,align='center')
s.arrow([[231,40],[244,40]],1.8)
s.box(249,23,112,33,CREAM,4);s.text(253,30,'Fixed hash order',7.1,w=104,align='center');s.text(253,41,'Question and title exclusions',6.6,w=104,align='center')
s.arrow([[363,40],[376,40]],1.8)
s.box(381,23,80,33,YELLOW,4);s.text(385,30,'300 questions',7.3,w=72,bold=True,align='center');s.text(385,41,'Frozen cohort',6.9,w=72,align='center')
s.box(6,70,455,94,BLUSH,5,width=.8)
s.text(14,77,'Question: On what date was the director of Film A born?',7.6,w=439,bold=True)
s.card(14,97,178,39,'S1','Film A was directed\nby Person B.',BLUE)
s.arrow([[195,116],[212,116]],1.8)
s.card(217,97,181,39,'S2','Person B was born on',GREEN)
s.box(239,111,59,12,YELLOW,2,width=.7,dashed=True)
s.text(241,113,'12 May 1960.',7,w=55)
s.stack(409,103,39,25,'Other',GRAY,3)
s.text(14,146,'All original candidate documents are retained',7.0,w=270)
s.path([[269,123],[269,186]],1.1,dashed=True)
s.path([[117,186],[350,186]],1.1,dashed=True)
s.path([[117,186],[117,195]],1.1,dashed=True)
s.path([[350,186],[350,195]],1.1,dashed=True)
s.line(117,193,117,195,1.1)
s.line(350,193,350,195,1.1)
s.label('b','Terminal-sentence detail',7,174,453)
s.box(6,195,222,105,CREAM,5,width=.9);s.box(240,195,221,105,BLUE,5,width=.9)
s.text(14,203,'Conflict condition (n = 200)',7.8,w=205,bold=True);s.text(249,203,'Ordinary condition (n = 100)',7.8,w=203,bold=True)
s.text(14,221,'Original: Person B was born on',7.0,w=205);s.text(249,221,'Original: Person B was born on',7.0,w=203)
s.box(14,235,74,18,GREEN,2,width=.7);s.text(16,240,'12 May 1960',7.1,w=70,align='center')
s.box(249,235,74,18,GREEN,2,width=.7);s.text(251,240,'12 May 1960',7.1,w=70,align='center')
s.arrow([[91,244],[110,244]],1.7);s.arrow([[326,244],[345,244]],1.7)
s.box(114,235,104,18,PINK,2,width=.7);s.text(117,240,'Added: 12 May 1967',6.9,w=98,align='center')
s.box(349,235,103,18,GREEN,2,width=.7);s.text(351,240,'Added: 12 May 1960',6.9,w=99,align='center')
s.math(17,261,r'y^{\prime}=y+7',[sup(t('y'),t('′')),t('='),t('y'),t('+'),t('7')],8.8,w=78,h=18)
s.text(101,264,'Answer year changed',6.9,w=118)
s.math(252,261,r'd^{\prime}=d',[sup(t('d'),t('′')),t('='),t('d')],8.8,w=76,h=18)
s.text(336,264,'Exact duplicate',6.9,w=116)
s.text(14,286,'Same source title and presentation status',6.7,w=205)
s.text(249,286,'Same source title and presentation status',6.7,w=203)
scenes.append(s.export())

# Figure 4: shared information and source-budget interface, with graph controls.
s=Scene('Figure_4_Paired_Comparison','Controlled information paths in the selector comparison',300,'Each selector branch is a separate per-question run. Candidate sources and declared token costs are fixed. The three graph-informed controls share the accepted graph and priority. The main frozen comparison is joint preservation against plain set; adapted SetR is supplemental. The source cap excludes the question and fixed instructions.')
s.label('a','Matched selector inputs and source budgets',7,4,454)
s.box(6,25,111,214,BLUSH,5,width=.8)
s.text(13,34,'Fixed within a question',7.0,w=97,bold=True)
s.stack(26,66,60,39,'Sources V',BLUE,3);s.text(20,117,'Question q',7.4,w=85,align='center');s.text(20,134,'Unit costs',7.4,w=85,align='center')
s.box(17,162,88,65,PURPLE,4,width=.8);s.text(22,169,'Shared graph',7.3,w=78,align='center');s.circle(38,199,9,BLUE);s.circle(84,199,9,PINK);s.line(49,199,73,199,1.5);s.text(22,214,'and common priority',6.7,w=78,align='center')
s.line(124,50,124,226,1.5);s.arrow([[110,119],[124,119]],1.5)
ys=[41,73,105,153,185,217];names=['Plain set','SetR-IRI (adapted)','MMR','Same-graph set','Chain closure','Joint preservation']
s.box(137,145,183,96,WHITE,5,width=.9,dashed=True)
for j,(y,name) in enumerate(zip(ys,names)):
    col=YELLOW if j==5 else GREEN if j>=3 else BLUE
    s.arrow([[124,y+9],[140,y+9]],1.4)
    s.box(145,y,105,21,col,3,width=.7);s.text(149,y+6,name,7.0,w=97,align='center',bold=j==5)
    s.arrow([[252,y+10],[266,y+10]],1.4)
    s.stack(272,y+3,35,15,'S',col,2)
s.path([[106,222],[111,222],[111,249],[137,249],[137,241]],1,dashed=True)
s.text(271,245,'Source cap',6.9,w=61,align='center')
s.math(334,31,r'C(S_m)\leq256',[*f('C',sub(t('S'),t('m'))),t('≤'),t('256')],8.7,w=124,h=19,align='center')
s.line(326,50,326,226,1.5)
for y in ys:s.line(311,y+10,326,y+10,1.3)
s.arrow([[326,132],[340,132]],1.8)
s.box(345,93,114,74,GREEN,5);s.text(351,102,'Fixed 8B reader',7.7,w=102,bold=True,align='center');s.text(351,121,'Same prompt',7.1,w=102,align='center');s.text(351,134,'Same decoding',7.1,w=102,align='center');s.text(351,147,'One readout per packet',6.8,w=102,align='center')
s.text(343,187,'Original selected text',7.1,w=116,align='center');s.text(343,202,'and source identifiers',7.1,w=116,align='center')
s.label('b','Paired evaluation with separate denominators',7,265,454)
s.box(6,280,222,17,CREAM,3,width=.7);s.text(10,285,'Conflict identification: 200 assigned cases',6.8,w=214,align='center')
s.box(240,280,221,17,BLUE,3,width=.7);s.text(244,285,'Ordinary EM, F1 and false conflicts: 100 cases',6.6,w=213,align='center')
scenes.append(s.export())

# Figure 5: repeated packet symbols reveal exactly which dependency changes.
s=Scene('Figure_5_Source_Intervention_Design','Matched perturbations of original source support',294,'Schematic unit roles: B bridge, A one answer side, O opposing side, N noncritical source, R replacement from the same candidate pool. Unit counts shown are illustrative; actual counts vary by question but are fixed within a matched triple. No reader output is implied by the schematic.')
s.box(6,5,455,31,BLUSH,5,width=.8);s.text(14,15,'Replacement text comes from the same original candidate pool',7.8,w=439,bold=True)
s.label('a','Bridge dependency: 16 matched questions',7,47,454)
for x,title in [(13,'Intact'),(167,'Sham'),(321,'Critical')]:s.text(x,68,title,7.8,w=135,bold=True,align='center')
for x,units,cols in [(13,['B','A','N'],[BLUE,GREEN,GRAY]),(167,['B','A','R'],[BLUE,GREEN,PURPLE]),(321,['R','A','N'],[PURPLE,GREEN,GRAY])]:
    s.box(x,83,134,62,WHITE,4,width=.8);s.cells(x+15,96,units,cols,cw=30,ch=21,gap=4,depth=3)
s.text(21,128,'Complete identifying bridge',6.8,w=118,align='center');s.text(175,128,'Noncritical source replaced',6.8,w=118,align='center');s.text(329,128,'Identifying bridge replaced',6.8,w=118,align='center')
s.label('b','Opposing support: 9 matched questions',7,159,454)
for x,units,cols in [(13,['B','A','O','N'],[BLUE,GREEN,PINK,GRAY]),(167,['B','A','O','R'],[BLUE,GREEN,PINK,PURPLE]),(321,['B','A','R','N'],[BLUE,GREEN,PURPLE,GRAY])]:
    s.box(x,179,134,62,WHITE,4,width=.8);s.cells(x+10,192,units,cols,cw=25,ch=21,gap=4,depth=3)
s.text(21,224,'Both opposing sides retained',6.7,w=118,align='center');s.text(175,224,'Noncritical source replaced',6.8,w=118,align='center');s.text(329,224,'One opposing side replaced',6.8,w=118,align='center')
s.box(6,252,455,20,GREEN,4,width=.8);s.text(10,258,'Matched unit count   |   Source cap: 256 tokens   |   Within-case length spread: at most 8 tokens',6.7,w=447,align='center')
s.text(8,281,'B: bridge    A: answer side    O: opposing side    N: noncritical source    R: replacement',6.7,w=451,align='center')
scenes.append(s.export())

# Figure 6: compact source packages plus independent diagnostic checks.
s=Scene('Figure_6_Reference_Diagnostics','Source inputs and complete-reference checks',288,'Three diagnostic inputs use the same 300 confirmation questions. Source inspection is confined to the fixed 60-question subset. R denotes a complete inspected reference in the lower detail. Its containment is one direct diagnostic of retaining that reference, not a necessary condition for all alternative complete witnesses. The three checks are not mutually exclusive error classes.')
s.label('a','Reader inputs on the same confirmation questions',7,4,454)
s.box(6,24,100,127,BLUSH,5,width=.8);s.text(12,32,'Candidate sources',7.2,w=88,bold=True,align='center');s.stack(27,64,49,39,'Pool V',BLUE,4);s.text(14,121,'Original text + IDs',6.9,w=84,align='center')
s.line(120,47,120,131,1.6);s.arrow([[108,88],[120,88]],1.6)
for y,title,detail,col in [(31,'Selected packet S','Automatic selection; 256-token cap',YELLOW),(74,'Full context V','All candidate units',BLUE),(117,'Annotation reference R','Privileged support identifiers',GREEN)]:
    s.arrow([[120,y+15],[134,y+15]],1.6);s.box(139,y,178,32,col,4,width=.8);s.text(145,y+5,title,7.5,w=166,bold=True);s.text(145,y+18,detail,6.8,w=166)
    s.arrow([[319,y+16],[335,y+16]],1.4)
s.line(338,47,338,133,1.6);s.arrow([[338,90],[352,90]],1.8)
s.box(357,59,104,62,CREAM,5);s.text(363,70,'Same fixed',7.6,w=92,align='center');s.text(363,84,'8B reader',7.6,w=92,bold=True,align='center');s.text(363,105,'Separate input conditions',6.4,w=92,align='center')
s.path([[228,149],[228,163],[446,163],[446,194]],1.0,dashed=True)
s.line(446,192,446,194,1.0)
s.label('b','Complete-reference detail: fixed 60-question inspection',7,173,454)
s.box(6,194,455,86,WHITE,5,width=1,dashed=True)
for x,title,col in [(14,'Budget feasibility',BLUE),(167,'Evidence retention',GREEN),(320,'Reader use',CREAM)]:s.box(x,202,132,69,col,4,width=.8);s.text(x+5,209,title,7.4,w=122,bold=True,align='center')
s.math(25,228,r'C(R)\leq B',[*f('C',t('R')),t('≤'),t('B')],9.5,w=110,h=20,align='center');s.text(22,253,'Does complete support fit?',6.7,w=116,align='center')
s.math(178,228,r'R\subseteq S',[t('R'),t('⊆'),t('S')],9.5,w=110,h=20,align='center');s.text(175,253,'Is this reference retained?',6.7,w=116,align='center')
s.math(331,228,r'f(q,R)',[t('f'),t('('),t('q'),t(','),t('R'),t(')')],9.5,w=110,h=20,align='center');s.text(328,253,'Read the complete reference',6.5,w=116,align='center')
scenes.append(s.export())

(ROOT/'figure_sources/figure_scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'stem':s['stem'],'height':s['height'],'objects':len(s['items']),'equations':sum(a['kind']=='math' for a in s['items'])} for s in scenes],indent=2))
