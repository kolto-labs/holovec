"""Acquire pinned MIT-licensed Kolto Labs documentation from source archives.
Usage: python acquire_kolto_docs.py DIRECTORY_CONTAINING_ARCHIVES
Archive filenames: holovec-<repository>.tgz. No embeddings are generated.
"""
import hashlib,json,sys,tarfile
from pathlib import Path
from urllib.parse import quote
PINS={'kotor-formats': {'revision': 'f223b4f573e3b72a25d2ec5d606e101ddbb875ad', 'files': {'README.md': '80be5edcd7a2cbc5508305170d424fd659dc092a', 'crates/kotor-diff/README.md': '912bc223d8dcbd044bb309476203c8623a9a14a2'}, 'license_blob': 'd71bcf9ce7aa688811fdb46b0f2f2a2486c972f2', 'archive_sha256': '393368bd244df739660487adadbac22b11fd2488f820a9ee2b4013f93cced893'}, 'odynsscomp': {'revision': '548f04423ddf98837b12231a060ed308eec12d73', 'files': {'README.md': '7093f2208f0a87626d8251f8640699145608c0cd'}, 'license_blob': '41c97e59cd999900759ece472871b8c6a9b585db', 'archive_sha256': '165a88164900d6fdceeb34f501a8e929688c26a74a0f83515685ac6c14e13b19'}, 'kq': {'revision': '0ff7db7e5695de230326088caae875914f0ded81', 'files': {'README.md': '8b34ec34c1e083bd4c570373501823b699aa2e57', 'docs/user-guide.md': 'fc19ccc30ef8953c1a1b45efdca24c7785520fd6', 'docs/ai-agents.md': '102fbf6a59931ad07e01af47378c50c90058c3d4'}, 'license_blob': '19fbfaaa77c3b1f62b0254e985127b01759beef4', 'archive_sha256': '4c3853e4eb0743fd3abe6ef461f27c64490d864bd87c2295929762387e510de2'}, 'nwscript-ext': {'revision': '4a7f0b094c45ea662c88abc54835dc7a398d2a84', 'files': {'README.md': 'e6fd0880f6e0e0c63bffdfdc643cb143f9ed3e31', 'BUILD.md': '8d7f332924afeb9bdf27db3b559175d7098e5fb2', 'docs/API.md': 'eb3e7eba3b9846a1f6b67db59f0890a419676e40', 'docs/SCOPE.md': '9524758854e4b395c4c694b92934291186ec6457', 'docs/TROUBLESHOOTING.md': '23c13bb135f2493c1ab6c6f9134b216fe1c23501'}, 'license_blob': '3a06cd0c721b461a29d16a3a026441f7802e5eae', 'archive_sha256': 'fb6b3b3e2991a839226964e272ec658156a3c1d1c574e34f53e17c9493562359'}}
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
rows=[];license_dir=Path('data/licenses');license_dir.mkdir(parents=True,exist_ok=True)
for repo,meta in sorted(PINS.items()):
 archive=Path(sys.argv[1])/('holovec-'+repo+'.tgz')
 with archive.open('rb') as f:
  if hashlib.file_digest(f,'sha256').hexdigest()!=meta['archive_sha256']:raise ValueError('archive mismatch: '+repo)
 with tarfile.open(archive,'r:gz') as tar:
  members={m.name.split('/',1)[1]:m for m in tar.getmembers() if m.isfile() and '/' in m.name}
  lic=tar.extractfile(members['LICENSE']).read()
  if blob(lic)!=meta['license_blob']:raise ValueError('license blob mismatch: '+repo)
  (license_dir/('kolto-'+repo+'-MIT.txt')).write_bytes(lic)
  for path,sha in sorted(meta['files'].items()):
   content=tar.extractfile(members[path]).read()
   if blob(content)!=sha:raise ValueError('document blob mismatch: '+repo+'/'+path)
   url='https://github.com/kolto-labs/'+repo+'/blob/'+meta['revision']+'/'+quote(path,safe='/')
   rows.append({'title':repo+' / '+path,'repository':'kolto-labs/'+repo,'path':path,'commit':meta['revision'],'blob_sha':sha,'url':url,'source_url':url,'text':content.decode('utf-8'),'text_sha256':hashlib.sha256(content).hexdigest(),'license':'MIT','license_url':'https://github.com/kolto-labs/'+repo+'/blob/'+meta['revision']+'/LICENSE','attribution':'Repository contributors; see file history','evidence_class':'secondary_technical_documentation','embedded':False})
Path('data/kolto-project-docs.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))
print('Included',len(rows),'documents from',len(PINS),'repositories')
