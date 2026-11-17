"""Lexically search every current text layer in a local HoloVec checkout.

This command makes no model or network calls. The manifest selects files and
pins their hashes. Source records remain separate, even when URLs overlap.
"""
import argparse, collections, hashlib, heapq, json, math, re
from pathlib import Path
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
TOKEN=re.compile(r"[a-z0-9]+",re.IGNORECASE)
def tokens(text): return TOKEN.findall(text.casefold())

def records(path):
 if path.suffix=='.jsonl':
  with path.open(encoding='utf-8') as f:
   for line in f:
    if line.strip(): yield json.loads(line)
 elif path.suffix=='.parquet':
  for batch in pq.ParquetFile(path).iter_batches(batch_size=128):
   yield from batch.to_pylist()
 else: raise ValueError('Unsupported text layer: '+str(path))

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('query');parser.add_argument('--top',type=int,default=10);parser.add_argument('--layer',action='append',help='Only search this manifest path; can repeat')
 args=parser.parse_args();query=tokens(args.query)
 if not query or args.top<1:parser.error('query must contain words and --top must be positive')
 terms=set(query);manifest=json.loads((ROOT/'manifest.json').read_text()); conflicts_path=ROOT/'catalog/sources/source-conflicts.json'; conflicts_entry=next(e for e in manifest['input_files'] if e['path']=='catalog/sources/source-conflicts.json');
 if hashlib.sha256(conflicts_path.read_bytes()).hexdigest()!=conflicts_entry['sha256']:raise SystemExit('Manifest hash mismatch: '+str(conflicts_path))
 conflicts=json.loads(conflicts_path.read_text())['conflicts']; entries=[e for e in manifest['input_files'] if e['path'].startswith('data/') and Path(e['path']).suffix in ('.jsonl','.parquet')]
 if args.layer:
  wanted=set(args.layer);known={e['path'] for e in entries}
  if not wanted<=known:parser.error('unknown manifest layer: '+', '.join(sorted(wanted-known)))
  entries=[e for e in entries if e['path'] in wanted]
 candidates=[];df=collections.Counter();chunks=0;total_length=0;doc_count=0;layer_counts={}
 for entry in entries:
  path=ROOT/entry['path']
  if not path.is_file():raise SystemExit('Missing dataset layer: '+str(path))
  with path.open('rb') as f:
   if hashlib.file_digest(f,'sha256').hexdigest()!=entry['sha256']:raise SystemExit('Manifest hash mismatch: '+str(path))
  layer_count=0
  for r in records(path):
   text=r.get('text')
   if not isinstance(text,str) or not text.strip():continue
   layer_count+=1;doc_count+=1
   title=r.get('title') or r.get('path') or r.get('repository') or ''
   title_terms=tokens(title);body=tokens(text)
   # Disjoint word chunks keep long articles from dominating the score and
   # return a bounded, locatable excerpt without invoking an embedding model.
   for start in range(0,len(body),256):
    part=body[start:start+256];tf=collections.Counter(part+title_terms+title_terms);length=sum(tf.values());chunks+=1;total_length+=length
    matched=terms.intersection(tf)
    if not matched:continue
    df.update(matched)
    # Keep original character spans, not reconstructed text or raw token arrays.
    candidates.append((entry['path'],r,title,start,tf,length))
  layer_counts[entry['path']]=layer_count
 avg=total_length/chunks if chunks else 1;heap=[]
 for index,(path,r,title,start,tf,length) in enumerate(candidates):
  score=sum(math.log(1+(chunks-df[t]+.5)/(df[t]+.5))*tf[t]*2.2/(tf[t]+1.2*(.25+.75*length/avg)) for t in terms if tf[t])
  if len(heap)<args.top:heapq.heappush(heap,(score,index))
  elif score>heap[0][0]:heapq.heapreplace(heap,(score,index))
 output=[]
 for score,index in sorted(heap,reverse=True):
  path,r,title,start,_,_=candidates[index];matches=list(TOKEN.finditer(r['text']));span=matches[start:start+256]
  excerpt=r['text'][span[0].start():span[-1].end()] if span else ''
  output.append({'title':title,'url':r.get('url') or r.get('source_url'),'source_revision_url':r.get('source_revision_url'),'layer':path,'license':r.get('license') or r.get('license_spdx'),'continuity':r.get('continuity'),'source_coverage':r.get('coverage'),'source_alterations':r.get('alterations'),'evidence_class':r.get('evidence_class'),'text_sha256':r.get('text_sha256') or r.get('sha256') or hashlib.sha256(r['text'].encode('utf-8')).hexdigest(),'word_start':start,'word_end':start+len(span),'excerpt':excerpt,'lexical_score':score,'source_warnings':[c['warning'] for c in conflicts if c['source_url']==(r.get('url') or r.get('source_url')) and (not c.get('source_revision') or str(c['source_revision'])==str(r.get('revision')))]})
 print(json.dumps({'query':args.query,'retrieval':'BM25-style lexical ranking over 256-word non-overlapping chunks; title terms weighted twice','layers_searched':layer_counts,'documents_searched':doc_count,'chunks_searched':chunks,'note':'Search covers the text layers listed in the current manifest.','results':output},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
