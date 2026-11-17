"""Produce quote-omitted SWTOR comic-series narratives from a pinned local page.

Usage: PYTHONPATH=<dependencies> python publish_swtor_comic_media_sections.py LOCAL_FULL_PAGE_JSON
The raw page stays local. A clean overlap screen is not rights clearance.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
SRC='97f47816fa63991d28e705674f5dc3dd481d0955e277e0cba3e9d8b41667dcb7';ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';REV='15803850'
TARGET={'Threat of Peace':('1a0cbfdcdff4f270f7efea9ff21a34b5bc58bc0b9922216e53e3b20b2ac28ada',['threat-1','threat-2','threat-3']), 'Blood of the Empire':('54f8b6ba5c2940c8f4ae1bb08a0768cec0b054499d05ddec0424752ef59c6b91',['blood-1','blood-2','blood-3']), 'The Lost Suns':('0ae26ed43941892e06d4d1727165efa9d94ded69d5eef91de619c8064ae07040',[])}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());raw=x['raw_wikitext']
if x['title']!='Star Wars: The Old Republic' or x['revision_id']!=REV or x['full_wikitext_sha256']!=SRC or sha(raw)!=SRC:raise ValueError('source mismatch')
code=mwparserfromhell.parse(raw);names={'quote','quotation','blockquote','quote box','dialogue','speech'}
quotes=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in names and t.has(1)]
quotes += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in code.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
qset=set().union(*(shingles(q) for q in quotes)) if quotes else set()
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$');hs=list(head.finditer(raw));selected={};publishers=[]
for i,h in enumerate(hs):
 name=mwparserfromhell.parse(h.group(2)).strip_code().strip();end=next((z.start() for z in hs[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));s=raw[h.end():end].strip()
 if name in TARGET:
  if name in selected:raise ValueError('Ambiguous section '+name)
  selected[name]=s
 if name.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):publishers.append(mwparserfromhell.parse(s).strip_code(normalize=True,collapse=True))
if set(selected)!=set(TARGET):raise ValueError('section missing')
pubset=set().union(*(shingles(p) for p in publishers)) if publishers else set();rows=[];held=[]
for name,(digest,act_ids) in TARGET.items():
 s=selected[name]
 if sha(s)!=digest:raise ValueError('section hash changed')
 c=mwparserfromhell.parse(s);removed=0
 for t in list(c.filter_templates(recursive=False)):
  if str(t.name).strip().casefold().replace('_',' ') in names:removed+=1
  c.remove(t,recursive=True)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for link in list(c.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:')):
   try:c.remove(link,recursive=True)
   except ValueError:pass
 clean=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',clean)
 reason='empty' if not text else 'unresolved quote or image marker' if re.search(r'["“”]',text) or 'thumb|' in text else 'eight-word overlap with quote block' if shingles(text)&qset else 'eight-word overlap with publisher section' if shingles(text)&pubset else None
 if reason:held.append({'series':name,'section_wikitext_sha256':digest,'reason':reason});continue
 url='https://starwars.fandom.com/wiki/Star_Wars:_The_Old_Republic'
 rows.append({'title':'Star Wars: The Old Republic — '+name,'url':url,'source_revision_url':url+'?oldid='+REV,'revision_id':REV,'timestamp':x['timestamp'],'source_archive_sha256':ARCH,'full_page_wikitext_sha256':SRC,'section_wikitext_sha256':digest,'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'section':name,'text':text,'related_webcomic_act_ids':act_ids,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images, and quotation-marked phrases removed; inline omissions marked [quoted words omitted]. Screened against full-page quotation blocks and publisher sections at eight words.','omitted_quote_templates':removed,'omitted_inline_quotations':n,'coverage':'Series-level summary, not complete act, issue, artwork, or primary comic coverage.','embedded':False})
if len(rows)+len(held)!=3:raise ValueError('incomplete screen')
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='1f66002acd4125c4027c3e81e56c0047c84ca86133072984d88db025c2743284':raise ValueError('output changed; re-screen before release')
Path('data/wookieepedia-swtor-comic-media-sections.jsonl').write_text(output)
Path('evaluation/swtor-comic-media-section-screen.json').write_text(json.dumps({'description':'Automated quote and publisher overlap screening across the source page; no source text stored. Not rights clearance.','source_archive_sha256':ARCH,'source_revision_id':REV,'quote_blocks':len(quotes),'publisher_sections':len(publishers),'sections_included':len(rows),'held':held},indent=2,ensure_ascii=False)+'\n')
print('prepared',len(rows),'sections; held',[(h['series'],h['reason']) for h in held])
