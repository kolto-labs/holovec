"""Publish six reviewed real-world issue introductions from a pinned wiki snapshot.

Input is local-only extracted wikitext. No primary comic content or inference.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
PINS={'1': ('14755548', 'ac1d1eefa09369586a815b73255597976f6aaecc8e1b6600216273c45e7212ad'), '2': ('14738226', '65eedd027523074dde1652aa3804b9992dae0fa5780f96da123330d0f5ac2943'), '3': ('14755549', '899620ef09d727667388306c4f8b5b8a85cfd4b7a8cf05d8f794063ec9490854'), '4': ('14755550', 'a721a36b31696e5401daa132a69ad6efb43cfb5ab5b5c7643625bd4809605a62'), '5': ('14755552', '7f4df5ccbd99fc981d6f628153d9053c820ffc0fd438ce714062c8fe012488e4'), '6': ('15786921', '82d091352cc21be06d0ce813009071d0040e897f4c6a141b432b8c61adc0cad6')}
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());assert x['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';rows=[]
for n in range(1,7):
 title=f'Jedi vs. Sith {n}';v=x['records'][title];raw=v['raw_wikitext'];assert (v['revision_id'],sha(raw))==PINS[str(n)] and v['raw_wikitext_sha256']==sha(raw) and v['work_id']==f'jedi-vs-sith-{n:03}'
 c=mwparserfromhell.parse(raw);tops=[t for t in c.filter_templates(recursive=False) if str(t.name).strip().casefold()=='top'];assert any(str(p.value).strip().casefold()=='rwm' for t in tops for p in t.params)
 heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:heads[0].start()];omitted=[]
 for t in c.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):omitted.extend(p.value.strip_code() for p in t.params)
 for t in c.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):omitted.append(t.contents.strip_code())
 for i,h in enumerate(heads):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((q.start() for q in heads[i+1:] if len(q.group(1))<=len(h.group(1))),len(raw));omitted.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
 code=mwparserfromhell.parse(lead)
 for t in list(code.filter_templates(recursive=False)):code.remove(t,recursive=True)
 for t in list(code.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:code.remove(t,recursive=True)
   except ValueError:pass
 text=code.strip_code(normalize=True,collapse=True).strip();assert text and not re.search(r'["“”]',text) and not any(shingles(text)&shingles(z) for z in omitted)
 rows.append({'title':title+' — publication introduction','url':v['url'],'source_revision_url':v['url']+'?oldid='+v['revision_id'],'revision_id':v['revision_id'],'timestamp':v['timestamp'],'source_archive_sha256':x['archive_sha256'],'full_page_wikitext_sha256':sha(raw),'lead_wikitext_sha256':sha(lead),'text_sha256':sha(text),'text':text,'work_id':v['work_id'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','coverage':'Real-world publication introduction only; no issue plot, comic pages or publisher text. Unmarked third-party excerpts remain unverified.','embedded':False})
out=''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows);Path('data/wookieepedia-jedi-vs-sith-introductions.jsonl').write_text(out);print('Included',len(rows),'revision-pinned issue introductions',sha(out))
