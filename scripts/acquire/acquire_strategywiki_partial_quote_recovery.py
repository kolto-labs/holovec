"""Extract partially recovered StrategyWiki walkthrough alternatives.

This limited marker screen cannot establish rights for unmarked game-derived
material. Templates are stripped, so output is not a complete rendered page.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
PINS={'237252': ('1192379', 'f1bddfd90658f12a024fb201acc7949755d16dbe91259456f9561841ed524ab5', 'KOTOR II'), '237158': ('1146436', 'e92be757a904c04ff6e0cfc049ba632114cda791f79d9f19d397bd5e9c2ddb73', 'KOTOR II'), '291411': ('1146581', '034c7c273d9d13b60d82dc5f30b14b5ecb1c53c260bea74a26667c0aa26bea44', 'KOTOR II'), '211950': ('1146568', 'e58a958e3d7b3109f38af5d9aee9056fe42572ab7004b342b1d66448750f46cc', 'KOTOR II'), '298066': ('1137889', '7581759cda4f50bd7cb6640caeb922021e017ef1611277717e4ad2e0abfecdd7', 'KOTOR II'), '298373': ('1167854', '2d7cb2c2b6e89ea95497cd49bbe0dfd023edd09c40ce8783021419769e016e60', 'KOTOR II'), '235154': ('1174110', '127bc11ae0456170d60017b404a3707de3f984dfb6f1500ab9630066753c2179', 'KOTOR II'), '331338': ('1156211', 'ea2efb02fb614b4b51f1fa42435b2edbb9ddc46bd2c665d924e0a6ee2e0384de', 'KOTOR II'), '186463': ('1143104', '87fa4ff3405b240b6ce63b49d825c1d3d8ddd26ebb7c544e485e9325c43fbfe7', 'KOTOR I'), '213524': ('1180306', '894363c304cedc057a162e840acf3a26daf17296bff701f86c52f3164236f36f', 'KOTOR I')}
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';r=s.get('https://strategywiki.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions|info','rvprop':'ids|timestamp|content','rvslots':'main','inprop':'url','revids':'|'.join(x[0] for x in PINS.values())},timeout=40);r.raise_for_status();pages=r.json()['query']['pages'];old={str(x['page_id']):x for x in map(json.loads,open('data/strategywiki.jsonl'))};rows=[];held=[]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
for page in pages:
 pid=str(page['pageid']);rev,rawhash,game=PINS[pid];v=page['revisions'][0];raw=v['slots']['main']['content'];c=mwparserfromhell.parse(raw)
 if str(v['revid'])!=rev or sha(raw)!=rawhash:raise ValueError('source mismatch')
 quote_names=re.compile(r'quote|dialog|crawl|game.?text',re.I)
 risky=[t for t in c.filter_templates(recursive=True) if quote_names.search(str(t.name))]
 quote_text=[]
 for t in risky:
  for parameter in t.params:quote_text.append(str(parameter.value.strip_code(normalize=True,collapse=True)))
 def shingles(value):
  words=re.findall(r'\w+',value.casefold());return {tuple(words[i:i+8]) for i in range(max(0,len(words)-7))}
 qset=set().union(*(shingles(q) for q in quote_text)) if quote_text else set()
 for t in list(c.filter_templates(recursive=False)):
  if quote_names.search(str(t.name)):c.remove(t,recursive=True)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for t in list(c.filter_wikilinks(recursive=True)):
  if str(t.title).strip().casefold().startswith(('file:','image:')):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 clean=c.strip_code(normalize=True,collapse=True).strip()
 text,omitted=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',clean)
 lines=text.splitlines(keepends=True);omitted_lines=0;preserved=[]
 for line in lines:
  if shingles(line)&qset:
   preserved.append('[passage omitted due to quote overlap]\n');omitted_lines+=1
  else:preserved.append(line)
 text=''.join(preserved).strip()
 reason='empty' if not text else 'unresolved quotation marks' if re.search(r'["“”]',text) else 'eight-word overlap remains after line omission' if shingles(text)&qset else 'no isolatable overlapping line' if not omitted_lines else None
 if reason:
  held.append({'page_id':int(pid),'title':page['title'],'revision_id':rev,'page_wikitext_sha256':rawhash,'reason':reason});continue
 prior=old[pid];row={'title':page['title'],'url':page['fullurl'],'source_revision_url':'https://strategywiki.org/w/index.php?oldid='+rev,'page_id':page['pageid'],'revision_id':rev,'timestamp':v['timestamp'],'page_wikitext_sha256':rawhash,'text_sha256':sha(text),'text':text,'compares_to_snapshot_revision':prior['revision'],'compares_to_snapshot_text_sha256':prior['sha256'],'license':'CC BY-SA 4.0; contributions prior to 1 October 2024 may be CC BY-SA 3.0; third-party material may have separate terms','attribution':'StrategyWiki contributors; see linked article revision history','game':game,'continuity':'game guide','evidence_class':'secondary_walkthrough','extraction':'References, galleries, images, marked quote/dialogue/crawl/game-text templates and quotation-marked phrases removed; lines overlapping removed template text replaced by [passage omitted due to quote overlap]. Template code stripped without rendering. Remaining text checked against removed template parameters at eight words.', 'omitted_inline_quotations':omitted,'risky_templates_detected':len(risky),'omitted_overlap_lines':omitted_lines,'coverage':'Partial guide text; templates, game excerpts, rendered tables, choices and complete game content are not established. The earlier source snapshot remains separately available.','embedded':False};rows.append(row)
rows.sort(key=lambda x:x['page_id'])
if {str(x['page_id']) for x in rows}|{str(x['page_id']) for x in held}!=set(PINS):raise ValueError('Missing pages')
output=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
if sha(output)!='8b5e6da404f56fdd790c2ce152f3cbab098460db8e27fee3fbb8fe3715070cf2':raise ValueError('Output changed; re-screen before release')
Path('data/strategywiki-partial-quote-overlap-recovery.jsonl').write_text(output);print('prepared',len(rows),'partially recovered walkthroughs',[(x['page_id'],x['text_sha256']) for x in rows])

Path('evaluation/strategywiki-partial-quote-recovery-holds.json').write_text(json.dumps({'description':'Sections held by limited markup and quotation-overlap screen; no source text retained. Not rights clearance.','included':len(rows),'held':held},indent=2,ensure_ascii=False)+'\n')
print('held',len(held),[(h['page_id'],h['reason']) for h in held])
