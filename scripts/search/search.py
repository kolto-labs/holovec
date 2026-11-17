"""Search published HoloVec shards with lexical and vector retrieval.

Generate query vectors using a hosted model endpoint, or supply an externally
created 4096-dimensional query vector in a JSON file. This runs no model locally.
"""
import argparse, collections, json, math, os, re, urllib.parse
import numpy as np, pyarrow.parquet as pq
from huggingface_hub import HfApi, InferenceClient, hf_hub_download
MODEL='Qwen/Qwen3-Embedding-8B'; REPO='jackmowden/holovec'; REV='1d8ad4ca9b3dd8059ad90a75d4983776a23d44af'
p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--vector-file');p.add_argument('--top',type=int,default=10);p.add_argument('--endpoint',default=os.environ.get('HOLOVEC_EMBEDDING_ENDPOINT'));args=p.parse_args()
if args.top<1:raise SystemExit('--top must be positive')
if args.vector_file:
 q=np.asarray(json.load(open(args.vector_file)),dtype=np.float32)
else:
 raise SystemExit('Hosted inference is on hold until the corpus is complete and the hold is explicitly lifted. Supply --vector-file or use search_corpus.py.')
 target=args.endpoint or MODEL
 client=InferenceClient(model=target,timeout=120)
 prompt='Instruct: Given a question about Star Wars Knights of the Old Republic, retrieve relevant lore passages\nQuery: '+args.query
 q=np.asarray(client.feature_extraction(prompt),dtype=np.float32).reshape(-1)
if q.shape!=(4096,) or not np.isfinite(q).all() or np.linalg.norm(q)==0:raise SystemExit('Query vector must have 4096 finite, nonzero values')
q=q/np.linalg.norm(q);tokenize=lambda s:re.findall(r'[a-z0-9]+',s.casefold());terms=tokenize(args.query)
conflicts=json.loads(open(hf_hub_download(REPO,'catalog/sources/source-conflicts.json',repo_type='dataset'),encoding='utf-8').read())['conflicts']
files=sorted(f for f in HfApi().list_repo_files(REPO,repo_type='dataset') if f.startswith('vectors/') and f.endswith('.parquet'))
if not files:raise SystemExit('No vector shards found')
rows=[];rawscores=[];lengths=[];freqs=[];df=collections.Counter()
for f in files:
 for batch in pq.ParquetFile(hf_hub_download(REPO,f,repo_type='dataset')).iter_batches(batch_size=256):
  table=__import__('pyarrow').Table.from_batches([batch])
  emb=table['embedding'].combine_chunks()
  offsets=np.asarray(emb.offsets.to_numpy());
  if np.any(np.diff(offsets)!=4096):raise SystemExit('Invalid vector dimension in '+f)
  values=np.asarray(emb.values.to_numpy(),dtype=np.float32).reshape(-1,4096)
  if not np.isfinite(values).all():raise SystemExit('Non-finite vector in '+f)
  scores=values @ q
  metadata=table.drop(['embedding']).to_pylist()
  for x,score in zip(metadata,scores):
   if x.get('model')!=MODEL or x.get('model_revision')!=REV:raise SystemExit('Incompatible vector model revision in '+f)
   title=x.get('title') or ''; path=urllib.parse.unquote(urllib.parse.urlparse(x.get('url') or '').path.rsplit('/',1)[-1]).replace('_',' '); path=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',path)
   tf=collections.Counter(tokenize(x['text']));tf.update(tokenize(title));tf.update(tokenize(title));tf.update(tokenize(path));rows.append(x);rawscores.append(float(score));lengths.append(sum(tf.values()));freqs.append(tf);df.update(set(tf).intersection(terms))

n=len(rows);avg=sum(lengths)/n if n else 0
if not n:raise SystemExit('No vector rows found')
lex=[]
for tf,length in zip(freqs,lengths):
 score=0.0
 for term in set(terms):
  count=tf[term]
  if count:score+=math.log(1+(n-df[term]+.5)/(df[term]+.5))*count*2.2/(count+1.2*(.25+.75*length/max(avg,1)))
 lex.append(score)
# Rank each signal and fuse with reciprocal rank fusion. No claim of tuned weights.
def top_rank(scores, positive=False):
 inds=sorted(range(n),key=lambda i:scores[i],reverse=True)[:min(100,n)]
 return {i:rank for rank,i in enumerate(inds,1) if not positive or scores[i]>0}
dense=top_rank(rawscores);sparse=top_rank(lex,True);ids=set(dense)|set(sparse)
ranked=sorted(ids,key=lambda i:(1/(60+dense[i]) if i in dense else 0)+(1/(60+sparse[i]) if i in sparse else 0),reverse=True)
results=[];seen_urls=set()
for i in ranked:
 url=rows[i].get('url')
 if url in seen_urls:continue
 seen_urls.add(url);results.append(i)
 if len(results)>=args.top:break
print(json.dumps({'query':args.query,'model':MODEL,'model_revision':REV,'shards_searched':len(files),'note':'Results cover only shards currently available; inspect COVERAGE.md.','results':[{'title':rows[i].get('title'),'url':rows[i].get('url'),'text':rows[i]['text'],'continuity':rows[i].get('continuity'),'license':rows[i].get('license'),'source_sha256':rows[i].get('source_sha256'),'start':rows[i].get('start'),'end':rows[i].get('end'),'dense_score':rawscores[i],'dense_rank':dense.get(i),'lexical_rank':sparse.get(i),'source_warnings':[c['warning'] for c in conflicts if c['source_url']==rows[i].get('url') and c.get('source_text_sha256')==rows[i].get('source_sha256')]} for i in results]},ensure_ascii=False,indent=2))
