"""Extract limited quote-screened secondary context for KOTOR: War.

Input is a locally recovered pinned Wookieepedia revision; no model is used.
Marked-quotation screening is incomplete and does not clear unmarked excerpts.
"""
import hashlib,json,re,sys,mwparserfromhell
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text());raw=x['raw'];digest=hashlib.sha256(raw.encode()).hexdigest()
if x['id']!='15810710' or digest!='0e3f18b80a7b57e62b2d4e302fee6369275d4185e242c7a71dbf9819c6a0cc07':raise ValueError('unexpected revision')
source=raw.split('===Drafted===',1)[1].split('\n===',1)[0];code=mwparserfromhell.parse(source)
for tag in list(code.filter_tags(recursive=True)):
 if str(tag.tag).lower() in ('ref','references','gallery','blockquote','q'):
  try:code.remove(tag,recursive=True)
  except ValueError:pass
for t in list(code.filter_templates(recursive=False)):code.remove(t,recursive=True)
text=code.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
if re.search(r'["“”]',text):raise ValueError('unresolved quotation marker')
words=lambda s:re.findall(r'\w+',s.casefold())
def shingles(s):
 w=words(s);return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
full=mwparserfromhell.parse(raw);q=[]
for t in full.filter_templates(recursive=True):
 if str(t.name).strip().casefold().replace('_',' ') in {'quote','quotation','blockquote','quote box','dialogue','speech','cquote','quote frame'}:
  for param in t.params:q.append(mwparserfromhell.parse(str(param.value)).strip_code(normalize=True,collapse=True))
 else:
  for param in t.params:
   if str(param.name).strip().casefold() in ('quote','quotation'):q.append(mwparserfromhell.parse(str(param.value)).strip_code(normalize=True,collapse=True))
for tag in full.filter_tags(recursive=True):
 if str(tag.tag).casefold() in ('blockquote','q'):q.append(mwparserfromhell.parse(str(tag.contents)).strip_code(normalize=True,collapse=True))
qset=set().union(*(shingles(v) for v in q)) if q else set()
if shingles(text)&qset:raise ValueError('overlap with marked quotation; review needed')
url='https://starwars.fandom.com/wiki/Zayne_Carrick';row={'title':'Zayne Carrick — Drafted (Knights of the Old Republic: War)','section':'Drafted','url':url,'source_url':url,'source_revision_url':url+'?oldid='+x['id'],'revision_id':x['id'],'timestamp':x['timestamp'],'source_page_wikitext_sha256':digest,'section_wikitext_sha256':hashlib.sha256(source.encode()).hexdigest(),'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'license':'CC BY-SA 3.0','license_url':'https://creativecommons.org/licenses/by-sa/3.0/','attribution':'Wookieepedia contributors; see linked revision history','continuity':'Legends','evidence_class':'secondary','issue_context':['kotor-war-001','kotor-war-002','kotor-war-003','kotor-war-004','kotor-war-005'],'extraction':'References, templates and quotation-marked words omitted; exact eight-word overlap against marked quote-template parameters and quote tags on full source page screened.','omitted_inline_quotations':n,'coverage':'Character-level War arc overview; not a complete issue summary, original comic, exhaustive branch coverage or rights clearance for unmarked excerpts.','embedded':False}
Path('data/wookieepedia-war-zayne-summary.jsonl').write_text(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');print('Included one section; length',len(text),'marked quote blocks',len(q),'omissions',n)
