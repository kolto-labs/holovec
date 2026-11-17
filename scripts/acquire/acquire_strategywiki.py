"""Extract a pinned independently published StrategyWiki archive.

Download https://archive.org/download/wiki-strategywiki.org_w-20250828/strategywiki.org_w-20250828-history.xml.zst
Then run: python acquire_strategywiki.py PATH_TO_ARCHIVE
Requires zstd, lxml and mwparserfromhell. Historical contributions may have
separate license terms; the output retains page links and revision IDs.
"""
import hashlib,json,re,subprocess,sys,urllib.parse,pathlib
from lxml import etree
import mwparserfromhell
if len(sys.argv)!=2:raise SystemExit(__doc__)
archive=pathlib.Path(sys.argv[1]);expected='eca84fa144476eae3b056657f741c185d1232b7924adb8bf076e082236b0e1da';h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
if h.hexdigest()!=expected:raise SystemExit('Archive SHA-256 mismatch')
p=subprocess.Popen(['zstd','--long=31','-dc',str(archive)],stdout=subprocess.PIPE);ctx=etree.iterparse(p.stdout,events=('start','end')); pages={}
for ev,el in ctx:
 tag=el.tag.rsplit('}',1)[-1]
 if ev=='start' and tag=='page':title='';pageid=None;selected=False;best=None
 if ev!='end':continue
 parent=el.getparent();ptag=parent.tag.rsplit('}',1)[-1] if parent is not None else ''
 if tag=='title' and ptag=='page':title=el.text or '';selected=bool(re.match(r'^Star Wars:? Knights of the Old Republic(?: II(?:: The Sith Lords)?)?(?:/|$)',title,re.I))
 elif tag=='id' and ptag=='page':pageid=el.text
 elif tag=='revision':
  if selected:
   def child(name):
    a=el.find('{*}'+name);return (a.text or '') if a is not None else ''
   ts=child('timestamp');raw=child('text');rid=child('id')
   if raw and (best is None or (ts,int(rid or 0))>(best[0],int(best[1] or 0))):best=(ts,rid,raw)
  el.clear()
  while el.getprevious() is not None:del parent[0]
 elif tag=='page':
  if selected and best and pageid:
   if pageid not in pages or (best[0],int(best[1] or 0))>(pages[pageid][1][0],int(pages[pageid][1][1] or 0)):pages[pageid]=(title,best)
  el.clear()
  while el.getprevious() is not None:del parent[0]
if p.wait()!=0:raise SystemExit('Archive decompression failed')
rows=[]
for pageid,(title,(timestamp,rid,raw)) in pages.items():
 if raw.lstrip().lower().startswith('#redirect'):continue
 plain=mwparserfromhell.parse(raw).strip_code(normalize=True,collapse=True).strip()
 if not plain:continue
 url='https://strategywiki.org/wiki/'+urllib.parse.quote(title.replace(' ','_'),safe='/():')
 rows.append({'title':title,'url':url,'page_id':pageid,'revision':rid,'timestamp':timestamp,'text':plain,'license':'CC BY-SA 4.0; older contributions may be CC BY-SA 3.0; third-party excerpts may have separate terms','attribution':'StrategyWiki contributors; see article revision history','archive':'https://archive.org/details/wiki-strategywiki.org_w-20250828','archive_sha256':expected,'sha256':hashlib.sha256(plain.encode()).hexdigest(),'evidence_class':'secondary_walkthrough'})
rows.sort(key=lambda x:x['title']);pathlib.Path('data').mkdir(exist_ok=True);pathlib.Path('data/strategywiki.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows));print('pages',len(rows))
