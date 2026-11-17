"""Publish screened revision-pinned Bane novel plot sections."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Darth Bane: Rule of Two': ('15799894', '09d15977b52728b71f29d09d09cc42d3ae6e1eb7dd2e50b425d2e507798e1d8c'), 'Darth Bane: Dynasty of Evil': ('15621652', '5f4295f9f9691a394d1c3c2a4b3cbf92116e1016727993c721c03675726cc3bd')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Darth Bane: Rule of Two', 'Darth Bane: Dynasty of Evil'];result=[]
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
for name in names:
 v=x[name];raw=v['raw_wikitext'];assert (v['revision_id'],hashlib.sha256(raw.encode()).hexdigest())==PINS[name] and raw.startswith('{{Top|rwm');code=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw)); bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):bad.extend(p.value.strip_code() for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):bad.append(t.contents.strip_code())
 sections=[]
 for i,h in enumerate(heads):
  if len(h.group(1))!=2:continue
  end=next((q.start() for q in heads[i+1:] if len(q.group(1))<=2),len(raw)); body=raw[h.end():end];namehead=h.group(2).strip()
  if namehead.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):bad.append(mwparserfromhell.parse(body).strip_code());continue
  if namehead.casefold() not in ('plot summary',):continue
  c=mwparserfromhell.parse(body)
  for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
  for t in list(c.filter_tags(recursive=True)):
   if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
    try:c.remove(t,recursive=True)
    except ValueError:pass
  for l in list(c.filter_wikilinks(recursive=True)):
   if str(l.title).strip().casefold().startswith(('file:','image:','category:')):
    try:c.remove(l,recursive=True)
    except ValueError:pass
  text=c.strip_code(normalize=True,collapse=True).strip(); omitted='She decides that the time has come, and that upon returning from Doan, she will challenge Bane for the mantle of Dark Lord of the Sith.'; assert (text.count(omitted)==1 if name=='Darth Bane: Dynasty of Evil' else text.count(omitted)==0); text=text.replace(omitted,'[sentence omitted due to publisher-summary overlap]'); omitted2="Bane argues that he only sought Andeddu's holocron because Zannah had not challenged him and that if Zannah wants the mantle of Dark Lord of the Sith, she must take it from him while he is in his prime, not once he has been weakened by old age."; assert (text.count(omitted2)==1 if name=='Darth Bane: Dynasty of Evil' else text.count(omitted2)==0); text=text.replace(omitted2,'[sentence omitted due to publisher-summary overlap]');text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text);sections.append({'section':namehead,'text':text,'quotes':n,'raw_sha256':hashlib.sha256(body.encode()).hexdigest()})
 for s in sections:s['overlap']=sum(bool(sh(s['text'])&sh(z)) for z in bad);s['unresolved_quote']=bool(re.search(r'["“”]',s['text']))
 result.append({'title':name,'revision_id':v['revision_id'],'timestamp':v['timestamp'],'raw_wikitext_sha256':v['raw_wikitext_sha256'],'sections':sections})
rows=[]
for r in result:
 assert len(r['sections'])==1
 z=r['sections'][0];assert z['text'] and z['overlap']==0 and not z['unresolved_quote']
 url='https://starwars.fandom.com/wiki/'+quote(r['title'].replace(' ','_'),safe=':_()')
 rows.append({'title':r['title'],'section':z['section'],'url':url,'source_revision_url':url+'?oldid='+r['revision_id'],'revision_id':r['revision_id'],'timestamp':r['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':r['raw_wikitext_sha256'],'section_wikitext_sha256':z['raw_sha256'],'text':z['text'],'text_sha256':hashlib.sha256(z['text'].encode()).hexdigest(),'omitted_inline_quotations':z['quotes'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Secondary plot section only, not original novel text or complete narrative. Marked quotations and templates removed; screen does not establish rights for unmarked excerpts. Some stories have uncertain or adjacent chronology.','omitted_overlap_sentences':2 if r['title']=='Darth Bane: Dynasty of Evil' else 0,'embedded':False})
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='f29be746a0d2127f8a9c3b01b52c16c82b15333ea9416076da966fb8d1831bca';Path('data/wookieepedia-bane-novel-plots.jsonl').write_text(out);print('Included',len(rows),'pinned novel plots; output sha256',hashlib.sha256(out.encode()).hexdigest())
