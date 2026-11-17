from pathlib import Path
"""Evaluate the published hybrid search using hosted query inference."""
raise SystemExit('Inference is on hold until the corpus is complete and the hold is explicitly lifted. No local inference is permitted.')
import json,os,subprocess,sys,tempfile
from sentence_transformers import SentenceTransformer
from huggingface_hub import hf_hub_download
repo='jackmowden/holovec';modelid='Qwen/Qwen3-Embedding-8B';rev='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
cases=os.environ.get('HOLOVEC_EVAL_CASES','evaluation/cross-source-smoke.json');data=json.load(open(hf_hub_download(repo,cases,repo_type='dataset')))['results']
m=SentenceTransformer(modelid,revision=rev,device='cuda',model_kwargs={'torch_dtype':'float16'});prefix='Instruct: Given a question about Star Wars Knights of the Old Republic, retrieve relevant lore passages\nQuery: ';q=m.encode([prefix+x['query'] for x in data],normalize_embeddings=True)
results=[]
with tempfile.TemporaryDirectory() as tmp:
 for i,case in enumerate(data):
  vf=os.path.join(tmp,'query.json');json.dump(q[i].tolist(),open(vf,'w'));env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';r=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[2] / 'scripts/search/search.py'),case['query'],'--vector-file',vf,'--top','20'],capture_output=True,text=True,env=env,check=True);hits=json.loads(r.stdout)['results'];rank=next((j+1 for j,x in enumerate(hits) if x['url']==case['expected_url']),None);results.append({'query':case['query'],'expected_url':case['expected_url'],'rank_at_20':rank,'top_urls':[x['url'] for x in hits[:5]]})
print(json.dumps({'scope':'hybrid smoke check; cases: '+cases+'; not a representative benchmark','results':results},indent=2))
