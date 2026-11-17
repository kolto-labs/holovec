"""Embed the separately licensed Wikipedia and project README snapshots on a hosted GPU."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import json, hashlib, os, pyarrow as pa, pyarrow.parquet as pq
from huggingface_hub import hf_hub_download,HfApi
from sentence_transformers import SentenceTransformer
repo='jackmowden/holovec';modelid='Qwen/Qwen3-Embedding-8B';rev='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
inputs=['data/wikipedia.jsonl','data/wikipedia-categories.jsonl','data/github-readmes.jsonl','data/github-readmes-extra.jsonl','data/github-project-docs.jsonl','data/strategywiki.jsonl'];docs={}
for path in inputs:
 for line in open(hf_hub_download(repo,path,repo_type='dataset'),encoding='utf8'):
  d=json.loads(line); url=d.get('url') or d.get('source_url');docs[url]=d
model=SentenceTransformer(modelid,revision=rev,device='cuda',model_kwargs={'torch_dtype':'float16'});rows=[]
for url,d in docs.items():
 text=d['text'];h=hashlib.sha256(text.encode()).hexdigest();pos=0
 while pos<len(text):
  end=min(pos+2000,len(text))
  if end<len(text):
   split=text.rfind(' ',pos+1000,end)
   if split>pos:end=split
  content=text[pos:end].strip()
  if content:rows.append({'id':hashlib.sha256((url+':'+str(pos)+':'+h).encode()).hexdigest(),'doc_id':url,'title':d.get('title') or d.get('repository'),'url':url,'license':d.get('license') or d.get('license_spdx'),'source_sha256':h,'start':pos,'end':end,'text':content,'model':modelid,'model_revision':rev})
  if end==len(text):break
  pos=max(pos+1,end-200)
print('documents',len(docs),'chunks',len(rows),flush=True)
for start in range(0,len(rows),300):
 block=rows[start:start+300];v=model.encode([x['text'] for x in block],batch_size=8,normalize_embeddings=True)
 for x,e in zip(block,v):x['embedding']=e.tolist()
 path='/tmp/holovec-additional.parquet';pq.write_table(pa.Table.from_pylist(block),path,compression='zstd');HfApi().upload_file(path_or_fileobj=path,path_in_repo=f'vectors/additional-{start:05d}.parquet',repo_id=repo,repo_type='dataset');print('uploaded',start,len(block),flush=True)
