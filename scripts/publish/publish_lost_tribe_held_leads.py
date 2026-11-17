"""Publish six pinned secondary introductions reviewed from held era candidates.

Input is the locally extracted, private wiki-dump JSON. The user has held all
inference; this script only performs deterministic text and rights screening.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={
'Fohargh':('15307308','0d1739e4db779c388742f6d59b58e79dab367125ad7a37567277b1f46ab0508f','fd8a5594264766fe551c79ce0a5bec24116acc37328e0c42ab6a2873656c4da0'),
'Thallis Khai':('15455989','47e29e8057e5a3f789c839c589c6b44295a03f7524c8af46db8b81f19fed9729','f00733d2ad3043cac760af9ca84cc23c1698bfe87e502216e39059ed44a283a0'),
'Orielle Kitai':('15785070','7b99a22fe70b97850bcb1b0748df56bcd46e204f70135b81c72e4adbaccb15e0','0f049430a22258babb9d6397536189a1c832cefb2949a0e6baa80475fba22617'),
'Force 57':('14490662','bcd77fb0e7c0ccd37bf43506c981ef2cddfa0677bc28d5a1509f7bcf8bedb802','f88982368084c282a858dc525f076105f49e659efa461f5e488cb3cbd5a1895d'),
'Slippery Hilts':('15792307','1efc4e3082e472a1d323df0309b4555ff737d7c6ccf74a93c3ae93e029e3a8f2','08d8be26b96b8a5714301674b412c0ac8113d856e3cdf19f29950be4a9ed8ff8'),
'Beray faction':('13883901','230b7af09c25d5fd37c04754409d9406e8f3ae225a0928e8c5b1c630e0c27b54','fda92b798b422401ab8e638a47e2d0cbb799d720b3fa7f78253c1c58d35330a7')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 words=re.findall(r'\w+',s.casefold());return {tuple(words[i:i+8]) for i in range(max(0,len(words)-7))}
def clean(raw):
 c=mwparserfromhell.parse(raw)
 for t in list(c.filter_templates(recursive=False)):c.remove(t)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for l in list(c.filter_wikilinks(recursive=True)):
  if str(l.title).strip().casefold().startswith(('file:','image:','category:')):
   try:c.remove(l,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip();return re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
source=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(revision,rawhash,texthash) in PINS.items():
 record=source[title];raw=record['raw_wikitext'];assert sha(raw)==rawhash and record['revision_id']==revision
 parsed=mwparserfromhell.parse(raw);tops=[t for t in parsed.filter_templates(recursive=False) if str(t.name).strip().casefold()=='top'];assert any('leg' in [str(p.value).strip().casefold() for p in t.params] for t in tops)
 headings=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:headings[0].start()] if headings else raw;text,omitted=clean(lead);assert sha(text)==texthash and not re.search(r'["“”]',text)
 risky=[]
 for t in parsed.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):risky.extend(p.value.strip_code() for p in t.params)
 for t in parsed.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):risky.append(t.contents.strip_code())
 for i,h in enumerate(headings):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((z.start() for z in headings[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));risky.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
 assert not any(shingles(text)&shingles(q) for q in risky),title
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe='/');rows.append({'title':title+' — lead','url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':record['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':rawhash,'lead_wikitext_sha256':sha(lead),'text_sha256':texthash,'text':text,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','continuity':'legends','omitted_inline_quotations':omitted,'coverage':'Wiki introduction only; includes adjacent-era or cross-era context. Unmarked excerpts and third-party rights remain unverified.','embedded':False})
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows);Path('data/wookieepedia-lost-tribe-held-leads.jsonl').write_text(out);print('Published',len(rows),'pinned introductions')
