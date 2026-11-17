"""Hold four legacy documents and vectors with marked quotation overlaps.

A reversible current-release precaution; prior published revisions are not erased.
Run only on the exact audited source and vector snapshot. No inference is run.
"""
import json,hashlib,pathlib,subprocess
import pyarrow as pa,pyarrow.compute as pc,pyarrow.parquet as pq
expected={'wookieepedia/R/Rakatan_revolt.md':('a9205c17117e42657d014193199be26d794701829975845d9aa0f5ba008c1802','vectors/wookieepedia-04900.parquet',4),'wookieepedia/S/Sith_(language).md':('04c35a9bc2c4f4b4e02b3ba1db12b6aad3012c4823cc504b8417dd54d93f743e','vectors/wookieepedia-05500.parquet',10),'wookieepedia/X/XoXaan.md':('9a7065a13fab159dc0358744059e82c19e8b9888ae6c9fb882f846593678653a','vectors/wookieepedia-07000.parquet',8),'wookieepedia/Z/Ziost_Legends.md':('1edb454b4dbc9cf2a982d1f305249c6ca6ae960f2efbd7c8bd08687f9c0aea15','vectors/wookieepedia-07200.parquet',21)}
src=pathlib.Path('data/wookieepedia-legends.parquet');table=pq.read_table(src);matches=[r for r in table.select(['doc_id','title','sha256','url']).to_pylist() if r['doc_id'] in expected]
if len(matches)!=len(expected) or any(r['sha256']!=expected[r['doc_id']][0] for r in matches):raise ValueError('Unexpected source snapshot')
prepared=[];passages=[]
for doc,(sha,path,count) in expected.items():
 t=pq.read_table(path);old=[r for r in t.select(['id','doc_id','start','end']).to_pylist() if r['doc_id']==doc]
 if len(old)!=count:raise ValueError('Unexpected vector count '+doc)
 passages.extend([{**r,'shard':path} for r in old]);prepared.append((path,t.filter(pc.not_equal(t['doc_id'],doc))))
report={'description':'Four legacy wiki articles and all associated vector passages held after exact matches to marked quotations in newer source revisions. Attribution and rights need independent review; this is a precaution, not a rights determination. Prior releases remain accessible.','previous_git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'source_audit':'evaluation/kotor-quote-source-trace.json','replacement':'data/wookieepedia-remaining-quote-replacements.jsonl','articles':matches,'held_passages':passages,'counts':{'articles':len(matches),'passages':len(passages)}}
pathlib.Path('evaluation/remaining-vector-quotation-holds.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');pq.write_table(table.filter(pc.invert(pc.is_in(table['doc_id'],value_set=pa.array(list(expected))))),src,compression='zstd')
for path,t in prepared:pq.write_table(t,path,compression='zstd')
print('Held',len(matches),'articles and',len(passages),'passages')
