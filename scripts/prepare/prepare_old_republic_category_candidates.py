"""Extract exact newer-dump pages for relevant category-census candidates.

Usage: python prepare_old_republic_category_candidates.py ARCHIVE NEW_LOCAL_OUTPUT
Raw markup is local-only review material; category relevance and rights are not proven.
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote,urlsplit
p=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with p.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive changed')
r=json.loads(Path('evaluation/old-republic-category-census.json').read_text());c=[v for v in r['items'] if v['status']=='discovery_only'];excluded=[v for v in c if all(x=='Star Wars: Tales of the Jedi episodes' for x in v['matched_categories'])];selected=[v for v in c if v not in excluded];need={}
for v in selected:
 title=unquote(urlsplit(v['url']).path.split('/wiki/',1)[-1]).replace('_',' ')
 if title in need:raise ValueError('duplicate title')
 need[title]=v
if (len(c),len(excluded),len(need))!=(58,6,52):raise ValueError('census set changed')
proc=subprocess.Popen(['7z','x','-so',str(p)],stdout=subprocess.PIPE);root=None;found={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or ''
 if title in need:
  rev=e.find('{*}revision');raw=rev.findtext('{*}text') or '';found[title]={'source_url':need[title]['url'],'snapshot_doc_id':need[title]['doc_id'],'snapshot_categories':need[title]['matched_categories'],'snapshot_continuity':need[title]['continuity'],'revision_id':rev.findtext('{*}id'),'timestamp':rev.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_wikitext':raw}
 root.clear()
if proc.wait()!=0:raise RuntimeError('dump scan failed')
out.write_text(json.dumps({'archive_sha256':expected,'candidate_count':len(need),'excluded_animated_titles':[x['title'] for x in excluded],'records':found,'missing':sorted(set(need)-set(found))},ensure_ascii=False));out.chmod(0o600);print('reviewed scope',len(need),'exact pages',len(found),'missing',len(need)-len(found),'animated excluded',len(excluded))
