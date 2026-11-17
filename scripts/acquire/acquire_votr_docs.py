"""Acquire pinned accessibility project documentation without inference.

Only contributor documentation is selected; repository game data, vendored
libraries and assets are excluded. Marked quotes and fenced code are omitted;
this screen does not clear unmarked third-party material.
"""
import hashlib,json,re,requests
from pathlib import Path
from urllib.parse import quote
REPO='JeanStiletto/voice-of-the-old-republic';REV='98cd6e948f49933de6f3207cf1c54c325d17b977'
BASE='https://raw.githubusercontent.com/'+REPO+'/'+REV+'/'
pins={'README.md':'37a47ee64f332d106df0b5babc01e7ce6d9b0aa2','ARCHITECTURE.md':'425c149814d4abc38e733deac9826ccc0b22a325','ACCESSIBILITY_MODDING_GUIDE.md':'c1f207a67767f04589cd6bd1815ddfd7dca6e182'};out=[]
for name in pins:
 r=requests.get(BASE+name,timeout=30);r.raise_for_status();raw=r.content;source=raw.decode('utf-8');blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
 if blob!=pins[name]:raise ValueError('Git blob mismatch: '+name)
 text,ncode=re.subn(r'(?ms)^\s*```[^\n]*\n.*?^\s*```\s*$','[code block omitted]',source)
 text,nquote=re.subn(r'(?m)^\s*>.*$', '[marked quotation omitted]',text)
 text,ninline=re.subn(r'[“"][^“”"\n]{1,300}[”"]','[quoted words omitted]',text)
 text=text.strip();url='https://github.com/'+REPO+'/blob/'+REV+'/'+quote(name,safe='/')
 out.append({'title':'Voice of the Old Republic — '+name,'repository':REPO,'commit':REV,'path':name,'blob_sha':blob,'url':url,'source_url':url,'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_text_sha256':hashlib.sha256(raw).hexdigest(),'license':'GPL-3.0','license_url':'https://github.com/'+REPO+'/blob/'+REV+'/LICENSE','attribution':'Repository contributors; see pinned file history','evidence_class':'secondary_technical_documentation','alterations':{'code_blocks_omitted':ncode,'marked_quote_lines_omitted':nquote,'inline_quotations_omitted':ninline},'coverage':'Accessibility project documentation, not complete game data. Source revision and technical claims may be outdated; unmarked third-party excerpts and game content remain unverified.','embedded':False})
r=requests.get(BASE+'LICENSE',timeout=30);r.raise_for_status();license_bytes=r.content;assert hashlib.sha1(b'blob '+str(len(license_bytes)).encode()+b'\0'+license_bytes).hexdigest()=='63c3050237141612180575faa9c6c641c848d384';Path('data/licenses/votr-GPL-3.0.txt').write_bytes(license_bytes)
Path('data/votr-accessibility-docs.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out))
print('Included',len(out),'documents; altered characters',sum(len(x['text']) for x in out))
