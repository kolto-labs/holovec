"""Check remote shard completeness and row consistency without local inference."""
import collections, hashlib, math, pyarrow.parquet as pq
from huggingface_hub import HfApi,hf_hub_download
repo='jackmowden/holovec'; files=sorted(f for f in HfApi().list_repo_files(repo,repo_type='dataset') if f.startswith('vectors/wookieepedia-') and f.endswith('.parquet'))
expected={f'vectors/wookieepedia-{i:05d}.parquet' for i in range(0,7234,100)}
print('shards',len(files),'of',len(expected),'missing',len(expected-set(files)))
source=pq.read_table(hf_hub_download(repo,'data/wookieepedia-legends.parquet',repo_type='dataset'),columns=['doc_id','text','sha256']).to_pylist(); lookup={d['doc_id']:d for d in source}; ids=set(); docs=set(); bad=collections.Counter(); rows=0
for f in files:
 path=hf_hub_download(repo,f,repo_type='dataset')
 for batch in pq.ParquetFile(path).iter_batches(batch_size=64):
  for x in batch.to_pylist():
   rows+=1;docs.add(x['doc_id']); v=x['embedding']; norm=math.sqrt(sum(n*n for n in v))
   if x['id'] in ids: bad['duplicate_ids']+=1
   ids.add(x['id'])
   if len(v)!=4096 or any(not math.isfinite(n) for n in v): bad['invalid_vector']+=1
   if x.get('model')!='Qwen/Qwen3-Embedding-8B' or x.get('model_revision')!='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af':bad['model_revision']+=1
   if abs(norm-1)>0.005: bad['normalization']+=1
   if not x['url'] or not x['source_sha256']: bad['missing_provenance']+=1
   original=lookup.get(x['doc_id']);start=x['start'];end=x['end']
   if original is None or x['source_sha256']!=original['sha256']:bad['source_hash']+=1
   elif not (0<=start<end<=len(original['text'])) or x['text']!=original['text'][start:end].strip():bad['source_span']+=1
   expected_id=hashlib.sha256((x['doc_id']+':'+str(start)+':'+x['source_sha256']).encode()).hexdigest()
   if x['id']!=expected_id:bad['id_integrity']+=1
print('rows',rows,'documents',len(docs),'problems',dict(bad))
manifest=__import__('json').load(open(hf_hub_download(repo,'manifest.json',repo_type='dataset')))
if expected-set(files) or bad or len(docs)!=manifest['counts']['wookieepedia_documents'] or rows!=manifest['counts']['wookieepedia_passages']: raise SystemExit(1)
