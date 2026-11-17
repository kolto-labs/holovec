"""Acquire contributor prose for a pinned StrategyWiki restored-content overview.

Requires requests and mwparserfromhell. Templates, reference/image markup,
external-links section and quotation-marked text are excluded; this does not
clear unmarked third-party excerpts or include mod or game assets.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
REV=1189005;TITLE='Star Wars Knights of the Old Republic II: The Sith Lords/Restored Content Mod';API='https://strategywiki.org/w/api.php'
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';r=s.get(API,params={'action':'query','format':'json','formatversion':2,'prop':'revisions|info','rvprop':'ids|timestamp|content','rvslots':'main','inprop':'url','revids':REV},timeout=30);r.raise_for_status();page=r.json()['query']['pages'][0];v=page['revisions'][0];raw=v['slots']['main']['content']
if page['title']!=TITLE or page['pageid']!=354953 or v['revid']!=REV or hashlib.sha256(raw.encode()).hexdigest()!='8c84c0cae0a1cbdac5f3d7ddb22d6918977aa987f86b949ba9fd4aa684277268':raise ValueError('source changed')
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
# Limit to contributor prose before the external-links section.
part=re.split(r'(?m)^\s*==\s*External links\s*==\s*$',raw,maxsplit=1,flags=re.I)[0];c=mwparserfromhell.parse(part)
for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
for t in list(c.filter_tags(recursive=True)):
 if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
  try:c.remove(t,recursive=True)
  except ValueError:pass
for t in list(c.filter_wikilinks(recursive=True)):
 if str(t.title).strip().casefold().startswith(('file:','image:')):
  try:c.remove(t,recursive=True)
  except ValueError:pass
text=c.strip_code(normalize=True,collapse=True).strip()
if not text or sha(text)!='06ec3bf193fa0072a6a4b0944d0d55447d16c7ac627d33a58ab427aa812334be' or re.search(r'["“”]',text) or len(text)>1500:raise ValueError('unexpected content: review required')
row={'title':TITLE,'url':page['fullurl'],'source_revision_url':'https://strategywiki.org/w/index.php?title=Star_Wars_Knights_of_the_Old_Republic_II:_The_Sith_Lords/Restored_Content_Mod&oldid='+str(REV),'page_id':page['pageid'],'revision_id':REV,'timestamp':v['timestamp'],'page_wikitext_sha256':sha(raw),'text_sha256':sha(text),'text':text,'license':'CC BY-SA 4.0; contributions prior to 1 October 2024 may be CC BY-SA 3.0; third-party material may have separate terms','attribution':'StrategyWiki contributors; see linked article revision history','continuity':'technical community source','evidence_class':'secondary','extraction':'Prose before external links; templates, references, images and quote blocks omitted. No game or mod assets.','coverage':'Brief mod overview only; does not enumerate restored content, compatibility, changes, game branches or primary assets.','embedded':False}
Path('data/strategywiki-restored-content-overview.jsonl').write_text(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print('acquired one pinned overview; text hash',sha(text),'source hash',sha(raw))
