"""Publish screened Legends leads; only Swine has a verified direct redirect."""
import hashlib,json,re,sys,mwparserfromhell
from pathlib import Path
from urllib.parse import quote
PINS={'Rabbit/Legends':('15788914','7e0443ae8d44b90b07edda5f759ed67366c81b4bd2d753e7527dabe4fa53bf67','5f28c461e3216ebcd7e578d97f918cb66ab290acb5fd6786998bbc3aa6667a79','bb6d46e578b17b9551966bc57f04b265a06f414e6750bb550dd475f902f937cc'),'Pig/Legends':('15787092','01169cac85950474a67f8666ff8ea389d115db754668e30afe15443f6b246943','aad8e1af8dacb46faa9f6deb5be90de7a75dbc8281abc37b8b794471d2423ebe','b74014c675f4c209743c8a3112a80b8bc50720f3e64df071d33e7767b6be8822')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());assert set(x)==set(PINS);rows=[]
for title,v in sorted(x.items()):
 raw=v['raw_wikitext'];assert (v['revision_id'],sha(raw))==PINS[title][:2] and v['sha256']==sha(raw);code=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:heads[0].start()] if heads else raw;q=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):q.extend(p.value.strip_code() for p in t.params)
 for t in code.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):q.append(t.contents.strip_code())
 for i,h in enumerate(heads):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((z.start() for z in heads[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));q.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
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
 text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 assert not re.search(r'["“”]',text) and (sha(lead),sha(text))==PINS[title][2:] and not any(sh(text)&sh(z) for z in q)
 u='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()');rows.append({'title':title+' — lead','url':u,'source_revision_url':u+'?oldid='+v['revision_id'],'revision_id':v['revision_id'],'timestamp':v['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':sha(raw),'lead_wikitext_sha256':sha(lead),'text_sha256':sha(text),'text':text,'omitted_inline_quotations':n,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','association':'Swine redirects to Pig/Legends in the pinned dump; appearance list is secondary.' if title=='Pig/Legends' else 'Possible Legends counterpart of Rabbit; the generic link is not established as the same subject.','appearance_issue_ids':['lost-tribe-spiral-002'] if title=='Pig/Legends' else [],'coverage':'Wiki introduction only; can describe other eras. No primary comic material; unmarked excerpts and third-party rights remain unverified.','embedded':False})
out=''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows);assert sha(out)=='6659af786172bcc86caa8ffb8b56fa060ab5f49fcebd421733e7fd21024da819';Path('data/wookieepedia-comic-legends-counterpart-leads.jsonl').write_text(out);print('Included',len(rows),'leads, sha256',sha(out))
