"""Locate passages in a previous metadata-only vector quote audit. Usage: script ARCHIVE FIRST_REPORT OUTPUT."""
import collections,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell,pyarrow.parquet as pq
root=Path(__file__).resolve().parents[2];archive=Path(sys.argv[1]); expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected

def shingles(s):
 w=re.findall(r'\w+',str(s).casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
passages=collections.defaultdict(list)
for f in sorted((root/'vectors').glob('wookieepedia-*.parquet')):
 for b in pq.ParquetFile(f).iter_batches(columns=['title','text','id','doc_id','start','end']):
  for row in b.to_pylist():passages[row['title']].append({'id':row['id'],'doc_id':row['doc_id'],'start':row['start'],'end':row['end'],'shard':str(f.relative_to(root)),'text_sha256':hashlib.sha256((row['text'] or '').encode()).hexdigest(),'shingles':shingles(row['text'] or '')})
candidate={r['title'] for r in json.load(open(sys.argv[2]))['flagged_titles']}; passages={k:v for k,v in passages.items() if k in candidate}; print('Candidate vector titles',len(passages),'passages',sum(map(len,passages.values())),flush=True)
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);xmlroot=None;found=set();hits=[];withquotes=0
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if xmlroot is None and event=='start':xmlroot=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in passages:
  found.add(title);rev=el.find('{*}revision');raw=rev.findtext('{*}text') or '';code=mwparserfromhell.parse(raw);quotes=[]
  for t in code.filter_templates(recursive=True):
   if re.search(r'(?i)quote|quotation|dialog|speech|crawl|lyrics|poem',str(t.name)):
    
    for key in (1,'text','quote'):
     if t.has(key): quotes.append(str(t.get(key).value.strip_code(normalize=True,collapse=True)))
  for t in code.filter_tags(recursive=True):
   if str(t.tag).casefold() in ('blockquote','q','poem'):quotes.append(str(t.contents.strip_code(normalize=True,collapse=True)))
  qs=set().union(*(shingles(q) for q in quotes)) if quotes else set()
  if qs:withquotes+=1
  matches=[{k:v for k,v in p.items() if k!='shingles'} for p in passages[title] if qs & p['shingles']];count=len(matches)
  if count:hits.append({'title':title,'dump_revision_id':rev.findtext('{*}id'),'vector_passages':len(passages[title]),'overlap_passages':count,'marked_quote_blocks':len(quotes),'passage_locations':matches})
 xmlroot.clear()
if proc.wait():raise RuntimeError('decompress failed')
out={'archive_sha256':expected,'method':'Exact eight-word overlap between first positional or text/quote parameters of marked quote, dialogue, crawl, lyrics and poem templates or blockquote/q/poem tags on titles flagged by the first pass in the pinned newer dump and older published vector passage text, by exact title; metadata only. A match is a review signal, not a rights decision. Misses can arise from title changes, revision changes, formatting, or unmarked quotations.','counts':{'vector_titles':len(passages),'vector_passages':sum(map(len,passages.values())),'exact_title_matches':len(found),'missing_titles':len(passages.keys()-found),'matched_titles_with_marked_sequences':withquotes,'flagged_titles':len(hits),'flagged_passages':sum(h['overlap_passages'] for h in hits)},'flagged_titles':sorted(hits,key=lambda r:(-r['overlap_passages'],r['title'])),'unmatched_titles':sorted(passages.keys()-found)}
out['vector_shards']=[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((root/'vectors').glob('wookieepedia-*.parquet'))]
source_file=root/'data/wookieepedia-legends.parquet'
ids={p['doc_id'] for r in hits for p in r['passage_locations']};sources={}
for batch in pq.ParquetFile(source_file).iter_batches(columns=['doc_id','title','sha256']):
 for row in batch.to_pylist():
  if row['doc_id'] in ids:sources[row['doc_id']]=row
for r in hits:
 source_ids={p['doc_id'] for p in r['passage_locations']};r['principal_sources']=[sources[i] for i in sorted(source_ids) if i in sources]
out['principal_source']={'path':str(source_file.relative_to(root)),'sha256':hashlib.sha256(source_file.read_bytes()).hexdigest(),'matched_document_ids':len(sources),'missing_document_ids':sorted(ids-set(sources))}
Path(sys.argv[3]).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out['counts']),flush=True)
