"""Publish screened revision-pinned SWTOR expansion world and faction sections."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Zakuul': ('15809562', '74598942e0388ed81f347599b798a66ee14a2079a8e1686480b5fafa3b26292a'), 'Eternal Empire': ('15799869', 'da888e1060dfe87bef971330e521d3bce5452d967976a9a1e7ce82ee1d0eee30'), 'GEMINI': ('14991373', '49a9d64786ecb7a754268f4a2ffb0056b2d7d6da2b9868da49c2b1ca59260131'), 'Eternal Throne': ('14986353', 'af2f652df699afcaa4216c91339d3df3786f428695d7ebd5dd7e89d70c53ef56'), 'Eternal Fleet': ('15766299', 'ca579c6b9207ffda4bd2c9469802ea4f4ea8bb6d8cb241161a0f52b3c6673ff7'), 'Order of Zildrog': ('15652508', '9e772db186a0f560a17d879a98b3fcc7d0cdac94c12f2ca100f10f2d91ed7cf6'), 'Horizon Guard': ('15533002', '3e21be4f43c9b16bbe7b10a351077df3275495e34263269ac7640a3c9b8990b8'), 'Skytrooper': ('15787215', '692b790cdb6cdb34273835001ccd3b5d4ad9b936df2088e66bce9c194f13357a'), 'Eternal Fleet flagship': ('15799876', '568ecc50b7bace87822d8c7f1d3e5d33413b0d0f3776c65d3be10e0344562db1'), 'Eternal Flagship': ('15446714', '830798cb383c71bfed247cfb6bed5659e47834cad8258d3e199eca63ddf9747a'), 'Heskal': ('14662523', '36fc99fc0359cef8418d83f48ef9be6f9eb601d3579dc37cf13855fe52e1a36f'), 'Endless Swamp': ('15658238', '998d48a956f0290f888457e104df7cddcda60921ace59ae6812e0adbcb76749f'), 'Scions of Zakuul': ('14421491', '6811dfa35d379ef68d395cbef7b38a47eb661363621eb3ae7bdcb59596049940'), 'Watcher Izax': ('14677158', 'ebaf622cc59a839e6662d8927eaff13044bb61010749da54a0ed062f13d81c39'), 'Old World': ('15784063', '834fad50448b7dd12dc8eec066c7307737142cf6610566a30e66577747c313a9'), 'Eternal Empire shuttle': ('15766297', '471064a26cbdd5980b14ed3d119e79d0fb90ff9407102678dc2469ad722bbd9c'), 'Eternal Fleet warship': ('15799878', 'f859afb907446d4bc32430029e36f9167687042576ef48ae6d72997f3bba89c3'), 'Eternal Empire military': ('15766296', '37440f84a7bb4dab8c4d609611b959d75317e04f46b3af12ea6172842d9b0be4')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Zakuul', 'Eternal Empire', 'GEMINI', 'Eternal Throne', 'Eternal Fleet', 'Order of Zildrog', 'Horizon Guard', 'Skytrooper', 'Eternal Fleet flagship', 'Eternal Flagship', 'Heskal', 'Endless Swamp', 'Scions of Zakuul', 'Watcher Izax', 'Old World', 'Eternal Empire shuttle', 'Eternal Fleet warship', 'Eternal Empire military'];result=[]
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
  if namehead.casefold() not in ('biography','history','organization','organization and philosophy','description','characteristics','culture','personality and traits','powers and abilities'):continue
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
rows.sort(key=lambda x:(x['title'],x['section']));out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='8f34f7638b6528fda365aa686ee10897492f3126b3acf68f8ef81081e42c778e';Path('data/wookieepedia-swtor-expansion-world-sections.jsonl').write_text(out);print('Included',len(rows),'sections across',len(result),'pinned articles; output sha256',hashlib.sha256(out.encode()).hexdigest())
