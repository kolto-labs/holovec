"""Publish two reviewed leads from a locally extracted, hash-pinned wiki snapshot.

Input is a local-only JSON review file with raw wikitext; no model calls.
The abbreviated snapshot records are secondary and do not clear unmarked excerpts.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={'Star Wars: Fate of the Old Republic':('15707204','3ab619f77518064621740e58410dcfc0b01c59cad3193f28de234fde84be2e9d'),'Arcanaut Studios':('15754135','eb862a8059ae2a9e6fbe16a77a4fea0831228ca8c601920d6070960385ad47e2')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
data=json.loads(Path(sys.argv[1]).read_text());assert set(data)==set(PINS);rows=[]
for title,v in sorted(data.items()):
 raw=v['raw'];assert (v['revision'],sha(raw))==PINS[title] and v['sha256']==sha(raw)
 lead=re.split(r'(?m)^\s*==[^=]',raw,maxsplit=1)[0];c=mwparserfromhell.parse(lead)
 for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','blockquote','q','poem','gallery'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for link in list(c.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:','category:')):
   try:c.remove(link,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 assert text and not re.search(r'["“”]',text)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':_()')
 rows.append({'title':title+' — introduction','url':url,'source_revision_url':url+'?oldid='+v['revision'],'revision_id':v['revision'],'timestamp':v['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':sha(raw),'lead_wikitext_sha256':sha(lead),'text_sha256':sha(text),'text':text,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked revision history','evidence_class':'secondary','coverage':'Introduction only; marked quoted words and templates omitted. Full articles, publisher material, primary game content, and unmarked third-party rights remain unresolved.','embedded':False,'omitted_inline_quotations':n})
out=''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows);Path('data/wookieepedia-fate-game-leads.jsonl').write_text(out);print('Included',len(rows),'pinned introductions; sha256',sha(out))
