"""Compare wiki quote-template word sequences with currently published vectors.

Metadata only: no quotation text leaves this process. Matching is a warning
signal, not a rights determination; different wiki revisions may differ.
Run: PYTHONPATH=<mwparserfromhell path> python audit_swtor_class_quote_overlap.py ARCHIVE OUTPUT
"""
import collections,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell,pyarrow.parquet as pq
root=Path(__file__).resolve().parents[2]
archive=Path(sys.argv[1]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive digest mismatch')
target=json.loads((root/'evaluation/swtor-class-source-audit.json').read_text())['items'];titles={r['article_title'] for r in target}
def words(text):return re.findall(r'\w+',text.casefold())
def shingles(text,n=8):
 w=words(text);return {tuple(w[i:i+n]) for i in range(max(0,len(w)-n+1))}
quote_sets={};source_meta={};proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);xmlroot=None
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if xmlroot is None and event=='start':xmlroot=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in titles:
  rev=el.find('{*}revision');raw=rev.findtext('{*}text') or '';code=mwparserfromhell.parse(raw);quotes=[]
  for t in code.filter_templates(recursive=True):
   if str(t.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech'):
    if t.has(1):quotes.append(str(t.get(1).value.strip_code(normalize=True,collapse=True)))
  quote_sets[title]=set().union(*(shingles(q) for q in quotes)) if quotes else set()
  source_meta[title]={'current_dump_revision':rev.findtext('{*}id'),'quote_templates':len(quotes),'quote_sequences_at_least_eight_words':sum(len(words(q))>=8 for q in quotes)}
 xmlroot.clear()
if proc.wait():raise RuntimeError('archive decompression failed')
if set(source_meta)!=titles:raise ValueError('Missing source titles: '+str(titles-set(source_meta)))
counts=collections.defaultdict(collections.Counter)
for file in sorted((root/'vectors').glob('*.parquet')):
 for batch in pq.ParquetFile(file).iter_batches(columns=['title','text']):
  for row in batch.to_pylist():
   title=row['title']
   if title in titles:
    counts[title]['passages']+=1
    counts[title]['passages_with_eight_word_quote_overlap']+=bool(quote_sets[title]&shingles(row['text'] or ''))
items=[]
for t in sorted(titles):items.append({'title':t,**source_meta[t],**dict(counts[t])})
report={'description':'Metadata-only exact eight-word sequence overlap between quotation templates in a newer wiki dump and vector text from an older WookieeLM snapshot. Overlap is a review signal; it does not resolve authorship, rights or whether other excerpts are present. Quote text is not stored.','archive_sha256':expected,'items':items,'totals':{'classes':len(items),'vector_passages':sum(i.get('passages',0) for i in items),'passages_with_eight_word_quote_overlap':sum(i.get('passages_with_eight_word_quote_overlap',0) for i in items)}}
output=Path(sys.argv[2])
if output.exists():raise FileExistsError(output)
output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report['totals']))
