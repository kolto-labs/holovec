"""Hosted retrieval smoke check across wiki, walkthrough, and tool documentation."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import json,numpy as np,pyarrow.parquet as pq
from huggingface_hub import HfApi,hf_hub_download
from sentence_transformers import SentenceTransformer
repo='jackmowden/holovec';modelid='Qwen/Qwen3-Embedding-8B';revision='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
queries=[('How do Jedi Guardian Sentinel and Consular classes differ in KOTOR II?','https://strategywiki.org/wiki/Star_Wars_Knights_of_the_Old_Republic_II:_The_Sith_Lords/Classes'),('How do I open and control the module editor in Holocron Toolset?','https://github.com/NickHugi/PyKotor/blob/5b7fb9c63b22906fa6c64b410140aaedab5e5c60/Tools/HolocronToolset/src/toolset/help/tools/1-moduleEditor.md'),('How do I create a merchant store on the Ebon Hawk using the Holocron Toolset?','https://github.com/NickHugi/PyKotor/blob/5b7fb9c63b22906fa6c64b410140aaedab5e5c60/Tools/HolocronToolset/src/toolset/help/tutorials/2-creatingANewStore.md'),('How do I enter the Sith base on Taris in KOTOR?','https://strategywiki.org/wiki/Star_Wars:_Knights_of_the_Old_Republic/Sith_Base_(Taris)')]
files=sorted(f for f in HfApi().list_repo_files(repo,repo_type='dataset') if f.startswith('vectors/') and f.endswith('.parquet'))
if len([f for f in files if f.startswith('vectors/wookieepedia-')])!=73 or len([f for f in files if f.startswith('vectors/additional-')])!=6:raise SystemExit('Complete shard sets required')
model=SentenceTransformer(modelid,revision=revision,device='cuda',model_kwargs={'torch_dtype':'float16'});prefix='Instruct: Given a question about Star Wars Knights of the Old Republic, retrieve relevant lore passages\nQuery: ';q=model.encode([prefix+x[0] for x in queries],normalize_embeddings=True);best=[[] for _ in queries]
for f in files:
 for batch in pq.ParquetFile(hf_hub_download(repo,f,repo_type='dataset')).iter_batches(batch_size=256,columns=['url','embedding']):
  t=batch.to_pydict();v=np.asarray(t['embedding'],dtype=np.float32);scores=q@v.T
  for i in range(len(queries)):
   inds=np.argpartition(scores[i],-min(20,len(v)))[-min(20,len(v)):];best[i]=sorted(best[i]+[(float(scores[i,j]),t['url'][j]) for j in inds],reverse=True)[:20]
results=[]
for (question,url),hits in zip(queries,best):
 rank=next((i+1 for i,(_,u) in enumerate(hits) if u==url),None);results.append({'query':question,'expected_url':url,'rank_at_20':rank,'top_urls':[u for _,u in hits[:5]]})
print(json.dumps({'scope':'four-query source smoke check; not a representative benchmark','results':results},indent=2))
