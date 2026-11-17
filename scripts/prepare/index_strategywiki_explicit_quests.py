"""Index only explicit quest-list entries in two pinned StrategyWiki pages.

The MediaWiki query API provides the original revision content:
https://www.mediawiki.org/wiki/API:Revisions
Labels and links are contributor-maintained discovery metadata, not a complete
mission census or a right to reproduce game dialogue.
"""
import hashlib,json,re,requests
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
p=Path('evaluation/strategywiki-guide-heading-index.json');idx=json.loads(p.read_text());lookup={v['title']:v for v in idx['pages']};source='Star Wars: Knights of the Old Republic/Taris';dantooine='Star Wars Knights of the Old Republic II: The Sith Lords/Dantooine';a=lookup[source];d=lookup[dantooine];assert (a['revision_id'],d['revision_id'])==('1121170','1095347')
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';res=s.get('https://strategywiki.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions','rvprop':'ids|content','rvslots':'main','revids':'1121170'},timeout=30);res.raise_for_status();raw=res.json()['query']['pages'][0]['revisions'][0]['slots']['main']['content'];assert hashlib.sha256(raw.encode()).hexdigest()==a['raw_wikitext_sha256'];match=re.search(r'(?m)^==\s*Quests\s*==\s*$',raw);assert match;end=re.search(r'(?m)^==[^=]',raw[match.end():]);body=raw[match.end():match.end()+end.start() if end else len(raw)];area=None;rows=[]
for line in body.splitlines():
 if line.startswith(';'):area=line[1:].strip()
 if not line.startswith('*'):continue
 c=mwparserfromhell.parse(line[1:].strip());dest=[]
 for t in list(c.filter_templates(recursive=False)):
  if str(t.name).strip()!='s':raise ValueError('Unexpected list template')
  page=str(t.get(1).value).strip();anchor=str(t.get(2).value).strip() if t.has(2) else None;dest.append((page,anchor));c.replace(t,anchor or page)
 for l in list(c.filter_wikilinks(recursive=True)):
  target=str(l.title).strip();page,_,anchor=target.partition('#');page=page.removeprefix('../').strip('/').replace('_',' ');shown=str(l.text).strip() if l.text is not None else page;dest.append((page,anchor.replace('_',' ') or None));c.replace(l,shown)
 assert len(dest)==1 and area
 label=c.strip_code(normalize=True,collapse=True).strip();page,anchor=dest[0];target=lookup['Star Wars: Knights of the Old Republic/'+page];source_revision_url=a['url']+'?oldid='+a['revision_id'];target_url=target['url']+'?oldid='+target['revision_id'];target_heading_match=any(h['label']==anchor for h in target['headings']) if anchor else None
 if anchor:target_url+='#'+quote(anchor.replace(' ','_'),safe='')
 rows.append({'game':'KOTOR I','kind':'guide quest-list entry','label':label,'area':area,'source_page':source,'source_revision_id':a['revision_id'],'source_revision_url':source_revision_url,'target_page':target['title'],'target_revision_id':target['revision_id'],'target_revision_url':target_url,'target_heading':anchor,'target_heading_exact_match':target_heading_match,'disposition':'secondary navigation only; quest identity, scope and branch coverage require review'})
assert len(rows)==12
bonus=[h for h in d['headings'] if re.search(r'(?i):\s*Bonus Mission$',h['label'])];assert len(bonus)==3
for h in bonus:
 rows.append({'game':'KOTOR II','kind':'guide bonus-mission heading','label':h['label'],'area':'Dantooine','source_page':dantooine,'source_revision_id':d['revision_id'],'source_revision_url':d['url']+'?oldid='+d['revision_id']+'#'+quote(h['label'].replace(' ','_'),safe=''),'target_page':dantooine,'target_revision_id':d['revision_id'],'target_heading':h['label'],'target_heading_exact_match':True,'disposition':'secondary navigation only; actual mission content and branches require review'})
out={'description':'Fifteen contributor-maintained guide labels: twelve Taris quest-list entries and three explicit Dantooine bonus-mission headings. This is not a complete quest census and does not establish source accuracy, original game content, rights or all branches. Page bodies are not copied.','source_heading_index':'evaluation/strategywiki-guide-heading-index.json','source_heading_index_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'license':'StrategyWiki contributor text CC BY-SA 4.0; older contributions may be CC BY-SA 3.0','attribution':'StrategyWiki contributors; see linked page histories','entries':rows}
Path('evaluation/strategywiki-explicit-quest-index.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('Indexed',len(rows),'explicit guide labels;',sum(r.get('target_heading_exact_match') is False for r in rows),'unmatched target headings')
