"""Prepare limited wiki-authored narrative from pinned revisions of held KOTOR subjects.

Markup extraction is lossy; a quote screen cannot clear unmarked third-party text.
Usage: PYTHONPATH=<mwparserfromhell> python publish_kotor_core_replacements.py <raw-bundle.json>
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'Arkadia Calimondra': ('15022663', '69b8920bcff0999dc4b60798d0642cb40e24d29d648c766207e54076d0ae6326'), 'Assault on the Tingel Arm region': ('15756568', 'ba63a890eab33d54b76ca99e176bbd6e730d357dd1f02d5cd5544df2101763ad'), 'Barel Ovair': ('14658638', '300974227fb3689fed61257d39d5c081f91c64299e86fd59fd175e8bbf28e9e5'), 'Dark Lord of the Sith/Legends': ('15798456', '46ba83e4e0fd64baf2aa3b75624a453187de936fb8bd3b3e003aa0cfd1a51d74'), 'Darth Marr': ('15764204', '52ce982aea623777d25d39fcd354f191deb424943e323db21f32aaa1e6e9e297'), 'Edell Vrai': ('15767081', '2a43cc0c26e56cdc48250c5995152b2db9c6741135592c80c93c228164d269d1'), 'Eison Gynt': ('15766201', 'b67bd6a92b2e741d8b1c0b25d597444d1dd767c7d2135105231347ee85714029'), 'Kerra Holt': ('15360127', '0f193591a2afdde5c78f2cc9b69c16e49a52fb4e8d9df7846f17fd39e96c137b'), 'Republic Dark Age': ('15791817', '97ebd67074a4190fe7ab586c04875144f6a9c06b8f9f35bcea502dc87133bcb5'), 'Sith Master/Legends': ('15792945', 'b3c94a78c417cd0be574d2565b7531d76471238a439369108b83aad550d6bc2f'), 'Valley of the Dark Lords/Legends': ('15808938', 'e8a57c383570931cf162fbd01755abcbba9159605d442face248dcfd68be8317')}
ALLOW={'biography','personality and traits','powers and abilities','equipment','history','prelude','the assault','aftermath','layout'}
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
  rows.append({'title':title+' — '+section,'subject':title,'subject_scope':'cross-era; some sections may be outside Old Republic' if title in {'Dark Lord of the Sith/Legends','Sith Master/Legends','Valley of the Dark Lords/Legends'} else 'Old Republic-related or adjacent; relevance varies by section','section':section,'url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':v['timestamp'],'source_archive_sha256':ARCHIVE,'full_page_wikitext_sha256':digest,'section_wikitext_sha256':sha(body),'text':text,'text_sha256':sha(text),'omitted_inline_quotations':n,'omitted_overlap_paragraphs':omitted,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Partial wiki-authored narrative. Marked quotations, overlapping paragraphs, templates and references removed; this may lose context. The screen does not clear unmarked excerpts or establish game-branch completeness.','embedded':False})
rows.sort(key=lambda x:(x['subject'],x['section']));output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
assert sha(output)=='b0cbcca8520234409ea282d4d372287d420bffb07be9093c3bafdfc94f0b00f0';Path('data/wookieepedia-old-republic-batch2-replacements.jsonl').write_text(output);Path('evaluation/old-republic-batch2-replacement-holds.json').write_text(json.dumps({'description':'Section fragments empty after removal or held by overlap screening. This is not a rights determination.','source_archive_sha256':ARCHIVE,'held':held},ensure_ascii=False,indent=2)+'\n')
print('Included sections',len(rows),'held',len(held),'by subject',{t:sum(r['subject']==t for r in rows) for t in PINS},'sha256',sha(output))
