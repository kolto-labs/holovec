"""Embed attributed Arqade posts using a hosted GPU and a pinned model."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import hashlib,json,pyarrow as pa,pyarrow.parquet as pq
from huggingface_hub import hf_hub_download,HfApi
from sentence_transformers import SentenceTransformer
repo='jackmowden/holovec';modelid='Qwen/Qwen3-Embedding-8B';rev='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
docs=[json.loads(x) for x in open(hf_hub_download(repo,'data/arqade.jsonl',repo_type='dataset'),encoding='utf8')];rows=[]
for d in docs:
 text=d['text'];pos=0
 while pos<len(text):
  end=min(pos+2000,len(text))
  if end<len(text):
   split=text.rfind(' ',pos+1000,end)
   if split>pos:end=split
  part=text[pos:end].strip()
  if part:rows.append({'id':hashlib.sha256((d['id']+':'+str(pos)+':'+d['sha256']).encode()).hexdigest(),'doc_id':d['id'],'title':d['title'],'url':d['url'],'license':d['license'],'author_name':d['author_name'],'author_url':d['author_url'],'source_sha256':d['sha256'],'start':pos,'end':end,'text':part,'model':modelid,'model_revision':rev})
  if end==len(text):break
  pos=max(pos+1,end-200)
print('documents',len(docs),'chunks',len(rows),flush=True);model=SentenceTransformer(modelid,revision=rev,device='cuda',model_kwargs={'torch_dtype':'float16'})
for start in range(0,len(rows),300):
 block=rows[start:start+300];vectors=model.encode([x['text'] for x in block],batch_size=8,normalize_embeddings=True)
 for x,v in zip(block,vectors):x['embedding']=v.tolist()
 path='/tmp/holovec-arqade.parquet';pq.write_table(pa.Table.from_pylist(block),path,compression='zstd');HfApi().upload_file(path_or_fileobj=path,path_in_repo=f'vectors/arqade-{start:05d}.parquet',repo_id=repo,repo_type='dataset');print('uploaded',start,len(block),flush=True)
