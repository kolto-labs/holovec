"""Publish screened leads for six expansion pages missing from an older census."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Eternal Empire trooper': ('15533197', '773dcf18d73374d53586df91ecb90508669af645b849ab5cc37c364055e659c3'), 'Eternal Empire Special Operator': ('15533199', 'b982b9e705e744573ad33785995c90340ea4873f88f36873eb0f1548b19f4abd'), 'Detention Block Guard': ('15533220', '8d2c8757bae70612cd5dac06dbad01e97d7b7345ff13301d150001fb317e5be2'), 'Rokka Rey': ('15806069', '12eb65801fd44b260e6610b23e676f49bbdbcf620e6d273e59fb3c025f40663f'), "Koth Vortena's warship": ('15802633', '780777b2693d617c86dd5622811ea185ef5427e860a391327fe30a58034b7c7d'), 'Zakuul Taxi': ('15013967', 'c3cbd294347cb875943fcc24b355fbfde473aeef3a1d6c9fd867fe09d4e72a6c')}
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456' and set(bundle['records'])==set(PINS);rows=[]
for name,v in sorted(bundle['records'].items()):
 raw=v['raw_wikitext'];assert (v['revision_id'],sha(raw))==PINS[name] and re.match(r'(?is)^\{\{Top\|[^}]*\bleg\b',raw)
 full=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:heads[0].start()] if heads else raw;omitted=[]
 for t in full.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):omitted.extend(p.value.strip_code() for p in t.params)
 for t in full.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):omitted.append(t.contents.strip_code())
 for i,h in enumerate(heads):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((z.start() for z in heads[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));omitted.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
 c=mwparserfromhell.parse(lead)
 for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for l in list(c.filter_wikilinks(recursive=True)):
  if str(l.title).strip().casefold().startswith(('file:','image:','category:')):
   try:c.remove(l,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text);assert text and not re.search(r'["“”]',text) and not any(sh(text)&sh(z) for z in omitted)
 url='https://starwars.fandom.com/wiki/'+quote(name.replace(' ','_'),safe=':_()')
 rows.append({'title':name+' — introduction','url':url,'source_revision_url':url+'?oldid='+v['revision_id'],'revision_id':v['revision_id'],'timestamp':v['timestamp'],'source_archive_sha256':bundle['archive_sha256'],'full_page_wikitext_sha256':sha(raw),'lead_wikitext_sha256':sha(lead),'text':text,'text_sha256':sha(text),'omitted_inline_quotations':n,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Selected wiki introduction, not complete article or game content. Marked quotations and templates omitted; unmarked third-party excerpt rights remain unverified.','embedded':False})
out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert sha(out)=='36f19782021b0db71ef14b708209487ab3cdb1265e6f013946e54956be652f78';Path('data/wookieepedia-swtor-expansion-new-introductions.jsonl').write_text(out);print('Included',len(rows),'leads; output sha256',sha(out))
