"""Publish screened revision-pinned SWTOR character and faction sections."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Arcann': ('15794269', '2d60d11800f7bf0e584d407fc6a9c2c1e1e60e6e08b68cdb32ed78d3da5197d9'), 'Indo Zal': ('14800007', '40a5648b9fedfb5cd35ab741db42a0112b5c5c8e6285d3253c343bcd648e98e5'), 'Knights of Zakuul': ('15802582', '2ea52f545410b9e0c115a881f0452baaf731a1f24d4362f817b16095bcc4260c'), 'Koth Vortena': ('15324650', 'de6cf3186e18c2612390ce94b25efcf6162eae8d7ef366d59bf23783749926c7'), 'Len Parvek': ('15803035', 'df5cc13ef9cae526b5af7fc87ff28fdb70198dd5f85ea00d345a2b2fedeff8e4'), 'Tenebrae': ('15806866', '3eca405cff7fbf2c00f4abe064aae934b1b82e5ca2da498164ab48f69eb866e7'), 'Thexan': ('15807006', 'a66bddb33c7a8a8ff8898707f036c31eb7ad0095d92d37f93fe33ead16db8c9f'), 'Unidentified Knight of Zakuul (Iokath)': ('15808551', 'd2ee4c3f41fcc5a637cb412d80464910e2ff246aec8152517e19a7d91a3624f0'), 'Vaylin': ('15808970', '75eb53b0eb666e3c2809f38698287abdb98fc204fb72242238671fbbeea12964')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Arcann', 'Indo Zal', 'Knights of Zakuul', 'Koth Vortena', 'Len Parvek', 'Tenebrae', 'Thexan', 'Unidentified Knight of Zakuul (Iokath)', 'Vaylin'];result=[]
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
for name in names:
 v=x[name];raw=v['raw_wikitext'];assert (v['revision_id'],hashlib.sha256(raw.encode()).hexdigest())==PINS[name] and re.match(r'(?is)^\{\{Top\|[^}]*\bleg\b',raw);code=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw)); bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):bad.extend(p.value.strip_code() for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):bad.append(t.contents.strip_code())
 sections=[]
 for i,h in enumerate(heads):
  if len(h.group(1))!=2:continue
  end=next((q.start() for q in heads[i+1:] if len(q.group(1))<=2),len(raw)); body=raw[h.end():end];namehead=h.group(2).strip()
  if namehead.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):bad.append(mwparserfromhell.parse(body).strip_code());continue
  if namehead.casefold() not in ('biography','history','organization and philosophy','personality and traits','powers and abilities'):continue
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
 assert r['sections']
 for z in r['sections']:
  assert z['text'] and z['overlap']==0 and not z['unresolved_quote']
  url='https://starwars.fandom.com/wiki/'+quote(r['title'].replace(' ','_'),safe=':_()')
  rows.append({'title':r['title']+' — '+z['section'],'section':z['section'],'url':url,'source_revision_url':url+'?oldid='+r['revision_id'],'revision_id':r['revision_id'],'timestamp':r['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':r['raw_wikitext_sha256'],'section_wikitext_sha256':z['raw_sha256'],'text':z['text'],'text_sha256':hashlib.sha256(z['text'].encode()).hexdigest(),'omitted_inline_quotations':z['quotes'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Selected contributor narrative, not complete article or game content. Marked quotations, templates and references removed; eight-word screen does not establish rights for unmarked excerpts. Player choices and branches may be simplified or omitted.','embedded':False})
rows.sort(key=lambda x:(x['title'],x['section']));out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='8283ad22fad20a37b374856f5046363eec6aaa08963604bf8a82b6106335b82f';Path('data/wookieepedia-swtor-expansion-character-sections.jsonl').write_text(out);print('Included',len(rows),'sections across',len(result),'pinned articles; output sha256',hashlib.sha256(out.encode()).hexdigest())
