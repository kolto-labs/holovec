"""Select KotOR-related Legends articles from the pinned public WookieeLM corpus."""
import hashlib, json, re
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
REV='5d19bba512fa8c65b225c1819d7971db316b871c'
PAT=re.compile(r'knights of the old republic|the sith lords|\bkotor\b|the old republic',re.I)
holds=json.loads(Path('evaluation/wiki-class-rights-holds.json').read_text())
held_ids={r['doc_id'] for r in holds['articles']}
core_holds=json.loads(Path('evaluation/kotor-core-rights-holds.json').read_text())
held_ids.update(r['doc_id'] for r in core_holds['articles'])
followup_holds=json.loads(Path('evaluation/kotor-quote-followup-holds.json').read_text())
held_ids.update(r['doc_id'] for r in followup_holds['articles'])
old_republic_holds=json.loads(Path('evaluation/old-republic-quote-followup-holds.json').read_text())
held_ids.update(r['doc_id'] for r in old_republic_holds['articles'])
batch2_holds=json.loads(Path('evaluation/old-republic-batch2-quote-holds.json').read_text())
held_ids.update(r['doc_id'] for r in batch2_holds['articles'])
hk47_holds=json.loads(Path('evaluation/hk47-quote-hold.json').read_text())
held_ids.update(r['doc_id'] for r in hk47_holds['articles'])
remaining_holds=json.loads(Path('evaluation/remaining-vector-quotation-holds.json').read_text())
held_ids.update(r['doc_id'] for r in remaining_holds['articles'])
rows=[]
for i in range(2):
 p=hf_hub_download('rafa-rrayes/wookieelm-corpus',f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV)
 for batch in pq.ParquetFile(p).iter_batches(batch_size=500):
  for x in batch.to_pylist():
   if x['continuity']=='legends' and x['doc_id'] not in held_ids and PAT.search(x['text']):
    x['sha256']=hashlib.sha256(x['text'].encode()).hexdigest(); x['upstream_revision']=REV; x['evidence_class']='secondary'; rows.append(x)
Path('data').mkdir(exist_ok=True)
pq.write_table(pa.Table.from_pylist(rows),'data/wookieepedia-legends.parquet',compression='zstd')
print(json.dumps({'records':len(rows),'upstream_revision':REV,'selection':PAT.pattern}))
