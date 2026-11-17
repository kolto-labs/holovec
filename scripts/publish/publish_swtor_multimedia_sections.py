"""Extract screened SWTOR multimedia narratives from a pinned local wiki page.

Usage: PYTHONPATH=<dependencies> python publish_swtor_multimedia_sections.py LOCAL_FULL_PAGE_JSON
Raw page stays local. Automated overlap screening does not establish rights.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
SRC='97f47816fa63991d28e705674f5dc3dd481d0955e277e0cba3e9d8b41667dcb7';ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';REV='15803850'
TARGET={'Short stories':'27683b26b9427cb9820756f55c6d213ad92dc3e7aab23e9852bafccd7cd3873a','Cinematic trailers':'79462e88d9aa1720ef6d2537972879e3c88402f1f98d9be5e66a493c32e5cf32','Galactic Timeline':'ec5b5b5244d5828b62c8c1f97f01113abf94087c926bb42a8e4a5f971de22f13','Novel series':'b89407dc4158fa4ba9af21ad37a60c82b10515f1ed2f854061956c14b5a99df4'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());raw=x['raw_wikitext']
if x['title']!='Star Wars: The Old Republic' or x['revision_id']!=REV or sha(raw)!=SRC or x['full_wikitext_sha256']!=SRC:raise ValueError('source mismatch')
code=mwparserfromhell.parse(raw);names={'quote','quotation','blockquote','quote box','dialogue','speech'}
quotes=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in names and t.has(1)]
quotes += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in code.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
qset=set().union(*(shingles(q) for q in quotes)) if quotes else set()
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$');hs=list(head.finditer(raw));selected={};publishers=[]
for i,h in enumerate(hs):
 name=mwparserfromhell.parse(h.group(2)).strip_code().strip();end=next((z.start() for z in hs[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));s=raw[h.end():end].strip()
 if name in TARGET:
  if name in selected:raise ValueError('Ambiguous '+name)
  selected[name]=s
 if name.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):publishers.append(mwparserfromhell.parse(s).strip_code(normalize=True,collapse=True))
if set(selected)!=set(TARGET):raise ValueError('section missing')
pubset=set().union(*(shingles(p) for p in publishers)) if publishers else set();rows=[];held=[];encountered=[]
for category,digest in TARGET.items():
 body=selected[category]
 if sha(body)!=digest:raise ValueError('section changed '+category)
 child=[h for h in head.finditer(body) if len(h.group(1))==4];groups=[]
 if child:
  if body[:child[0].start()].strip():groups.append(('Introduction',body[:child[0].start()].strip()))
  for i,h in enumerate(child):
   end=child[i+1].start() if i+1<len(child) else len(body)
   groups.append((mwparserfromhell.parse(h.group(2)).strip_code().strip(),body[h.end():end].strip()))
 else:groups=[(category,body)]
 for name,s in groups:
  encountered.append((category,name));c=mwparserfromhell.parse(s);removed=0
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
  if reason:held.append({'category':category,'section':name,'section_wikitext_sha256':sha(s),'reason':reason});continue
  url='https://starwars.fandom.com/wiki/Star_Wars:_The_Old_Republic'
  rows.append({'title':'Star Wars: The Old Republic — '+category+' — '+name,'url':url,'source_revision_url':url+'?oldid='+REV,'revision_id':REV,'timestamp':x['timestamp'],'source_archive_sha256':ARCH,'full_page_wikitext_sha256':SRC,'parent_section_wikitext_sha256':digest,'section_wikitext_sha256':sha(s),'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'category':category,'section':name,'text':text,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images, and quotation-marked phrases removed; inline omissions marked [quoted words omitted]. Screened against full-page quotation blocks and publisher sections at eight words.','omitted_quote_templates':removed,'omitted_inline_quotations':n,'coverage':'Partial secondary narrative, not primary works, video, audio, or complete story coverage.','embedded':False})
if len(set(encountered))!=len(encountered) or len(rows)+len(held)!=len(encountered):raise ValueError('duplicate or missing')
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='0be4d1f28a9e83f0da4e41c819061e79ee8bb41fb849f99c2c73b5a5e605229b':raise ValueError('Output changed; re-screen before release')
Path('data/wookieepedia-swtor-multimedia-sections.jsonl').write_text(output)
Path('evaluation/swtor-multimedia-section-screen.json').write_text(json.dumps({'description':'Automated full-page quotation-block and publisher-section overlap screening; no source text stored. Not rights clearance.','source_archive_sha256':ARCH,'source_revision_id':REV,'quote_blocks':len(quotes),'publisher_sections':len(publishers),'sections_encountered':len(encountered),'sections_included':len(rows),'held':held},indent=2,ensure_ascii=False)+'\n')
print('included',len(rows),'held',len(held));print([(h['category'],h['section'],h['reason']) for h in held])
