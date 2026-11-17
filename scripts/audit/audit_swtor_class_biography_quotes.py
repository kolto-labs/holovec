"""Screen prepared class sections against full source-page quote blocks.

Usage: PYTHONPATH=<dependencies> python audit_swtor_class_biography_quotes.py ARCHIVE OUTPUT
Does not publish raw quotation text; a clean result is not rights clearance.
"""
import collections,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
import mwparserfromhell
from pathlib import Path
archive=sys.argv[1]
with open(archive,'rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456': raise ValueError('archive mismatch')
files=['data/wookieepedia-swtor-remaining-class-biographies.jsonl','data/wookieepedia-swtor-class-biographies.jsonl']
rows=[]
for p in files:
 for line in open(p):
  r=json.loads(line);r['_source_file']=p;rows.append(r)
titles={r['url'].split('/wiki/',1)[-1] for r in rows}
from urllib.parse import unquote
titles={unquote(x).replace('_',' ') for x in titles}
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
p=subprocess.Popen(['7z','x','-so',archive],stdout=subprocess.PIPE);root=None;reports=[];found=set()
for event,el in ET.iterparse(p.stdout,events=('start','end')):
 if root is None and event=='start':root=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in titles:
  found.add(title);rev=el.find('{*}revision');code=mwparserfromhell.parse(rev.findtext('{*}text') or '')
  q=[]
  for t in code.filter_templates(recursive=True):
   if str(t.name).strip().casefold().replace('_',' ') in ('quote','quotation','blockquote','quote box','dialogue','speech'):
    if t.has(1): q.append(str(t.get(1).value.strip_code(normalize=True,collapse=True)))
  for t in code.filter_tags(recursive=True):
   if str(t.tag).casefold() in ('blockquote','q'):q.append(t.contents.strip_code(normalize=True,collapse=True))
  sequences=set().union(*(shingles(t) for t in q)) if q else set()
  for r in rows:
   if unquote(r['url'].split('/wiki/',1)[-1]).replace('_',' ')!=title:continue
   if r['revision_id']!=rev.findtext('{*}id'):raise ValueError('revision mismatch')
   overlap=shingles(r['text']) & sequences
   if overlap: reports.append({'title':title,'section':r['section'],'source_file':r['_source_file'],'text_sha256':r['text_sha256'],'distinct_eight_word_sequences':len(overlap)})
  print('screened',title,'quote blocks',len(q),flush=True)
 root.clear()
if p.wait()!=0:raise RuntimeError('7z failure')
if found!=titles:raise ValueError('missing titles: '+str(titles-found))
out={'description':'Eight-word overlaps against quotation template and blockquote text from whole source pages at the same revisions. A match is a review signal, and absence does not clear unmarked quotations or establish rights. No source text included.','archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','rows_screened':len(rows),'overlaps':reports}
output=Path(sys.argv[2])
if output.exists(): raise FileExistsError(output)
output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('DONE overlaps',len(reports))
