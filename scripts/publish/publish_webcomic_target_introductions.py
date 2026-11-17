"""Publish screened leads for six expansion pages missing from an older census."""
import json,re,hashlib,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Rimma Trade Route/Legends': ('15806043', '43646f27c0c2de42fcaf6b3a5f5a338520af8c1ea4eba612693cb559549aa9e1'), 'Commander/Legends': ('15826633', '0091539e1bcfad2852e3ead5df9e36e557b8e24f5be7a8a61b8a720faced5467'), 'Ray shield/Legends': ('15789478', '79ef5f05666df9bb1422ddfbcf31620bb0b01b1daa74e26618f43ad76885b886'), 'Bomb/Legends': ('15823394', '322f33c4e5335276b70ac840575c9775bb521a7fc9428a23e454dca9cde4956c'), 'Sith training saber': ('14453692', '59cc3fe94fb391b1f63dd05f1f0edc4de8bcd40fb088342531d3c6a8d7413b5c')}
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
bundle=json.load(open(sys.argv[1]));assert bundle['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456' and set(bundle['records'])==set(PINS) and set(bundle['missing'])=={'Mantras of Maraugurs','Toxical-coma gas'};rows=[]
for name,v in sorted(bundle['records'].items()):
 raw=v['raw_wikitext'];assert (v['revision_id'],sha(raw))==PINS[name] and (name.endswith('/Legends') or re.match(r'(?is)^\{\{Top\|[^}]*\bleg\b',raw))
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
out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);assert sha(out)=='d442cd224ead22a3e40545046f3783d428134b0827e8f44b3a618fd0274e07c4';Path('data/wookieepedia-webcomic-target-introductions.jsonl').write_text(out);print('Included',len(rows),'leads; output sha256',sha(out))
