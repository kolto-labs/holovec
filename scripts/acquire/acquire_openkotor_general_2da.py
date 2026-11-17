"""Acquire general 2DA wiki documentation, omitting tables and game-data sections.

Input: pinned OpenKotOR/wiki tar.gz; no game-specific -k1/-k2 pages, code,
Markdown tables or data-statistics sections are included. Generic pages appear
heavily templated; descriptions are unverified and may be inaccurate. GPL-3.0
repository licensing does not establish rights to unmarked third-party content.
"""
import hashlib,json,re,sys,tarfile
from pathlib import Path
from urllib.parse import quote
REV='4adb8a875c3f677e215b2b10a0fdc632834c51c8';ARCHIVE='524f77688bc242b0471c351b6899aa99e6713b53ac7b933501428833087c3414'
p=Path(sys.argv[1]);
with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==ARCHIVE
rows=[];held=[]
with tarfile.open(p,'r:gz') as tar:
 for member in sorted(tar.getmembers(),key=lambda x:x.name):
  if not member.isfile() or '/' not in member.name:continue
  path=member.name.split('/',1)[1]
  if not path.startswith('wiki/odyssey-engine/2da/') or not path.endswith('.md') or '/' in path[len('wiki/odyssey-engine/2da/'):]:continue
  stem=Path(path).stem
  if stem.endswith(('-k1','-k2')):continue
  raw=tar.extractfile(member).read();source=raw.decode('utf-8');blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  source=re.sub(r'(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$', '[code block omitted]',source)
  lines=source.splitlines();out=[];skip_level=None
  for line in lines:
   h=re.match(r'^(#{1,6})\s+(.+?)\s*$',line)
   if h:
    level=len(h.group(1))
    if skip_level is not None and level>skip_level:continue
    skip_level=level if h.group(2).strip().casefold() in {'data statistics','data tables','game availability','file information','class availability (k1)','class availability (k2 additional)'} else None
    if skip_level is not None:continue
   if skip_level is not None or re.match(r'^\s*(\||>|<)',line):continue
   out.append(line)
  text='\n'.join(out).strip()
  text,encoding_claim_removed=re.subn(r'Text-based format with tab-separated values','[generic encoding claim omitted; 2DA has binary and text versions]',text)
  if not text:held.append({'path':path,'reason':'empty after filtering'});continue
  url='https://github.com/OpenKotOR/wiki/blob/'+REV+'/'+quote(path,safe='/')
  rows.append({'title':stem+' 2DA documentation','repository':'OpenKotOR/wiki','commit':REV,'path':path,'blob_sha':blob,'url':url,'source_url':url,'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_text_sha256':hashlib.sha256(raw).hexdigest(),'license':'GPL-3.0','license_url':'https://github.com/OpenKotOR/wiki/blob/'+REV+'/LICENSE.md','attribution':'OpenKotOR/wiki contributors; see file history','evidence_class':'secondary_technical_documentation','alterations':'Markdown tables, code fences, blockquotes and selected data-related sections removed; generic encoding claim omitted when present','encoding_claim_removed':bool(encoding_claim_removed),'coverage':'Heavily templated secondary descriptions; technical claims may be inaccurate, and unmarked third-party material is not cleared. Game-specific data pages excluded.','embedded':False})
out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
Path('data/openkotor-wiki-2da-general.jsonl').write_text(out)
Path('evaluation/openkotor-general-2da-screen.json').write_text(json.dumps({'source_archive_sha256':ARCHIVE,'commit':REV,'included':len(rows),'held':held,'selection':'General 2DA Markdown pages; game-specific -k1/-k2 pages excluded','limitations':'Filtering is not proof of independent authorship or technical accuracy; removed data and code reduce coverage.','output_sha256':hashlib.sha256(out.encode()).hexdigest(),'encoding_correction':{'affected_records':sum(r['encoding_claim_removed'] for r in rows),'disposition':'generic text-only encoding phrase omitted from derived records','evidence_url':'https://synchro.codeberg.page/rakata/formats/text/2da.html','evidence':'Engine analysis describes a binary V2.b path and a text V2.0 path. Specific files and technical claims require separate verification.'}},indent=2)+'\n')
print('Included',len(rows),'held',len(held))
