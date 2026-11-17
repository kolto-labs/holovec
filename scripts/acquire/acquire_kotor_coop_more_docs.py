"""Acquire two reviewed co-op project documents from pinned public Git blobs."""
import hashlib,json
from pathlib import Path
from urllib.parse import quote
import requests
REPO='kolto-labs/kotor-coop';REV='9816b86bcc5c18910ee4d7093c21332fdbfec53c'
FILES={'docs/CONFIG.md':'842a0d206c27cd3131eedd7fb2536ced17d420cb','docs/roadmap-seamless.md':'2e9d7f9ad47a7b90bdea2b0ae3244f40ca312828'}
rows=[]
for path,expected in sorted(FILES.items()):
 r=requests.get('https://raw.githubusercontent.com/'+REPO+'/'+REV+'/'+quote(path,safe='/'),headers={'User-Agent':'HoloVec/0.1 (https://github.com/kolto-labs/holovec)'},timeout=40);r.raise_for_status();b=r.content
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==expected
 url='https://github.com/'+REPO+'/blob/'+REV+'/'+quote(path,safe='/')
 rows.append({'title':'kotor-coop / '+path,'repository':REPO,'path':path,'commit':REV,'blob_sha':expected,'url':url,'source_url':url,'text':b.decode('utf-8'),'text_sha256':hashlib.sha256(b).hexdigest(),'license':'GPL-3.0-only; repository linking permission applies only to consenting contributors and specified use','license_url':'https://github.com/'+REPO+'/blob/'+REV+'/LICENSE','license_copy':'data/licenses/kolto-kotor-coop-GPL-3.0-only.txt','linking_exception_url':'https://github.com/'+REPO+'/blob/'+REV+'/KOTOR-LINKING-EXCEPTION.txt','attribution':'Repository contributors; see file history','evidence_class':'secondary_technical_documentation','coverage':'Historical project documentation at pinned commit; engineering claims are not independently verified, complete repository coverage is not established, and third-party game material rights are separate.','embedded':False})
out=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows);Path('data/kotor-coop-additional-docs.jsonl').write_text(out);print('Included',len(rows),'documents; sha256',hashlib.sha256(out.encode()).hexdigest())
