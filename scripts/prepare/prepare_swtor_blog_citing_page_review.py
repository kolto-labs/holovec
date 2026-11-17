"""Extract exact uncatalogued citing-page markup to private local scratch for review.

Usage: python prepare_swtor_blog_citing_page_review.py ARCHIVE NEW_LOCAL_OUTPUT
No extracted page text is approved for publication by this scan.
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive changed')
r=json.loads(Path('evaluation/swtor-narrative-blog-citations.json').read_text());targets={}
for lead in r['items']:
 for p in lead['wiki_pages']:
  if p['corpus_matches']:continue
  x=targets.setdefault(p['title'],{'revision_id':p['revision_id'],'raw_wikitext_sha256':p['source_wikitext_sha256'],'publisher_urls':[]})
  if (x['revision_id'],x['raw_wikitext_sha256'])!=(p['revision_id'],p['source_wikitext_sha256']):raise ValueError('inconsistent revision')
  if lead['publisher_url'] not in x['publisher_urls']:x['publisher_urls'].append(lead['publisher_url'])
if len(targets)!=47:raise ValueError('review scope changed')
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or ''
 if title in targets:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';x=targets[title]
  if (v.findtext('{*}id'),hashlib.sha256(raw.encode()).hexdigest())!=(x['revision_id'],x['raw_wikitext_sha256']):raise ValueError('page changed '+title)
  found[title]={**x,'timestamp':v.findtext('{*}timestamp'),'raw_wikitext':raw}
 root.clear()
if proc.wait()!=0 or set(found)!=set(targets):raise ValueError('incomplete archive scan')
out.write_text(json.dumps({'archive_sha256':expected,'records':found},ensure_ascii=False));out.chmod(0o600);print('Found',len(found),'pinned pages for local-only review')
