"""Run on a hosted GPU; write resumable, source-linked vector shards to the Hub."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import os, hashlib, re
import pyarrow as pa, pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, HfApi
from sentence_transformers import SentenceTransformer
REPO='jackmowden/holovec'; MODEL='Qwen/Qwen3-Embedding-8B'; REV='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
api=HfApi(); path=hf_hub_download(REPO,'data/wookieepedia-legends.parquet',repo_type='dataset'); table=pq.read_table(path).to_pylist()
model=SentenceTransformer(MODEL, revision=REV, device='cuda', model_kwargs={'torch_dtype':'float16'})
existing=set(api.list_repo_files(REPO,repo_type='dataset'))
for start in range(0,len(table),100):
 name=f'vectors/wookieepedia-{start:05d}.parquet'
 if name in existing: print('skip',name,flush=True); continue
 rows=[]
 for doc in table[start:start+100]:
  text=doc['text']; pos=0
  while pos<len(text):
   end=min(pos+2000,len(text));
   if end<len(text):
    split=text.rfind(' ',pos+1000,end)
    if split>pos: end=split
   part=text[pos:end].strip()
   if part: rows.append({'id':hashlib.sha256((doc['doc_id']+':'+str(pos)+':'+doc['sha256']).encode()).hexdigest(),'doc_id':doc['doc_id'],'title':doc['title'],'url':doc['url'],'continuity':doc['continuity'],'license':doc['license'],'source_sha256':doc['sha256'],'start':pos,'end':end,'text':part,'model':MODEL,'model_revision':REV})
   if end==len(text): break
   pos=max(pos+1,end-200)
 if not rows: continue
 vectors=model.encode([x['text'] for x in rows],batch_size=8,normalize_embeddings=True,show_progress_bar=False)
 for row,vec in zip(rows,vectors): row['embedding']=vec.tolist()
 dest=f'/tmp/holovec-{start}.parquet';pq.write_table(pa.Table.from_pylist(rows),dest,compression='zstd');api.upload_file(path_or_fileobj=dest,path_in_repo=name,repo_id=REPO,repo_type='dataset',commit_message=f'Add embeddings for articles {start}–{start+len(table[start:start+100])-1}');os.remove(dest);print('uploaded',name,len(rows),flush=True)
