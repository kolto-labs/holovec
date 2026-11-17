"""Extract local wiki appearance-section markup for inventoried comic issues.

Usage: python prepare_comic_appearance_metadata.py ARCHIVE LOCAL_OUTPUT
Raw source markup remains local and is not approved for public redistribution.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote
arc=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with arc.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive mismatch')
snapshot_ids={v['work_id'] for v in json.loads(Path('evaluation/comic-appearance-extraction.json').read_text())['items']};assert len(snapshot_ids)==144;issues=[v for v in json.loads(Path('catalog/works/comics-issue-inventory.json').read_text())['issues'] if v['work_id'] in snapshot_ids];assert {v['work_id'] for v in issues}==snapshot_ids;targets={}
for i in issues:
 u=next((i[k].get('url') for k in ('reviewed_plot_section','secondary_summary','secondary_summary_held') if i.get(k,{}).get('url')),None)
 if u:title=unquote(u.split('/wiki/',1)[-1]).replace('_',' ')
 elif i['work_id']=='dawn-2012-000':title='Star Wars: Dawn of the Jedi 0'
 elif i['series'].startswith('Dawn of the Jedi:'):title=i['series']+' '+str(i['issue_number'])
 else:raise ValueError('Missing title: '+i['work_id'])
 if title in targets:raise ValueError('Duplicate title '+title)
 targets[title]=i['work_id']
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$');proc=subprocess.Popen(['7z','x','-so',str(arc)],stdout=subprocess.PIPE);root=None;found={}
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title')
 if title in targets:
  v=e.find('{*}revision');raw=v.findtext('{*}text') or '';hs=list(head.finditer(raw));matches=[(i,h) for i,h in enumerate(hs) if h.group(2).strip().casefold()=='appearances'];record={'work_id':targets[title],'title':title,'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'sections':[]}
  for i,h in matches:
   end=next((z.start() for z in hs[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));section=raw[h.end():end].strip();record['sections'].append({'raw_wikitext':section,'sha256':hashlib.sha256(section.encode()).hexdigest()})
  found[title]=record
 root.clear()
if proc.wait()!=0:raise RuntimeError('decompression failed')
result={'source_archive_sha256':expected,'target_count':len(targets),'not_found':[{'title':t,'work_id':targets[t]} for t in sorted(set(targets)-set(found))],'records':found};out.write_text(json.dumps(result,ensure_ascii=False));out.chmod(0o600)
print('targets',len(targets),'found',len(found),'not found',len(result['not_found']),'with appearances',sum(bool(x['sections']) for x in found.values()))
