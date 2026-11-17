"""Prepare two quote-screened wiki contexts for a SWTOR short-story lead."""
import json,re,hashlib,mwparserfromhell
from pathlib import Path
PINS={'Lana Beniko':('15802812','8cb432ab1b3c6efed1baf59ba03c3f55e6d01de89469531936da8811c683ca95'),'Invasion of Talay':('13924927','267f40bd386c7689e03efbc0c438bfdb8082b4f63755a952cd945850b333de82')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def sh(s):
 w=re.findall(r'\w+',str(s).casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
bundle=json.load(open('/tmp/holovec-lana-talay-raw.json'));rows=[]
for title,(rev,digest) in PINS.items():
 v=bundle[title];raw=v['raw_wikitext'];assert v['revision_id']==rev and sha(raw)==digest
 code=mwparserfromhell.parse(raw);bad=[]
 for t in code.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|speech|crawl|lyrics|poem',str(t.name)):bad.extend(str(x.value.strip_code()) for x in t.params)
 for tag in code.filter_tags(recursive=True):
  if str(tag.tag).casefold() in ('blockquote','q','poem'):bad.append(str(tag.contents.strip_code()))
 ban=set().union(*(sh(x) for x in bad)) if bad else set();heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw))
 if title=='Lana Beniko':
  i=next(i for i,h in enumerate(heads) if h.group(2).strip()=='Advisor to Darth Arkous');body=raw[heads[i].end():heads[i+1].start()];section='Advisor to Darth Arkous'
 else:body=raw[:heads[0].start()];section='introduction'
 assert "Lana Beniko's Journal" in raw
 c=mwparserfromhell.parse(body)
 for t in list(c.filter_templates(recursive=False)):
  try:c.remove(t,recursive=True)
  except ValueError:pass
 for tag in list(c.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:c.remove(tag,recursive=True)
   except ValueError:pass
 for link in list(c.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:','category:')):
   try:c.remove(link,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 if not text or re.search(r'["“”]',text) or sh(text)&ban:raise ValueError('quote screen held '+title)
 url='https://starwars.fandom.com/wiki/'+title.replace(' ','_')
 rows.append({'title':title+' — '+section,'subject':title,'section':section,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':v['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':digest,'section_wikitext_sha256':sha(body),'text':text,'text_sha256':sha(text),'omitted_inline_quotations':n,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','coverage':'Partial context related to Lana Beniko\'s Journal: Darth Arkous, not the original story or evidence of complete story coverage; unmarked third-party excerpt rights are unverified.','embedded':False})
Path('data/wookieepedia-lana-talay-context.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows));print('Included',len(rows),'sections')
