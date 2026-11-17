"""Publish screened revision-pinned anthology story plot sections."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Shadows and Light': ('15611457', '15db0f837c4ba3e0eddd3fad06c95ab4c8d3dab33d7e0c01d0793defadb3de8e'), 'Unseen, Unheard': ('15609189', 'cac1573873c792b743ca9207b6d775902aed47b3984bb736b93c8ea17dae9a3c'), 'Heart of Darkness': ('15611361', '81c7d8d44c6c85face9ebefccfb8f4a9a858b2867125086bf84b2a57fab99bc1'), 'All for You': ('15611406', '8c25632b2575e613c41566eaad5fe2779e7007f973f97fcf7f15df5734f8f2e3'), 'The Apprentice (comic story)': ('15597086', 'da9389021af652539ecb1f757d8281a08bd188ea475ddc2f7b981f635cc63a90')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Shadows and Light','Unseen, Unheard','Heart of Darkness','All for You','The Apprentice (comic story)'];result=[]
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
  text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text);sections.append({'section':namehead,'text':text,'quotes':n,'raw_sha256':hashlib.sha256(body.encode()).hexdigest()})
 for s in sections:s['overlap']=sum(bool(sh(s['text'])&sh(z)) for z in bad);s['unresolved_quote']=bool(re.search(r'["“”]',s['text']))
 result.append({'title':name,'revision_id':v['revision_id'],'timestamp':v['timestamp'],'raw_wikitext_sha256':v['raw_wikitext_sha256'],'sections':sections})
rows=[]
for r in result:
 assert len(r['sections'])==1
 z=r['sections'][0];assert z['text'] and z['overlap']==0 and not z['unresolved_quote']
 url='https://starwars.fandom.com/wiki/'+quote(r['title'].replace(' ','_'),safe=':_()')
 rows.append({'title':r['title'],'section':z['section'],'url':url,'source_revision_url':url+'?oldid='+r['revision_id'],'revision_id':r['revision_id'],'timestamp':r['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':r['raw_wikitext_sha256'],'section_wikitext_sha256':z['raw_sha256'],'text':z['text'],'text_sha256':hashlib.sha256(z['text'].encode()).hexdigest(),'omitted_inline_quotations':z['quotes'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Secondary plot section only, not comic pages or complete narrative. Marked quotations and templates removed; screen does not establish rights for unmarked excerpts. Some stories have uncertain or adjacent chronology.','embedded':False})
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='323f71835f0c2344591004e666d50962a5b6e81c651df5c7c0e7dead50f37632';Path('data/wookieepedia-anthology-story-plots.jsonl').write_text(out);print('Included',len(rows),'pinned story plots; output sha256',hashlib.sha256(out.encode()).hexdigest())
