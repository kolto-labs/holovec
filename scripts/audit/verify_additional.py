"""Audit hosted additional-source vector shards without model inference."""
import hashlib,json,math
from huggingface_hub import HfApi,hf_hub_download
import pyarrow.parquet as pq
repo='jackmowden/holovec';paths=['data/wikipedia.jsonl','data/wikipedia-categories.jsonl','data/github-readmes.jsonl','data/github-readmes-extra.jsonl','data/github-project-docs.jsonl','data/strategywiki.jsonl'];docs={}
for path in paths:
 for line in open(hf_hub_download(repo,path,repo_type='dataset'),encoding='utf8'):
  d=json.loads(line);url=d.get('url') or d.get('source_url');docs[url]=hashlib.sha256(d['text'].encode()).hexdigest()
files=sorted(f for f in HfApi().list_repo_files(repo,repo_type='dataset') if f.startswith('vectors/additional-') and f.endswith('.parquet'));seen=set();ids=set();bad={};rows=0
for name in files:
 for batch in pq.ParquetFile(hf_hub_download(repo,name,repo_type='dataset')).iter_batches(batch_size=64):
  for d in batch.to_pylist():
   rows+=1;url=d['url'];seen.add(url);v=d['embedding'];norm=math.sqrt(sum(n*n for n in v))
   for key,fail in [('id_duplicate',d['id'] in ids),('source_hash',docs.get(url)!=d['source_sha256']),('dimension',len(v)!=4096),('nonfinite',not all(math.isfinite(n) for n in v)),('normalization',abs(norm-1)>0.005),('model_revision',d.get('model_revision')!='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af')]:
    if fail:bad[key]=bad.get(key,0)+1
   ids.add(d['id'])
print('shards',len(files),'rows',rows,'sources',len(seen),'expected_sources',len(docs),'errors',bad)
if bad or seen!=set(docs):raise SystemExit(1)
