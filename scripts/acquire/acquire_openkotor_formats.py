"""Acquire selected OpenKotOR format docs from the pinned source archive.

The file-type documentation is a technical secondary source. Game 2DA data
and game filesystem inventories in the same repository are intentionally not
selected. This script does not infer or create embeddings.
"""
import hashlib,json,sys,tarfile
from pathlib import Path
from urllib.parse import quote
REV='4adb8a875c3f677e215b2b10a0fdc632834c51c8'
ARCHIVE_SHA='524f77688bc242b0471c351b6899aa99e6713b53ac7b933501428833087c3414'
ARCHIVE_URL='https://github.com/OpenKotOR/wiki/archive/'+REV+'.tar.gz'
PINS={'wiki/file-types/2da.md': '17278a1b8391e9127c8e0729798dcb3bf6960f8a', 'wiki/file-types/audio-files.md': '9af01bcd36d3e46509de5943c8122d259a54ff1b', 'wiki/file-types/bif.md': '35fef5e54a79aac8447113554b3ce69b1cd23e19', 'wiki/file-types/dlg.md': '2343196ff290c6199122108a4ff909f7e8b04661', 'wiki/file-types/erf.md': '59090d2ae0d23693d80524d6f3b2fcf9c3d198dc', 'wiki/file-types/gff.md': 'ab1f7619c4d92b588c265bbbc48e90421a8aed8f', 'wiki/file-types/index.md': '13fde192a9069989d1bdaeb9138a87321b0828ea', 'wiki/file-types/key.md': 'f10313f3ebbb9b506b1ff9ef0dba1e3291fabfc0', 'wiki/file-types/lip.md': '3b2e40cf3364d537097222cd851865f83cc675a7', 'wiki/file-types/resource-types.md': 'ff3a64d9fd1ae53ced0082132ad851306290213f', 'wiki/file-types/sav.md': '6ff9ee0b8a0f18218ca9ea9985cb8cabac830ac3', 'wiki/file-types/ssf.md': '309f3304d74df1981e3209b2916cb4d5091abb32', 'wiki/file-types/tlk.md': '3297304a83af3b2f2bfba7c8eb4a9d5460b090d9', 'wiki/file-types/tpc.md': 'df164301d6408ed92344f6e2665e445ed52467f8', 'wiki/file-types/txi.md': '21bb3a01f2b2c9e597c31213b924b3adae8cb690', 'wiki/file-types/uti.md': 'c3e10506d633843af09d947f07211cef468f5f3e', 'wiki/file-types/wok.md': '3a4546c3d759834308d98ad1b3c992c802a01751'}
with open(sys.argv[1],'rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=ARCHIVE_SHA:raise ValueError('unexpected archive digest')
rows=[]
with tarfile.open(sys.argv[1],'r:gz') as tar:
 members={m.name.split('/',1)[1]:m for m in tar.getmembers() if m.isfile() and '/' in m.name}
 for path,blob in sorted(PINS.items()):
  content=tar.extractfile(members[path]).read(); actual=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
  if actual!=blob:raise ValueError('blob mismatch: '+path)
  text=content.decode('utf-8');url='https://github.com/OpenKotOR/wiki/blob/'+REV+'/'+quote(path,safe='/')
  rows.append({'title':path.rsplit('/',1)[-1][:-3]+' file format','repository':'OpenKotOR/wiki','commit':REV,'path':path,'blob_sha':blob,'url':url,'source_url':url,'text':text,'text_sha256':hashlib.sha256(content).hexdigest(),'license':'GPL-3.0','license_url':'https://github.com/OpenKotOR/wiki/blob/'+REV+'/LICENSE.md','attribution':'OpenKotOR/wiki contributors; see file history','evidence_class':'secondary_technical_documentation','embedded':False})
 license_bytes=tar.extractfile(members['LICENSE.md']).read()
 out=Path('data/licenses/openkotor-wiki-GPL-3.0.md');out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(license_bytes)
Path('data/openkotor-wiki-formats.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))
print('Included',len(rows),'technical documents; game data tables excluded')
