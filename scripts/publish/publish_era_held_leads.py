"""Publish three pinned secondary introductions reviewed from held era candidates.

Input is the locally extracted, private wiki-dump JSON. The user has held all
inference; this script only performs deterministic text and rights screening.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={
 'Cult of Darth Phobos':('14659841','a621a352346b814c965b98c30e78820e3e179b4aa8d249f4a33999ca20751d9a','90bc54e071435a2b30918fce0162aa99dd3dbe79d8a6fbfcaacac954eff9d598'),
 'Johun Othone':('15802212','681096e493801342e199c173ceb61ede9fe5caa4201913e5e2cc5a22fee4a809','6c904fb528970a5db6e0266a7d3be7352fde6cf60eb998bce35e9b5f23340baa'),
 'Lignan':('15023078','e3da383f627ed0f537514ecf8abfb35a947748a621bf538a114a391d9d4e3854','52ad14833cce28e0034231a0b272c9f2bb0d53e22cb9857bebf40554c917159d')}
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
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows);Path('data/wookieepedia-era-held-leads.jsonl').write_text(out);print('Published',len(rows),'pinned introductions')
