"""Extract nine current, revision-pinned StrategyWiki guide alternatives.

This limited marker screen cannot establish rights for unmarked game-derived
material. Templates are stripped, so output is not a complete rendered page.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
PINS={'59487': ('1159889', 'c92e8a36feecbd610d0b68e3e1ead1c1b87724e7b2d569b8808154c93ed3bb9b', 'KOTOR II'), '176143': ('1141200', 'b6813e89e2e5fc3f89d360943b28a7940712ef90c8d722a84fe87e2a6d50c4ae', 'KOTOR II'), '258418': ('1141182', '08cc7a47566ac13c428607106837bffedb641a610713449cb4fca11d483bd4e1', 'KOTOR II'), '176014': ('1171623', '2181b39ea2b62f7622271a70d4559fb93e7318df3de568bce6c313ccbe8e04e0', 'KOTOR II'), '62230': ('1195192', 'adf6fc8d991c310e4cbbcf022dad4aed39617d4a8d19a147d54c6bfb2d49f9a1', 'KOTOR I'), '62228': ('1171457', '6b5c8b07a43a10f19a2bc71086febba095de19dab98ccfcef5b8746335fd1349', 'KOTOR I'), '159481': ('1151332', '143693627e75f41d809b33a22489668b1452d3e019142dc7b0c992599cdb2546', 'KOTOR I'), '159349': ('1171622', '6db86392fce1be8f398153b28a595c1a13ee84fde30f74852e368591d3af26fe', 'KOTOR I'), '175633': ('1195193', 'b06b73bae5b088551cc93311c5509bfff3d8c4d02cc3895cabce32cfef3479ae', 'KOTOR I')}
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
if sha(output)!='2c9ddc54e10d973c582b499a2a25b5f12be33f5b1476165d56821017a50c333d':raise ValueError('Output changed; re-screen before release')
Path('data/strategywiki-current-guide-revisions.jsonl').write_text(output);print('prepared',len(rows),'revision-pinned guide pages',[(x['page_id'],x['text_sha256']) for x in rows])
