"""Extract wiki markup for 46 issue pages whose plot scans yielded no text.

Usage: python prepare_comic_uncovered_issue_pages.py ARCHIVE NEW_LOCAL_OUTPUT
Output contains source markup and is private local review material.
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive changed')
r=json.loads(Path('evaluation/missing-comic-issue-plot-scan.json').read_text());targets={v['title']:v for v in r['items']}
if len(targets)!=46:raise ValueError('target scope changed')
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or ''
 if title in targets:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';p=targets[title]
  if p['revision_id'] is not None and v.findtext('{*}id')!=p['revision_id']:raise ValueError('revision changed: '+title)
  found[title]={'work_id':p['work_id'],'url':p['url'],'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_wikitext':raw}
 root.clear()
if proc.wait()!=0 or set(found)!=set(targets):raise ValueError('incomplete archive scan')
out.write_text(json.dumps({'archive_sha256':expected,'records':found},ensure_ascii=False));out.chmod(0o600);print('Found',len(found),'pinned pages for local-only review')
