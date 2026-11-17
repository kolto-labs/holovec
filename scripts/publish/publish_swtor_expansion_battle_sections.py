"""Publish pinned SWTOR battle and escape sections after quotation screening."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Assault on Odessen': ('15195877', '9b82e2972e9d555e782b6f28f6b3a47b27d571f6009be0e69941ad0b3ab84a5c'), 'Battle of Asylum': ('15795171', '13a13457f9af860cfd9d437e8ef2ef8a563bc7200bd5764c4118620058041d16'), 'Battle of Odessen': ('14970683', '3c9ecbd397a02d40aaf3eafe3c86722f37f23e143576d997a9586ba455070496'), 'Invasion of Voss': ('15000240', 'c1756a411b4a53b6ede77787e4c3b04ade5c24e6b5ac4f8329436ece743df7ae'), 'Escape from Iokath': ('15799823', '222ec889c88f2cb0dd377add95153ab2690bab42741e915379d98f5f6c3eda3f'), 'Assault on the Gravestone': ('14968941', '99d29d7e496cf5530eb1e5f67cbdffbacfd3b30bdf3f349ebc9e6019f7554773')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Assault on Odessen','Battle of Asylum','Battle of Odessen','Invasion of Voss','Escape from Iokath','Assault on the Gravestone'];result=[]
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
for name in names:
 v=x[name];raw=v['raw_wikitext'];assert (v['revision_id'],hashlib.sha256(raw.encode()).hexdigest())==PINS[name];code=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw)); bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):bad.extend(p.value.strip_code() for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):bad.append(t.contents.strip_code())
 sections=[]
 for i,h in enumerate(heads):
  if len(h.group(1))!=2:continue
  end=next((q.start() for q in heads[i+1:] if len(q.group(1))<=2),len(raw)); body=raw[h.end():end];namehead=h.group(2).strip()
  if namehead.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):bad.append(mwparserfromhell.parse(body).strip_code());continue
  if namehead.casefold() not in ('prelude','the battle','the escape','the assault','aftermath'):continue
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
  text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text);sections.append({'section':namehead,'text':text,'quotes':n,'raw_sha256':hashlib.sha256(body.encode()).hexdigest()})
 for s in sections:s['overlap']=sum(bool(sh(s['text'])&sh(z)) for z in bad);s['unresolved_quote']=bool(re.search(r'["“”]',s['text']))
 result.append({'title':name,'revision_id':v['revision_id'],'timestamp':v['timestamp'],'raw_wikitext_sha256':v['raw_wikitext_sha256'],'sections':sections})
rows=[]
for r in result:
 assert len(r['sections'])==3
 for z in r['sections']:
  assert z['text'] and z['overlap']==0 and not z['unresolved_quote']
  url='https://starwars.fandom.com/wiki/'+quote(r['title'].replace(' ','_'),safe=':_()')
  rows.append({'title':r['title']+' — '+z['section'],'section':z['section'],'url':url,'source_revision_url':url+'?oldid='+r['revision_id'],'revision_id':r['revision_id'],'timestamp':r['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':r['raw_wikitext_sha256'],'section_wikitext_sha256':z['raw_sha256'],'text':z['text'],'text_sha256':hashlib.sha256(z['text'].encode()).hexdigest(),'omitted_inline_quotations':z['quotes'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Selected narrative section only. Marked quotations, templates and references removed; eight-word screen does not establish rights for unmarked excerpts. Not original game content or complete story branches.','embedded':False})
rows.sort(key=lambda x:(x['title'],x['section']));out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='173c0af7148e04bd717c020aa017ec9f88798a48d590314de5f3ef5b74b4b39b';Path('data/wookieepedia-swtor-expansion-battle-sections.jsonl').write_text(out);print('Included',len(rows),'sections across',len(result),'pinned articles; output sha256',hashlib.sha256(out.encode()).hexdigest())
