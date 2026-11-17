"""Prepare limited wiki-authored narrative from pinned revisions of held KOTOR subjects.

Markup extraction is lossy; a quote screen cannot clear unmarked third-party text.
Usage: PYTHONPATH=<mwparserfromhell> python publish_kotor_core_replacements.py <raw-bundle.json>
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'Kreia':('15829285','cea761268c93f86cff0d4ee8586039177f494c55099aae14ce147c24a5014801'),"Darth Revan's Sith Empire":('15764243','b5f8fefb901f05cdbe1accb6e0da62fc4f5bef8ae37b544758ad9d638b328d9f'),'Handmaiden Sisters':('15769331','308a539849be1cd36521fe8c43c2d0673b452d03b45b02e8ee63bea60c8724a9')}
ALLOW={'biography','personality and traits','powers and abilities','equipment','history','government and politics','military','astrography','service'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',str(s).casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
bundle=json.loads(Path(sys.argv[1]).read_text());assert bundle['archive_sha256']==ARCHIVE
rows=[];held=[]
for title,(revision,digest) in PINS.items():
 v=bundle['records'][title];raw=v['raw_wikitext'];assert v['revision_id']==revision and sha(raw)==digest and v['raw_wikitext_sha256']==digest
 code=mwparserfromhell.parse(raw);bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|speech|crawl|lyrics|poem',str(t.name)):bad.extend(str(p.value.strip_code()) for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):bad.append(str(t.contents.strip_code()))
 quote_shingles=set().union(*(shingles(q) for q in bad)) if bad else set()
 heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));allowed=False;parents={}
 for i,h in enumerate(heads):
  level=len(h.group(1));heading=h.group(2).strip();
  if level==2:allowed=heading.casefold() in ALLOW;parents={}
  if not allowed:continue
  parents[level]=mwparserfromhell.parse(heading).strip_code().strip();parents={k:v for k,v in parents.items() if k<=level}
  end=heads[i+1].start() if i+1<len(heads) else len(raw);body=raw[h.end():end];section=' / '.join(parents[k] for k in sorted(parents));c=mwparserfromhell.parse(body)
  for t in list(c.filter_templates(recursive=False)):
   try:c.remove(t,recursive=True)
   except ValueError:pass
  for t in list(c.filter_tags(recursive=True)):
   if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
    try:c.remove(t,recursive=True)
    except ValueError:pass
  for l in list(c.filter_wikilinks(recursive=True)):
   if str(l.title).strip().casefold().startswith(('file:','image:','category:')):
    try:c.remove(l,recursive=True)
    except ValueError:pass
  text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text);parts=re.split(r'\n\s*\n',text);omitted=sum(bool(shingles(part)&quote_shingles) for part in parts);text='\n\n'.join('[paragraph omitted due to marked-quote overlap]' if shingles(part)&quote_shingles else part for part in parts)
  reason='empty after markup removal' if not text or not re.sub(r'\[paragraph omitted due to marked-quote overlap\]','',text).strip() else 'unresolved quotation mark' if re.search(r'["“”]',text) else 'eight-word match against marked quote body' if shingles(text)&quote_shingles else None
  if reason:held.append({'title':title,'section':section,'section_wikitext_sha256':sha(body),'reason':reason});continue
  url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
  rows.append({'title':title+' — '+section,'subject':title,'section':section,'url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':v['timestamp'],'source_archive_sha256':ARCHIVE,'full_page_wikitext_sha256':digest,'section_wikitext_sha256':sha(body),'text':text,'text_sha256':sha(text),'omitted_inline_quotations':n,'omitted_overlap_paragraphs':omitted,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Partial wiki-authored narrative. Marked quotations, overlapping paragraphs, templates and references removed; this may lose context. The screen does not clear unmarked excerpts or establish game-branch completeness.','embedded':False})
rows.sort(key=lambda x:(x['subject'],x['section']));output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
assert sha(output)=='51fa324ed5bebca240c5d3368a319a2237fa3e4da0dd41a426045e5c0eb8c24d';Path('data/wookieepedia-kotor-core-replacements.jsonl').write_text(output);Path('evaluation/kotor-core-replacement-holds.json').write_text(json.dumps({'description':'Section fragments empty after removal or held by overlap screening. This is not a rights determination.','source_archive_sha256':ARCHIVE,'held':held},ensure_ascii=False,indent=2)+'\n')
print('Included sections',len(rows),'held',len(held),'by subject',{t:sum(r['subject']==t for r in rows) for t in PINS},'sha256',sha(output))
