"""Find two pinned pages; writes raw copyrighted markup to local-only scratch."""
import subprocess,xml.etree.ElementTree as ET,json,hashlib,sys
from pathlib import Path
names={"All That's Left",'Quite A Story To Tell'};path=Path(sys.argv[1])
with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
p=subprocess.Popen(['7z','x','-so',str(path)],stdout=subprocess.PIPE);root=None;out={}
for ev,e in ET.iterparse(p.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title')
 if title in names:
  r=e.find('{*}revision');raw=r.findtext('{*}text') or '';out[title]={'revision':r.findtext('{*}id'),'timestamp':r.findtext('{*}timestamp'),'raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
 root.clear()
assert p.wait()==0 and set(out)==names
q=Path(sys.argv[2]);assert not q.exists();q.write_text(json.dumps(out,ensure_ascii=False));q.chmod(0o600)
print('Found',len(out),'pinned pages')
