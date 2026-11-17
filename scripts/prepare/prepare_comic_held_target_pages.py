"""Find exact titles of comic-linked review targets in a pinned wiki dump.

Usage: python prepare_comic_held_target_pages.py ARCHIVE NEW_LOCAL_OUTPUT
Output contains source markup and must stay in local private scratch.
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote,urlsplit
import pyarrow.parquet as pq
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive changed')
r=json.loads(Path('evaluation/comic-linked-wiki-coverage.json').read_text());targets={unquote(v['target_url']).casefold():v for v in r['review_candidates'] if v['status']=='requires_relevance_or_rights_review'};seen=set()
for p in Path('data').iterdir():
 if p.name in ('wookieepedia-comic-held-target-leads.jsonl','wookieepedia-comic-held-long-leads.jsonl'):continue
 if p.suffix=='.jsonl':
  with p.open() as f:docs=[json.loads(x) for x in f if x.strip()]
 elif p.suffix=='.parquet':docs=pq.read_table(p).to_pylist()
 else:continue
 for d in docs:
  u=unquote(d.get('url') or d.get('source_url') or '').casefold()
  if u in targets:seen.add(u)
need={}
for key,v in targets.items():
 if key in seen:continue
 title=unquote(urlsplit(v['target_url']).path.split('/wiki/',1)[-1]).replace('_',' ')
 if title in need:raise ValueError('duplicate title')
 need[title]=v
if len(targets)!=156 or len(need)!=152:raise ValueError('target set changed; reconcile before scanning')
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or ''
 if title in need:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';found[title]={'target_url':need[title]['target_url'],'issue_ids':need[title]['issue_ids'],'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_wikitext':raw}
 root.clear()
if proc.wait()!=0:raise RuntimeError('archive extraction failed')
out.write_text(json.dumps({'archive_sha256':expected,'targets':len(need),'records':found,'missing':sorted(set(need)-set(found))},ensure_ascii=False));out.chmod(0o600);print('targets',len(need),'exact pages',len(found),'missing',len(need)-len(found),'already represented',len(seen))
