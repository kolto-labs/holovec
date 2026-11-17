"""Extract a pinned SWTOR wiki page for local review; raw text is private scratch.

Usage: python prepare_swtor_comic_media_page.py ARCHIVE LOCAL_OUTPUT
"""
import hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
archive=sys.argv[1];out=Path(sys.argv[2])
if out.exists():raise FileExistsError(out)
with open(archive,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
p=subprocess.Popen(['7z','x','-so',archive],stdout=subprocess.PIPE);root=None;found=False
for ev,e in ET.iterparse(p.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 if e.findtext('{*}title')=='Star Wars: The Old Republic':
  rev=e.find('{*}revision');raw=rev.findtext('{*}text') or '';d={'title':e.findtext('{*}title'),'revision_id':rev.findtext('{*}id'),'timestamp':rev.findtext('{*}timestamp'),'full_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'raw_wikitext':raw}
  out.write_text(json.dumps(d,ensure_ascii=False));out.chmod(0o600);print('found revision',d['revision_id'],'characters',len(raw),'digest',d['full_wikitext_sha256'],flush=True);found=True;p.kill();p.wait();break
 root.clear()
if not found:raise ValueError('missing')
