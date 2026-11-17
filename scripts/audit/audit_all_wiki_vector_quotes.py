"""Audit marked-quotation overlaps in published wiki vectors; metadata only.

Usage: PYTHONPATH=<deps> python audit_all_wiki_vector_quotes.py <pinned-dump.7z> <output.json>
The comparison is a rights-review signal, not proof of copying or clearance.
"""
import collections,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell,pyarrow.parquet as pq
root=Path(__file__).resolve().parents[2];archive=Path(sys.argv[1]); expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected

def shingles(s):
 w=re.findall(r'\w+',str(s).casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
passages=collections.defaultdict(list)
for f in sorted((root/'vectors').glob('wookieepedia-*.parquet')):
 for b in pq.ParquetFile(f).iter_batches(columns=['title','text']):
  for row in b.to_pylist():passages[row['title']].append(shingles(row['text'] or ''))
print('Vector titles',len(passages),'passages',sum(map(len,passages.values())),flush=True)
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);xmlroot=None;found=set();hits=[];withquotes=0
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if xmlroot is None and event=='start':xmlroot=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in passages:
  found.add(title);rev=el.find('{*}revision');raw=rev.findtext('{*}text') or '';code=mwparserfromhell.parse(raw);quotes=[]
  for t in code.filter_templates(recursive=True):
   if re.search(r'(?i)quote|quotation|dialog|speech|crawl|lyrics|poem',str(t.name)):
    quotes.extend(str(p.value.strip_code(normalize=True,collapse=True)) for p in t.params)
  for t in code.filter_tags(recursive=True):
   if str(t.tag).casefold() in ('blockquote','q','poem'):quotes.append(str(t.contents.strip_code(normalize=True,collapse=True)))
  qs=set().union(*(shingles(q) for q in quotes)) if quotes else set()
  if qs:withquotes+=1
  count=sum(bool(qs & sh) for sh in passages[title])
  if count:hits.append({'title':title,'dump_revision_id':rev.findtext('{*}id'),'vector_passages':len(passages[title]),'overlap_passages':count,'marked_quote_blocks':len(quotes)})
 xmlroot.clear()
if proc.wait():raise RuntimeError('decompress failed')
out={'archive_sha256':expected,'method':'Exact eight-word overlap between marked quote, dialogue, crawl, lyrics and poem templates or blockquote/q/poem tags in the pinned newer dump and older published vector passage text, by exact title; metadata only. A match is a review signal, not a rights decision. Misses can arise from title changes, revision changes, formatting, or unmarked quotations.','counts':{'vector_titles':len(passages),'vector_passages':sum(map(len,passages.values())),'exact_title_matches':len(found),'missing_titles':len(passages.keys()-found),'matched_titles_with_marked_sequences':withquotes,'flagged_titles':len(hits),'flagged_passages':sum(h['overlap_passages'] for h in hits)},'flagged_titles':sorted(hits,key=lambda r:(-r['overlap_passages'],r['title'])),'unmatched_titles':sorted(passages.keys()-found)}
out['vector_shards']=[{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((root/'vectors').glob('wookieepedia-*.parquet'))]
Path(sys.argv[2]).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out['counts']),flush=True)
