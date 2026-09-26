#!/usr/bin/env python3
"""Render a 13-week isometric calendar from GitHub's public contribution page.
No authentication or third-party dependencies. GitHub HTML changes fail closed.
"""
import argparse
from collections import Counter
from datetime import date, timedelta
from html import escape, unescape
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def get(url):
    req = Request(url, headers={'User-Agent': 'yuanjuju-profile', 'Accept': 'application/json' if 'api.github.com' in url else 'text/html'})
    with urlopen(req, timeout=30) as res:
        return res.read().decode('utf-8')


def fetch(username):
    page = get(f'https://github.com/users/{username}/contributions')
    cells = {}
    for raw in re.findall(r'<td\s+([^>]*data-date="[^"]+"[^>]*)>', page):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', raw))
        cells[attrs['id']] = attrs
    tips = {}
    for raw, body in re.findall(r'<tool-tip\s+([^>]*)>(.*?)</tool-tip>', page, re.S):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', raw))
        if attrs.get('for') in cells:
            text = unescape(re.sub('<[^>]*>', '', body)).strip()
            m = re.match(r'([\d,]+) contributions? on ', text)
            if text.startswith('No contributions on '):
                count = 0
            elif m:
                count = int(m[1].replace(',', ''))
            else:
                raise ValueError('Unrecognized public contribution tooltip')
            tips[attrs['for']] = count
    if len(cells) < 350 or set(cells) != set(tips):
        raise ValueError('Incomplete public contribution calendar; refusing to overwrite assets')
    days = sorted([{'date': a['data-date'], 'count': tips[key], 'level': int(a['data-level'])} for key,a in cells.items()], key=lambda x: x['date'])
    repos = json.loads(get(f'https://api.github.com/users/{username}/repos?per_page=100'))
    if len(repos) == 100:
        raise ValueError('Repository pagination required')
    return {'username':username,'fetched_at':date.today().isoformat(),'days':days,'repos':[{'name':r['name'],'language':r['language'],'fork':r['fork'],'stars':r['stargazers_count']} for r in repos]}


def render(data, dark):
    end = date.fromisoformat(data['days'][-1]['date'])
    end_saturday = end + timedelta(days=(5-end.weekday()) % 7)
    start = end_saturday-timedelta(days=90)
    days = [d for d in data['days'] if start.isoformat() <= d['date'] <= end.isoformat()]
    counts = {d['date']:d['count'] for d in days}
    total=sum(counts.values());active=sum(n>0 for n in counts.values());peak=max(counts.values(),default=0)
    bg='#111728' if dark else '#f5f3ff';ink='#ebeaff' if dark else '#252349';muted='#9b9ebf' if dark else '#696582';stroke='#293049' if dark else '#e0daef'
    zero=['#283049','#20273b','#1a2032'] if dark else ['#e6e1f2','#d7cfe8','#c7bfdc']
    palette=[['#8da8ff','#667ed4','#4d60ac'],['#80d7d9','#49acb6','#32838f'],['#c2a0f2','#9974d0','#7956ac'],['#ffd49b','#e9ab65','#bf8148']]
    p=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="560" viewBox="0 0 1100 560" role="img" aria-labelledby="title desc"><title id="title">{escape(data.get("username","yuanjuju"))}: {total} contributions in 13 weeks</title><desc id="desc">Public GitHub contributions from {start} to {end}. One tile per day; height represents the number of contributions. {active} active days. Peak: {peak} contributions in one day.</desc>',
       '<style>.tower{animation:appear .85s ease-out both;transform-box:fill-box;transform-origin:center bottom}@keyframes appear{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}.star{animation:twinkle 3s ease-in-out infinite}@keyframes twinkle{50%{opacity:.25}}@media(prefers-reduced-motion:reduce){.tower,.star{animation:none}}</style>',
       f'<rect width="1100" height="560" rx="18" fill="{bg}"/>']
    def text(x,y,value,size=16,color=None,weight=400,font='Arial, sans-serif'):
        p.append(f'<text x="{x}" y="{y}" fill="{color or ink}" font-family="{font}" font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>')
    text(38,49,'GITHUB / 13 WEEKS',15,muted,600,'monospace')
    text(772,49,f'{start:%Y.%m.%d} — {end:%Y.%m.%d}',14,muted)
    text(38,107,total,42,ink,700);text(124,105,'contributions',16,muted)
    text(317,107,active,32,ink,700);text(369,105,'active days',16,muted)
    text(534,107,peak,32,ink,700);text(587,105,'best day',16,muted)
    # Camera basis: a week moves right/down; a weekday moves left/down.
    # Drawing increasing x+y puts the front tiles over the back tiles.
    a,b,gap=32,14,1.8
    for week,weekday in sorted(((w,d) for w in range(13) for d in range(7)),key=lambda x:(sum(x),x[0])):
        day=start+timedelta(days=week*7+weekday)
        if day>end:continue
        n=counts.get(day.isoformat(),0)
        x=315+(week-weekday)*a;y=199+(week+weekday)*b
        height=5 if not n else 15+math.sqrt(n)*15
        colors=zero if not n else palette[(day.month-1)%4]
        top,left,right=colors
        cl=' class="tower"' if n else ''
        p.append(f'<g{cl}><title>{day}: {n} contributions</title>')
        def poly(points,fill):p.append(f'<polygon points="{" ".join(f"{xx:.1f},{yy:.1f}" for xx,yy in points)}" fill="{fill}"/>')
        aa=a-gap;bb=b-gap/2
        poly([(x-aa,y-height),(x,y+bb-height),(x,y+bb),(x-aa,y)],left)
        poly([(x+aa,y-height),(x,y+bb-height),(x,y+bb),(x+aa,y)],right)
        poly([(x,y-bb-height),(x+aa,y-height),(x,y+bb-height),(x-aa,y-height)],top)
        p.append('</g>')
    # Small date annotations keep the range readable without a dense set of labels.
    text(98,327,f'{start:%b %d}',12,muted,font='monospace')
    text(704,481,f'{end:%b %d}',12,muted,font='monospace')
    # A compact legend and two actual public repository metrics.
    text(850,197,'PUBLIC REPOS',12,muted,600,'monospace')
    text(850,237,len(data['repos']),31,ink,700)
    text(850,280,'STARS',12,muted,600,'monospace')
    text(850,320,sum(r['stars'] for r in data['repos']),31,ink,700)
    p.append(f'<path d="M842 349h198" stroke="{stroke}"/>')
    text(850,380,'1 block = 1 day',13,muted)
    text(850,405,'height = activity',13,muted)
    for x,y,r in [(782,155,3),(1036,159,4),(1017,444,3)]:
        p.append(f'<path class="star" d="M{x-r} {y}h{r*2} M{x} {y-r}v{r*2}" stroke="#b8a0f2" stroke-width="2"/>')
    p.append(f'<path d="M38 510h1024" stroke="{stroke}"/>')
    text(38,538,'@yuanjuju',13,muted,font='monospace')
    text(736,538,'SOURCE: GITHUB PUBLIC CALENDAR',12,muted,font='monospace')
    p.append('</svg>')
    return '\n'.join(p)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',type=Path);parser.add_argument('--username',default='yuanjuju');args=parser.parse_args()
    data=json.loads(args.fixture.read_text()) if args.fixture else fetch(args.username)
    assets=ROOT/'assets';assets.mkdir(exist_ok=True)
    for dark in [False,True]:
        name=f'activity-{"dark" if dark else "light"}.svg'
        (assets/name).write_text(render(data,dark))
    (assets/'activity-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Generated light and dark calendars from public data.')

if __name__=='__main__':main()
