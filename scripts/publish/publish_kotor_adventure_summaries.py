"""Publish pinned secondary summaries for two KOTOR tabletop adventures.

The raw input is extracted from the pinned public wiki dump; full source pages,
publisher blurbs and original adventure text are not redistributed here.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'The Betrayal of Darth Revan':{'revision':'15324986','raw':'01783fc7059b0c105a55b741ef615899b592f5178ab4f2f107d672a785eeddb5','section':'199b7123e006c1aac2cb0642dfa129c12fa23d50e542f4f1aef36307e8f856e0','text':'6966689e8f9c32c6ea5348e13fa54b0fd08e8ac2285f35d8582221f1d509a8d7','kind':'plot summary'},'Iridonian Darkness':{'revision':'15402574','raw':'47db9a40b8d95a646a3602d129dc13058e5c7a4eee62e987cc1d4ea3e73163a7','section':None,'text':'1ab9bb9266947939b0465551dfed92b62d75c5388dd689b23da45cb588c1e7c2','kind':'introduction'}}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def clean(s):
 c=mwparserfromhell.parse(s)
 for t in list(c.filter_templates(recursive=False)):c.remove(t)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for t in list(c.filter_wikilinks(recursive=True)):
  if str(t.title).strip().casefold().startswith(('file:','image:','category:')):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 return re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',c.strip_code(normalize=True,collapse=True).strip())
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,pin in PINS.items():
 r=x[title];raw=r['raw_wikitext'];assert r['revision_id']==pin['revision'] and sha(raw)==pin['raw']
 heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));sections={}
 for i,h in enumerate(heads):
  end=next((v.start() for v in heads[i+1:] if len(v.group(1))<=len(h.group(1))),len(raw));sections.setdefault(h.group(2).strip().casefold(),[]).append(raw[h.end():end].strip())
 source=sections['plot summary'][0] if pin['kind']=='plot summary' else raw[:heads[0].start()]
 if pin['section']:assert sha(source)==pin['section']
 text,n=clean(source);assert sha(text)==pin['text'] and not re.search(r'["“”]',text)
 allcode=mwparserfromhell.parse(raw);risky=[]
 for t in allcode.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):risky.extend(p.value.strip_code() for p in t.params)
 for t in allcode.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):risky.append(t.contents.strip_code())
 for k in ("publisher's summary",'official description','opening crawl','back cover'):
  for s in sections.get(k,[]):risky.append(clean(s)[0])
 assert not any(shingles(text)&shingles(q) for q in risky),title
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe='/');rows.append({'title':title+' — '+pin['kind'],'url':url,'source_revision_url':url+'?oldid='+pin['revision'],'revision_id':pin['revision'],'timestamp':r['timestamp'],'source_archive_sha256':ARCH,'full_page_wikitext_sha256':pin['raw'],'section_wikitext_sha256':sha(source),'text':text,'text_sha256':pin['text'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','continuity':'Source labels Revan scenario non-canon Legends; Iridonian continuity unverified.' if title=='The Betrayal of Darth Revan' else 'Legends continuity unverified','coverage':'Partial wiki contributor text; tabletop player choices and primary adventure content are not fully represented. Unmarked excerpts remain unverified.','omitted_inline_quotations':n,'embedded':False})
rows.sort(key=lambda r:r['title']);Path('data/wookieepedia-kotor-adventure-summaries.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows));print('Published',len(rows),'secondary records')
