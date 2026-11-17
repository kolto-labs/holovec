"""Acquire public project-authored docs and root licenses by pinned Git blob.

Requires authenticated gh CLI; no model inference or game assets are used.
"""
import base64,hashlib,json,subprocess
from pathlib import Path
from urllib.parse import quote
PINS={
 'OdyPatcher':{'commit':'cfb6e80732e6098febf9aef46f4d28c18454bcca','license':'AGPL-3.0-or-later','license_path':'LICENSE','license_blob':'0ad25db4bd1d86c452db3f9602ccdbe172438f52','docs':{'README.md':'7dea2b0c9b4da186d280e7242134b2cdbccf1997','docs/instructions.md':'2c2c4266d2c2851af86047bf93a0e4273bb842f7'}},
 'ModSync.ts':{'commit':'2b3fecbe6b5de0d87dfc003963d245136437b802','license':'GPL-3.0-or-later','license_path':'LICENSE','license_blob':'f288702d2fa16d3cdf0035b15a9fcbc552cd88e7','docs':{'README.md':'2dd8497720c2f20e28eb6e051310288254e1dc0f','docs/KOTOR_FORMATS.md':'c1fa8eeb22af0852a8edbec52f5886a9f4888fec','docs/PHYSICAL_INSTALL.md':'e567ac9477e2f0e7123aeccb84554b8b6691cc86','docs/PLAN.md':'550bef5d8629ab510a2f30fb91d202b9509ebdec','docs/RUNNERS.md':'58d4ca1791919bd68a4bb9f440988ace5f8fa797','packages/core/native/README.md':'1213d408a3da615809804ceceb4a5be903a5b973','packages/electron/README.md':'5692cbbac8db064dfa5e33fcd7a142078ee58744'}},
 'swkotor-web':{'commit':'e5d335f8a5926b49fca5d1520e887462cf45ac7b','license':'GPL-3.0 (version scope not specified)','license_path':'LICENSE.md','license_blob':'3b09f2dbb8e670f045a3595f5a1df8fce6589892','docs':{'README.md':'fdafb53b3183face7a928027efedaa009a7ee052'}},
 'kotor-sourceport':{'commit':'c78aecdc9287fa1aed75d8d0613c1bb658837424','license':'CC0-1.0','license_path':'LICENSE','license_blob':'0e259d42c996742e9e3cba14c677129b2c1b6311','docs':{'README.md':'afbd42322ae4ad112c5bda7731893e0ecc566681'}}}
def blob(repo,sha):
 p=subprocess.run(['gh','api',f'repos/kolto-labs/{repo}/git/blobs/{sha}'],capture_output=True,text=True,check=True);r=json.loads(p.stdout)
 if r.get('sha')!=sha or r.get('encoding')!='base64':raise ValueError('unexpected blob metadata')
 b=base64.b64decode(r['content']);h=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 if h!=sha:raise ValueError('blob hash mismatch')
 return b
rows=[];ld=Path('data/licenses');ld.mkdir(parents=True,exist_ok=True)
for repo,v in sorted(PINS.items()):
 lic=blob(repo,v['license_blob']);license_dest=ld/('kolto-'+repo+'-license.txt');license_dest.write_bytes(lic)
 for path,digest in sorted(v['docs'].items()):
  b=blob(repo,digest);u='https://github.com/kolto-labs/'+repo+'/blob/'+v['commit']+'/'+quote(path,safe='/')
  rows.append({'title':repo+' / '+path,'repository':'kolto-labs/'+repo,'path':path,'commit':v['commit'],'blob_sha':digest,'url':u,'source_url':u,'text':b.decode('utf8'),'text_sha256':hashlib.sha256(b).hexdigest(),'license':v['license'],'license_url':'https://github.com/kolto-labs/'+repo+'/blob/'+v['commit']+'/'+v['license_path'],'license_copy':str(license_dest),'attribution':'Repository contributors; see file history','evidence_class':'secondary_technical_documentation','coverage':'Selected project documentation only; game assets, repository completeness, and third-party content rights are not established.','embedded':False})
rows.sort(key=lambda x:(x['repository'],x['path']));out=''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows);assert hashlib.sha256(out.encode()).hexdigest()=='6615f12a0e414400995061b653a1bd85011fd5a61ae2f1938a8d890a7267bb31';Path('data/kolto-additional-project-docs.jsonl').write_text(out);print('Included',len(rows),'documents across',len(PINS),'repositories; sha256',hashlib.sha256(out.encode()).hexdigest())
