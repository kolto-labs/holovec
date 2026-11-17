"""Record comic-link redirects and exact destination URLs present in local text layers.

Usage: python reconcile_comic_redirects.py LOCAL_TARGET_SCAN
The scan contains source markup and must stay local; the report contains metadata only.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit
import pyarrow.parquet as pq

x=json.loads(Path(sys.argv[1]).read_text())
if x['source_archive_sha256']!='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456' or x['targets']!=145:raise ValueError('unexpected source scan')
items=[]
for v in x['records'].values():
 raw=v['raw_wikitext']
 if hashlib.sha256(raw.encode()).hexdigest()!=v['raw_wikitext_sha256']:raise ValueError('source hash mismatch')
 m=re.match(r'\s*#redirect\s*\[\[([^\]]+)\]\]',raw,re.I)
 if not m:continue
 target=m.group(1).split('#',1)[0]
 items.append({'source_title':v['title'],'source_url':v['target_url'],'source_revision_id':v['revision_id'],'source_wikitext_sha256':v['raw_wikitext_sha256'],'issue_ids':v['issue_ids'],'destination_title':target,'destination_url':'https://starwars.fandom.com/wiki/'+quote(target.replace(' ','_'),safe=':/()'),'disambiguation':target.endswith(' (disambiguation)'),'corpus_matches':[]})
if len(items)!=11:raise ValueError('redirect set changed')
wanted={v['destination_title']:v for v in items}
manifest=json.loads(Path('manifest.json').read_text());registered={v['path']:v for v in manifest['input_files']};scanned=[]
for f in sorted(Path('data').iterdir()):
 if f.suffix not in ('.jsonl','.parquet'):continue
 digest=hashlib.sha256(f.read_bytes()).hexdigest(); entry=registered.get(str(f))
 if not entry or entry['sha256']!=digest:raise ValueError('unregistered or changed data layer: '+str(f))
 scanned.append({'file':str(f),'sha256':digest})
 if f.suffix=='.jsonl':
  with f.open(encoding='utf8') as fp:docs=[json.loads(line) for line in fp if line.strip()]
 elif f.suffix=='.parquet':docs=pq.read_table(f).to_pylist()
 else:continue
 for d in docs:
  url=d.get('url') or d.get('source_url') or ''
  if urlsplit(url).hostname!='starwars.fandom.com':continue
  parts=unquote(urlsplit(url).path).split('/wiki/',1)
  if len(parts)!=2:continue
  title=parts[1].replace('_',' ')
  if title in wanted:
   item={'file':str(f),'url':url,'title':d.get('title'),'text_sha256':hashlib.sha256((d.get('text') or '').encode()).hexdigest()}
   wanted[title]['corpus_matches'].append(item)
items.sort(key=lambda v:v['source_title'])
report={'description':'Direct redirect destinations and exact destination URLs in local text layers; this does not verify issue-specific coverage, continuity, article rights, or historical redirect targets.','source_archive_sha256':x['source_archive_sha256'],'scanned_data_layers':scanned,'redirects':len(items),'destinations_with_corpus_matches':sum(bool(v['corpus_matches']) for v in items),'disambiguation_destinations':sum(v['disambiguation'] for v in items),'items':items}
Path('evaluation/comic-linked-redirect-reconciliation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print('redirects',report['redirects'],'destination matches',report['destinations_with_corpus_matches'],'disambiguation destinations',report['disambiguation_destinations'])
