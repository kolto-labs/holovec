"""Find four Legends counterparts in a pinned dump; output is local-only markup."""
import json,hashlib,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
names={'Flier/Legends','Rabbit/Legends','Seventh Battle of Ruusan/Legends','Pig/Legends'};p=Path(sys.argv[1])
with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
proc=subprocess.Popen(['7z','x','-so',str(p)],stdout=subprocess.PIPE);root=None;out={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or ''
 if title in names:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';out[title]={'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'raw_wikitext':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
 root.clear()
assert proc.wait()==0
f=Path(sys.argv[2]);assert not f.exists();f.write_text(json.dumps(out,ensure_ascii=False));f.chmod(0o600);print('found',len(out),'missing',sorted(names-set(out)))
for k,v in out.items():print(k,'revision',v['revision_id'],'redirect',v['raw_wikitext'].lstrip().casefold().startswith('#redirect'))
