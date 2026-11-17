"""Publish screened, revision-pinned SWTOR event and mission sections."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Ambush on Dromund Kaas': ('15793983', '32d9c30e45be1b08368d787dcb15195b207e115bcb1f4e0bffc9214ca623e811'), 'Assassination of Valkorion': ('15435833', '0584099463af7285b08d94841cf82c2c679058a2012f48d575c31f6c51d6512b'), 'Attack on Korriban': ('15622275', '3a984f7fe3d46eaa400fc77f60af376c4e678576a5818cee8701ad8cc530fd30'), 'Battle of Zakuul': ('15226997', '7090f17c79527a6759fac39cd4ad74d6fc396c62f59ab104cd3ad9bcd4468d9a'), "Destruction of Darth Marr's flagship": ('15799050', 'bb5653f46617ab80f6bea20a48d2f79191db5d690d6e9c696ee45419773fefc3'), 'Escape from the Coil': ('15429284', '927722bc0fe8b7598d7363070db1d3c9c3b8e43443e223fcc92291dc4ca41873'), 'Eternal Empire conquest': ('15704569', '32b9f709139531e1004c83239ce9317675fd9b561dd0e416b57ff667ad01dd97'), 'GEMINI trap': ('15800969', '80d3f56b0e1adbe519c6f6d16143edc4d573764adffd12f7c0ffb705af868f02'), 'Grand Festival of Empress Vaylin': ('15768831', '519005be20148af60549ff637dda321972fb05e7694d29060ef6492c9aa78fd6'), 'Mission to Nathema': ('15429380', '295fa97321204b868e78b29ad860f9e4f11dff5a9ed5260312b27cfbd663ba60'), 'Mission to Zakuul listening post': ('15474313', '8581efed8b7aa6f671c140782f87ae19756584635fef740315dca7ff1759c9bd'), 'Mission to the hyperwave relay station': ('15429379', '93ca98a4fa37cf37f48630d05748115f03f92e764dc4f38d06e3762b44b0a673'), 'Raid on Darvannis': ('15805892', '81e0e87ce2338206c1237ae7f257759a02f2812c08fd39be9cf43e3af6d527b0'), 'Raid on the Gilded Star': ('15418465', '263e246d4661e7a0b7b5f13ec86aff331adee77caeb8426f2b377600fb87d2e9'), 'Raid on the Overwatch': ('14982632', '70a93c71837961328d907df9d0ba746da1120fd281622419904c256535e5015a'), 'Rakghoul pandemic': ('15789187', 'a8b0078f9f0915ac5e67176cb87d8dce8eaea3372ed76022b867195a2b0f46bd'), 'Reclamation Service Yavin 4 expedition': ('15789694', '15bba51877b93b8da90ee53d51ae644330b3647f0a6d727ef00815ab376f3d49'), 'Rescue of the Outlander': ('15820917', 'ca9363346f93ced031756a15d3809cec0b01698d1dcd713a615d6bd72de05ed7')}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=bundle['records']; names=['Ambush on Dromund Kaas', 'Assassination of Valkorion', 'Attack on Korriban', 'Battle of Zakuul', "Destruction of Darth Marr's flagship", 'Escape from the Coil', 'Eternal Empire conquest', 'GEMINI trap', 'Grand Festival of Empress Vaylin', 'Mission to Nathema', 'Mission to Zakuul listening post', 'Mission to the hyperwave relay station', 'Raid on Darvannis', 'Raid on the Gilded Star', 'Raid on the Overwatch', 'Rakghoul pandemic', 'Reclamation Service Yavin 4 expedition', 'Rescue of the Outlander'];result=[]
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
for name in names:
 v=x[name];raw=v['raw_wikitext'];assert (v['revision_id'],hashlib.sha256(raw.encode()).hexdigest())==PINS[name] and raw.startswith('{{Top|leg');code=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw)); bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):bad.extend(p.value.strip_code() for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):bad.append(t.contents.strip_code())
 sections=[]
 for i,h in enumerate(heads):
  if len(h.group(1))!=2:continue
  end=next((q.start() for q in heads[i+1:] if len(q.group(1))<=2),len(raw)); body=raw[h.end():end];namehead=h.group(2).strip()
  if namehead.casefold() in ("publisher's summary",'official description','opening crawl','back cover'):bad.append(mwparserfromhell.parse(body).strip_code());continue
  if namehead.casefold() not in ('prelude','the battle','the escape','the assault','aftermath','the ambush','the confrontation','the attack',"valkorion's trap",'escape','the war','the mission','the celebration','background','the heist','the raid','history','the expedition','the rescue'):continue
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
  rows.append({'title':r['title']+' — '+z['section'],'section':z['section'],'url':url,'source_revision_url':url+'?oldid='+r['revision_id'],'revision_id':r['revision_id'],'timestamp':r['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':r['raw_wikitext_sha256'],'section_wikitext_sha256':z['raw_sha256'],'text':z['text'],'text_sha256':hashlib.sha256(z['text'].encode()).hexdigest(),'omitted_inline_quotations':z['quotes'],'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Selected narrative section only. Marked quotations, templates and references removed; eight-word screen does not establish rights for unmarked excerpts. Not original game content or complete story branches.','embedded':False})
rows.sort(key=lambda x:(x['title'],x['section']));out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert hashlib.sha256(out.encode()).hexdigest()=='0f541eb9b4855671d0c6779d9913248fdd57628c3d4c5c4b49a5393c4fade0c6';Path('data/wookieepedia-swtor-expansion-event-sections.jsonl').write_text(out);print('Included',len(rows),'sections across',len(result),'pinned articles; output sha256',hashlib.sha256(out.encode()).hexdigest())
