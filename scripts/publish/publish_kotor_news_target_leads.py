"""Publish five pinned secondary introductions reviewed from held era candidates.

Input is the locally extracted, private wiki-dump JSON. The user has held all
inference; this script only performs deterministic text and rights screening.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={
'Taris Home Guard':('13694257','d0c745f1a555b213e6d76cfd6a24ba1a4ab439c0c631a10accba00cb9f0cd318','bbf6100115b58a36b1f07e7c50006368f4f47dcbec52cb6bedf2ed5919f2cabb'),
'Tremendous group':('14172691','23190026f323a30b52a78aa380c5f03e57dc64c1b83862bc39eb7616b0d4b650','7098b59860605692512640a86e4c3152105456d5636e0cf9894ede94ca9dfb2d'),
'Highpoint':('14395067','c3a97479453365d1ea2764042c5b1e697b5ebe3f1dae6e1dcc09d61eb181e93f','e4aa46f6f5c02a824b037975938ca7987b69be28ee327689b3a27b44025dbd74'),
'Senatorial Suite':('14422837','237d671c7a0f835ecff79502711c7676260d241ee908e9ba39eb1b4eb61a0a32','838b6392bfb3f27047215c58874f063427d7d74356c27c7b3b30abcf07a0a36c'),
'Joint Operations Information Office':('15538141','51da8ee69ec6dffcc78e11534ebe51b3c5f2e85b2ec452eba15b6b676a039206','6b32b478164c934c20f1d4bcd1f679dce63f9ef65d7c7e81871f4a4f3490d055')}
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
source=json.loads(Path(sys.argv[1]).read_text());reconciliation={r['target']:r for r in json.loads(Path('evaluation/kotor-news-target-reconciliation.json').read_text())['items']};rows=[]
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
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe='/');rows.append({'title':title+' — lead','url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':record['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':rawhash,'lead_wikitext_sha256':sha(lead),'text_sha256':texthash,'text':text,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','appearance_insert_ids':reconciliation[title]['insert_ids'],'continuity':'legends','omitted_inline_quotations':omitted,'coverage':'Wiki introduction for a subject linked by a news-insert appearance index; the index does not prove complete or accurate insert coverage. Unmarked excerpts and third-party rights remain unverified.','embedded':False})
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows);Path('data/wookieepedia-kotor-news-target-leads.jsonl').write_text(out);print('Published',len(rows),'pinned introductions')
