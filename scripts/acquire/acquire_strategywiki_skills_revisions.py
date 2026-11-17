"""Extract two current, revision-pinned StrategyWiki skill-guide alternatives.

This limited marker screen cannot establish rights for unmarked game-derived
material. Templates are stripped, so output is not a complete rendered page.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
PINS={'62234':('1137765','c51a52c6fe6bcc1f8410a0be1a11d31df1acbc8f41e392cc8837c1e1a388a45c','KOTOR I'),'175947':('1167405','b32eff53c929f10f6cf55f0c89d17b59e9cba6ccd20c92c95c68098669181d1e','KOTOR II')}
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';r=s.get('https://strategywiki.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions|info','rvprop':'ids|timestamp|content','rvslots':'main','inprop':'url','revids':'|'.join(x[0] for x in PINS.values())},timeout=40);r.raise_for_status();pages=r.json()['query']['pages'];old={str(x['page_id']):x for x in map(json.loads,open('data/strategywiki.jsonl'))};rows=[]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
for page in pages:
 pid=str(page['pageid']);rev,rawhash,game=PINS[pid];v=page['revisions'][0];raw=v['slots']['main']['content'];c=mwparserfromhell.parse(raw)
 if str(v['revid'])!=rev or sha(raw)!=rawhash:raise ValueError('source mismatch')
 if re.search(r'["“”]',raw) or any(re.search(r'quote|dialog|crawl|game.?text',str(t.name),re.I) for t in c.filter_templates(recursive=True)):raise ValueError('marked third-party text')
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for t in list(c.filter_wikilinks(recursive=True)):
  if str(t.title).strip().casefold().startswith(('file:','image:')):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip()
 if not text or re.search(r'["“”]',text):raise ValueError('unexpected text')
 prior=old[pid];row={'title':page['title'],'url':page['fullurl'],'source_revision_url':'https://strategywiki.org/w/index.php?oldid='+rev,'page_id':page['pageid'],'revision_id':rev,'timestamp':v['timestamp'],'page_wikitext_sha256':rawhash,'text_sha256':sha(text),'text':text,'compares_to_snapshot_revision':prior['revision'],'compares_to_snapshot_text_sha256':prior['sha256'],'license':'CC BY-SA 4.0; contributions prior to 1 October 2024 may be CC BY-SA 3.0; third-party material may have separate terms','attribution':'StrategyWiki contributors; see linked article revision history','game':game,'continuity':'game guide','evidence_class':'secondary_walkthrough','extraction':'Reference, gallery, quote and image markup removed; template code stripped without rendering. No quote marks or quote/dialogue/crawl/game-text template names detected in raw source.','coverage':'Partial guide text; templates, game excerpts, rendered tables, choices and complete game content are not established. The earlier source snapshot remains separately available.','embedded':False};rows.append(row)
rows.sort(key=lambda x:x['page_id'])
if {str(x['page_id']) for x in rows}!=set(PINS):raise ValueError('Missing pages')
output=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
if sha(output)!='714af9617a31750f0a458a94bab898eef254e79bda68c464cc49e7a6141d2407':raise ValueError('Output changed; re-screen before release')
Path('data/strategywiki-current-skills.jsonl').write_text(output);print('prepared',len(rows),'revision-pinned skill pages',[(x['page_id'],x['text_sha256']) for x in rows])
