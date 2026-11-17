"""Prepare limited wiki-authored narrative from pinned revisions of held Old Republic subjects.

Markup extraction is lossy; a quote screen cannot clear unmarked third-party text.
Usage: PYTHONPATH=<mwparserfromhell> python publish_kotor_core_replacements.py <raw-bundle.json>
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'Dorjander Kace': ('15765191', '12502097c3e0ca37586edd38117b56b9a1b0e9816c4849f94868fbd1db2331a5'), 'HK-24 series assassin droid': ('15356864', '01b8c381a1fb4b2a80be121e4cf0e44c025923e294c8668f72dc86a071700f5a'), 'Hundred-Year Darkness/Legends': ('15790828', '9b19ded532ce665942eb6d6f68dc092a8397dd772f285cb7d21cb47ffba53b1c'), 'Lenn Teraan': ('14401454', 'f779cb64d316c931617fd7324183ffe8950720fd62f69d1127bfc8fbd7b7f8a5'), 'Mandalorian/Legends': ('15803849', 'f011d0e6497d870ab847dc04a82ecf79e5331a22fc09f75a5f950f5f632778bc'), 'Marka Ragnos': ('15803690', '4e5334cfe2dd723db29d10088ca469119d13a9685f2089a30958ed7213a2f6ae'), 'Oroko': ('15445721', 'ff8a38e2aa90921ea458fe04b0bedada783d4d6383b47f715f9d58073b13154b'), 'Renegin': ('15790137', '55ab316a7a5894e88634c413c3c856f9d9407c13257f98db058cbe1c3c86b2f5'), 'Republic Strategic Information Service': ('15810891', 'cf93dfaaa88ab0342855a9f70cdca1cd121ac64342ae6e3a3803448c5d2704d5'), "Resol'nare rhyme": ('15790388', '737198851da8fd9f6cb9a36b8bae25f506332763089a2db1f5eeaea2a587cb7c'), "Search for Dramath the Second's remains": ('14374570', 'd1f8108e46451fce9e482ab688525171b9daceb1cd5e4a1d52c5b332161a9d86'), 'Sith Empire/Legends': ('15806423', '39da0a55332f7623a6477fac212951f52595f2deaa7684778fc2e7c031b95a83'), "Skirmish outside of Darth Nyriss's stronghold": ('14218926', '3018716a5a822d91e2dbb8462557510b69a1df85a01b42630dc06ba65f77d031')}
ALLOW={'biography','personality and traits','powers and abilities','equipment','history','description','society and culture','military','astrography','government and politics','culture','symbols','overview','beginnings','war','a new world','return','legacy','prelude','the search','skirmish','aftermath','commanders and crew'}
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
  rows.append({'title':title+' — '+section,'subject':title,'subject_scope':'cross-era; some sections may be outside Old Republic' if title in {'Mandalorian/Legends','Sith Empire/Legends','Republic Strategic Information Service'} else 'Old Republic-related or adjacent; relevance varies by section','section':section,'url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':v['timestamp'],'source_archive_sha256':ARCHIVE,'full_page_wikitext_sha256':digest,'section_wikitext_sha256':sha(body),'text':text,'text_sha256':sha(text),'omitted_inline_quotations':n,'omitted_overlap_paragraphs':omitted,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Partial wiki-authored narrative. Marked quotations, overlapping paragraphs, templates and references removed; this may lose context. The screen does not clear unmarked excerpts or establish game-branch completeness.','embedded':False})
for title in PINS:
 if not any(r['subject']==title for r in rows):held.append({'title':title,'section':None,'reason':'no qualifying non-empty prose section'})
rows.sort(key=lambda x:(x['subject'],x['section']));output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
assert sha(output)=='243f98c27f9d9f4ff75273313f1d60f546b6ab338c2f4ea5335425ebd3ffdcd3';Path('data/wookieepedia-old-republic-quote-replacements.jsonl').write_text(output);Path('evaluation/old-republic-quote-replacement-holds.json').write_text(json.dumps({'description':'Section fragments empty after removal or held by overlap screening. This is not a rights determination.','source_archive_sha256':ARCHIVE,'held':held},ensure_ascii=False,indent=2)+'\n')
print('Included sections',len(rows),'held',len(held),'by subject',{t:sum(r['subject']==t for r in rows) for t in PINS},'sha256',sha(output))
