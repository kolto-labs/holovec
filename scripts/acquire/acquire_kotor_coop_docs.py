"""Acquire three pinned, project-authored KOTOR co-op technical documents.

Repository GPL-3.0-only terms apply to original work; game and third-party
rights remain separate. No game assets are acquired, and no inference runs.
"""
import hashlib,json
from pathlib import Path
from urllib.parse import quote
import requests
REPO='kolto-labs/kotor-coop';REV='9816b86bcc5c18910ee4d7093c21332fdbfec53c';BASE='https://raw.githubusercontent.com/'+REPO+'/'+REV+'/'
FILES={'README.md':'ca6530ad0b76b6ad9bfeb03422324a4001b2d19d','docs/ARCHITECTURE.md':'9987f4d717fd6fa472420a168b4fab70db5bef62','docs/limitations.md':'c09f144277653db1bdbbd04a456e7eac9e935452'}
AUX={'LICENSE':('f288702d2fa16d3cdf0035b15a9fcbc552cd88e7','data/licenses/kolto-kotor-coop-GPL-3.0-only.txt'),'KOTOR-LINKING-EXCEPTION.txt':('0f447034abc303d12887571f59ee78feb857322e','data/licenses/kolto-kotor-coop-linking-exception.txt')}
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
def get(path,expected):
 r=s.get(BASE+quote(path,safe='/'),timeout=40);r.raise_for_status();b=r.content
 if blob(b)!=expected:raise ValueError('blob mismatch: '+path)
 return b
for path,(sha,dest) in AUX.items():
 b=get(path,sha);Path(dest).parent.mkdir(parents=True,exist_ok=True);Path(dest).write_bytes(b)
rows=[]
for path,sha in sorted(FILES.items()):
 b=get(path,sha);url='https://github.com/'+REPO+'/blob/'+REV+'/'+quote(path,safe='/')
 rows.append({'title':'kotor-coop / '+path,'repository':REPO,'path':path,'commit':REV,'blob_sha':sha,'url':url,'source_url':url,'text':b.decode('utf-8'),'text_sha256':hashlib.sha256(b).hexdigest(),'license':'GPL-3.0-only; repository linking permission applies only to consenting contributors and specified use','license_url':'https://github.com/'+REPO+'/blob/'+REV+'/LICENSE','linking_exception_url':'https://github.com/'+REPO+'/blob/'+REV+'/KOTOR-LINKING-EXCEPTION.txt','attribution':'Repository contributors; see file history','evidence_class':'secondary_technical_documentation','coverage':'Selected project documentation only; no game assets fetched. Third-party material, complete multiplayer behavior and exhaustive technical coverage are not established.','embedded':False})
output=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
if hashlib.sha256(output.encode()).hexdigest()!='2a23723a1fb28b608288c4a2faf734a172d18cccb730ebd71975f03b3af8170f':raise ValueError('Output changed; review before release')
Path('data/kotor-coop-technical-docs.jsonl').write_text(output);print('Included',len(rows),'pinned project documents and license evidence')
