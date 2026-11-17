"""Reconcile two bounded, revision-pinned Wikipedia comic-era tables.

The extracted titles and dates are bibliography metadata, not comic text or a
complete universe inventory. Ambiguous issue zero is reported, not merged.
"""
import hashlib,json,re,requests
from pathlib import Path
import mwparserfromhell
REV=1379066095
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
r=s.get('https://en.wikipedia.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main','revids':REV},timeout=30);r.raise_for_status();v=r.json()['query']['pages'][0]['revisions'][0];raw=v['slots']['main']['content'];digest=hashlib.sha256(raw.encode()).hexdigest()
text=raw[raw.index('===Before the Republic era'):raw.index('===Rise of the Empire era',raw.index('===Before the Republic era'))];chunks=[]
for part in re.split(r'(?m)^\|-\s*$',text):
 cells=[line[1:].strip() for line in part.splitlines() if line.startswith('|') and not line.startswith('|}')]
 if len(cells)>=4 and '#' in cells[0]:chunks.append({'source_title':mwparserfromhell.parse(cells[0]).strip_code().strip(),'source_publication_date':mwparserfromhell.parse(cells[1]).strip_code().strip(),'source_row_sha256':hashlib.sha256(part.encode()).hexdigest()})
series=['Dawn of the Jedi: Force Storm','Dawn of the Jedi: The Prisoner of Bogan','Dawn of the Jedi: Force War','Tales of the Jedi: The Golden Age of the Sith','Tales of the Jedi: The Fall of the Sith Empire','Tales of the Jedi','Tales of the Jedi: The Freedon Nadd Uprising','Tales of the Jedi: Dark Lords of the Sith','Tales of the Jedi: The Sith War','Tales of the Jedi: Redemption','Knights of the Old Republic','Knights of the Old Republic: War','The Old Republic','The Old Republic: The Lost Suns','Lost Tribe of the Sith: Spiral','Knight Errant','Knight Errant: Deluge','Knight Errant: Escape','Jedi vs. Sith']
expected_titles=['Dawn of the Jedi: Force Storm #1–5','Dawn of the Jedi: The Prisoner of Bogan #1–5','Dawn of the Jedi: Force War #1–5','Tales of the Jedi: Golden Age of the Sith #0–5','Tales of the Jedi: The Fall of the Sith Empire #1–5','Tales of the Jedi: Knights of the Old Republic #1–5','Tales of the Jedi: The Freedon Nadd Uprising #1–2','Tales of the Jedi: Dark Lords of the Sith #0–6','Tales of the Jedi: The Sith War #1–6','Tales of the Jedi: Redemption #1–5','Knights of the Old Republic #0–50','Knights of the Old Republic: War #1–5','The Old Republic #1–6','The Old Republic—The Lost Suns #1–5','Lost Tribe of the Sith—Spiral #1–5','Knight Errant: Aflame #0–5','Knight Errant: Deluge #1–5','Knight Errant: Escape #1–5','Jedi vs. Sith #1–6']
assert len(chunks)==len(series)==19 and [r['source_title'] for r in chunks]==expected_titles
issues=json.load(open('catalog/works/comics-issue-inventory.json'))['issues'];rows=[]
for chunk,name in zip(chunks,series):
 relevant=[x for x in issues if x['series']==name];chunk['inventory_series']=name;chunk['matched_issue_work_ids']=[x['work_id'] for x in relevant if isinstance(x.get('issue_number'),int)];chunk['non_numbered_work_ids']=[x['work_id'] for x in relevant if not isinstance(x.get('issue_number'),int)];span=re.search(r'#(\d+)–(\d+)',chunk['source_title']);expected_numbers=set(range(int(span.group(1)),int(span.group(2))+1));actual_numbers={x['issue_number'] for x in relevant if isinstance(x.get('issue_number'),int)};chunk['missing_numbered_issues']=sorted(expected_numbers-actual_numbers);chunk['additional_inventory_numbers']=sorted(actual_numbers-expected_numbers);chunk['qualification']='Title/range reconciliation only; not evidence of original pages, narrative, edition fidelity, accuracy or reuse rights.'
 if name=='Tales of the Jedi: Dark Lords of the Sith':chunk['discrepancy']='Source lists #0-6; inventory has issues 1-6 plus an unnumbered special ashcan. Whether the ashcan is #0 remains unresolved.'
 if name=='Knight Errant: Escape':chunk['discrepancy']='Source lists June-October 2011; the separate Knight Errant article and issue indexes place Escape in 2012. Do not adopt the date without source review.';chunk['contrasting_sources']=['https://en.wikipedia.org/wiki/Star_Wars:_Knight_Errant?oldid=1355697941','https://www.comics.org/series/66292/']
 rows.append(chunk)
out={'description':'Reconciliation of 19 rows from the Before the Republic and Old Republic legends comic tables in one Wikipedia revision. This bounded comparison cannot establish global completeness and does not ingest primary comic content.','source_url':'https://en.wikipedia.org/w/index.php?oldid='+str(REV),'revision':REV,'timestamp':v['timestamp'],'source_wikitext_sha256':digest,'source_section_sha256':hashlib.sha256(text.encode()).hexdigest(),'license':'CC BY-SA 4.0','attribution':'Wikipedia contributors; see linked revision history','rows':rows,'scope_exclusions':'The source tables are selected by their headings and may omit works, anthology stories, variants, flashbacks and newer publications. Numbered matching does not prove issue contents or licensing.'}
Path('evaluation/wikipedia-comic-era-reconciliation.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('Rows',len(rows),'numbered issue references',sum(len(x['matched_issue_work_ids']) for x in rows),'empty runs',sum(not x['matched_issue_work_ids'] for x in rows),'source sha',digest)
