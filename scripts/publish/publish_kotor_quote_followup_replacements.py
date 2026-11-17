"""Prepare limited wiki-authored narrative from pinned revisions of ten additional held KOTOR subjects.

Markup extraction is lossy; a quote screen cannot clear unmarked third-party text.
Usage: PYTHONPATH=<mwparserfromhell> python publish_kotor_core_replacements.py <raw-bundle.json>
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'Force drain/Legends': ('15827871', 'be3ec9686d51e1c87b0eb379d3eeed6a0349f7018a504adee6418783264b9d24'), 'Gu-vandi': ('15769111', '4e58aecec0ff46278598665b2e159c0e117ce105680adc1eeeb1264f85596c95'), 'Hssiss': ('15770318', '698224c64e0dc7474973b85afe93760f3cebca3810e5e31f1a5cf8aecaf85ffd'), 'Mira': ('15603403', '5f1beb6431bbe8088943b743b1d7ac746d318cd86453057416f438f1eaa80729'), 'Mission Vao': ('15780095', '30f5f0d770f1c2e136bda4af83e07969e457814b7f0bdf80885cc6878728d126'), 'Sword of Ajunta Pall': ('15789481', '7131ef19f9d94294847eef3d320c92bdd96c12d062bc756a25718776bd84a3f4'), 'Tulak Hord': ('15192676', '3550a0cb1f76e8e6bf7e8f456c22b582cb8398d051f883ecf4ca9c63587c5be2'), 'Undercity (Taris)': ('15807685', '5c1e1bccdc2dcd3eeff0294715d5fc73699b40246a21829be0ffcd3f4af7c481'), 'Unidentified Aqualish (North Apartments)': ('15775429', 'cab6d8387a475a4a2d218f89624c8e2bfccd6144f63ad3ad76dbc7ca7435ff15'), 'Unidentified Republic diplomat': ('15777011', '7f7063d2ed0007b037fe5dd91fb8ffb5b5b738bd0b5d9ff030694e9788e15a84')}
ALLOW={'biography','personality and traits','powers and abilities','skills and abilities','equipment','history','description','society and culture','gu-vandi in the galaxy','biology and appearance','force sensitivity'}
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
assert sha(output)=='3b8ef66e8086cffc025f47a22450cbd223c11c91b7567c68da30da88d6e58040';Path('data/wookieepedia-kotor-quote-followup-replacements.jsonl').write_text(output);Path('evaluation/kotor-quote-followup-replacement-holds.json').write_text(json.dumps({'description':'Section fragments empty after removal or held by overlap screening. This is not a rights determination.','source_archive_sha256':ARCHIVE,'held':held},ensure_ascii=False,indent=2)+'\n')
print('Included sections',len(rows),'held',len(held),'by subject',{t:sum(r['subject']==t for r in rows) for t in PINS},'sha256',sha(output))
