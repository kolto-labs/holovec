"""Create local-only SWTOR main-game review candidates, including raw sections from a pinned wiki dump; no text is auto-approved.
Usage: python prepare_swtor_game_review.py ARCHIVE OUTPUT
"""
import sys,subprocess,xml.etree.ElementTree as ET,re,json,hashlib
from pathlib import Path
import mwparserfromhell
names=['Star Wars: The Old Republic']
archive=sys.argv[1]; expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with open(archive,'rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==expected
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$');risky=re.compile(r'(?i)\{\{\s*(?:quote|quotation|blockquote|quote[_ ]?box|dialogue|speech)\b|<\s*(?:blockquote|q)\b|["“”]')
def clean(s):
 code=mwparserfromhell.parse(s)
 for t in list(code.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(t,recursive=True)
   except ValueError:pass
 for t in list(code.filter_templates(recursive=False)):
  try:code.remove(t,recursive=True)
  except ValueError:pass
 return code.strip_code(normalize=True,collapse=True).strip()
def overlap(a,b):
 a=re.findall(r'\w+',a.casefold());b=re.findall(r'\w+',b.casefold()); n=10; shingles={tuple(a[i:i+n]) for i in range(len(a)-n+1)}
 return any(tuple(b[i:i+n]) in shingles for i in range(len(b)-n+1))
proc=subprocess.Popen(['7z','x','-so',archive],stdout=subprocess.PIPE); found={};root=None
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and event=='start':root=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in names:
  rev=el.find('{*}revision');raw=rev.findtext('{*}text') or '';heads=list(head.finditer(raw));sections={}
  for i,h in enumerate(heads):
   end=next((x.start() for x in heads[i+1:] if len(x.group(1))<=len(h.group(1))),len(raw));sections.setdefault(h.group(2).strip().casefold(),[]).append(raw[h.end():end].strip())
  plots=sections.get('plot summary',[]); publisher=' '.join(clean(t) for k,v in sections.items() if k in ("publisher's summary",'official description','opening crawl','back cover') for t in v)
  for section in plots:
   text=clean(section); reasons=[]
   if risky.search(section):reasons.append('quotes_or_dialogue')
   if not text:reasons.append('empty')
   if overlap(text,publisher):reasons.append('publisher_overlap')
   found[title]={'revision_id':rev.findtext('{*}id'),'timestamp':rev.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(section.encode()).hexdigest(),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text,'raw_section':section,'reasons':reasons}
  if not plots:found[title]={'reason':'no_plot'}
 root.clear()
if proc.wait():raise RuntimeError('decompression failed')
p=Path(sys.argv[2]);
if p.exists(): raise FileExistsError(p)
p.write_text(json.dumps(found,ensure_ascii=False,indent=2));p.chmod(0o600)
print('matched',len(found),'no plot',sum('reason' in v for v in found.values()),'review candidates',sum('reasons' in v and not v['reasons'] for v in found.values()))
for k,v in found.items():print(k, v.get('reason',','.join(v.get('reasons',[])) or 'review'),len(v.get('text','')))
print('not found',set(names)-set(found))
