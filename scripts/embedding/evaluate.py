"""Hosted-GPU retrieval smoke evaluation; expected titles are a small, non-exhaustive benchmark."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import json, numpy as np, pyarrow.parquet as pq
from huggingface_hub import HfApi,hf_hub_download
from sentence_transformers import SentenceTransformer
REPO='jackmowden/holovec'; MODEL='Qwen/Qwen3-Embedding-8B'; REV='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
queries=[('Who trained the Jedi Exile and was known as Darth Traya?','Kreia'),('Who was the Jedi who used battle meditation and accompanied Revan?','Bastila Shan'),('What ancient space station produced the Sith fleet in the Jedi Civil War?','Star Forge'),('Which planet was devastated by the Mass Shadow Generator?','Malachor V'),('Which assassin droid calls humans meatbags?','HK-47')]
files=sorted(f for f in HfApi().list_repo_files(REPO,repo_type='dataset') if f.startswith('vectors/wookieepedia-') and f.endswith('.parquet'))
if len(files)!=73: raise SystemExit(f'Expected 73 vector shards, found {len(files)}')
model=SentenceTransformer(MODEL,revision=REV,device='cuda',model_kwargs={'torch_dtype':'float16'})
prefix='Instruct: Given a question about Star Wars Knights of the Old Republic, retrieve relevant lore passages\nQuery: '
q=model.encode([prefix+x[0] for x in queries],normalize_embeddings=True)
best=[[] for _ in queries]
for f in files:
 t=pq.read_table(hf_hub_download(REPO,f,repo_type='dataset'),columns=['title','embedding']); d=t.to_pylist();v=np.asarray([x['embedding'] for x in d],dtype=np.float32);scores=q@v.T
 for i in range(len(queries)):
  inds=np.argpartition(scores[i],-min(20,len(d)))[-min(20,len(d)):]
  best[i]=sorted(best[i]+[(float(scores[i,j]),d[j]['title']) for j in inds],reverse=True)[:20]
report=[]
for (question,expected),hits in zip(queries,best):
 rank=next((i+1 for i,(_,title) in enumerate(hits) if title.casefold()==expected.casefold()),None)
 report.append({'query':question,'expected_title':expected,'rank_at_20':rank,'top_titles':[t for _,t in hits[:5]]})
print(json.dumps({'scope':'small smoke evaluation, not a quality benchmark','results':report},indent=2))
