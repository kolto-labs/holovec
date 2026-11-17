"""Find unresolved comic-linked titles in the pinned wiki dump for local review.

Usage: python prepare_missing_comic_link_targets.py ARCHIVE LOCAL_OUTPUT
No page text in this scratch output is approved for publication.
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote,urlsplit
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive hash mismatch')
report=json.loads(Path('evaluation/comic-linked-wiki-coverage.json').read_text());targets={}
for r in report['snapshot_url_missing']:
 title=unquote(urlsplit(r['target_url']).path.split('/wiki/',1)[-1]).replace('_',' ');k=title.casefold()
 if k in targets:raise ValueError('duplicate title')
 targets[k]={'target':r['target'],'target_url':r['target_url'],'issue_ids':r['issue_ids']}
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;candidates={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or '';k=title.casefold()
 if k in targets:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';candidates.setdefault(k,[]).append({'title':title,'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_wikitext':raw,**targets[k]})
 root.clear()
if proc.wait()!=0:raise RuntimeError('decompression failed')
found={}; ambiguous=[]
for k,items in candidates.items():
 expected_title=unquote(urlsplit(targets[k]['target_url']).path.split('/wiki/',1)[-1]).replace('_',' ')
 exact=[v for v in items if v['title']==expected_title]
 if len(exact)==1:found[k]=exact[0]
 elif not exact and len(items)==1:found[k]=items[0]
 else:ambiguous.append({'target':targets[k]['target'],'candidate_titles':[v['title'] for v in items]})
if ambiguous:raise ValueError(f'ambiguous case-folded matches: {ambiguous}')
result={'source_archive_sha256':expected,'targets':len(targets),'records':found,'not_found':[targets[k] for k in sorted(set(targets)-set(found))]};out.write_text(json.dumps(result,ensure_ascii=False));out.chmod(0o600);print('targets',len(targets),'matched',len(found),'not found',len(result['not_found']))
