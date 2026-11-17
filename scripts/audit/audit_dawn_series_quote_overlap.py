"""Compare old and new Dawn wiki text with source-page quotation blocks.

Usage: PYTHONPATH=<dependencies> python audit_dawn_series_quote_overlap.py ARCHIVE OUTPUT
Cross-revision overlap is a warning signal, not a rights conclusion.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive hash mismatch')
rows=[]
for p in ('data/wookieepedia-publication-summaries.jsonl','data/wookieepedia-dawn-series-sections.jsonl'):
 for line in open(p):
  r=json.loads(line)
  if r['title'].startswith('Star Wars: Dawn of the Jedi'):
   if p.endswith('dawn-series-sections.jsonl'):title=r['title'].split(' — ',1)[0]
   else:title=r['title']
   if title in {'Star Wars: Dawn of the Jedi','Star Wars: Dawn of the Jedi: Force Storm','Star Wars: Dawn of the Jedi: The Prisoner of Bogan','Star Wars: Dawn of the Jedi: Force War'}:rows.append((p,title,r))
targets={t for _,t,_ in rows}
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
p=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found=set();matches=[];meta=[]
for ev,e in ET.iterparse(p.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title')
 if title in targets:
  found.add(title);v=e.find('{*}revision');rid=v.findtext('{*}id');c=mwparserfromhell.parse(v.findtext('{*}text') or '');names={'quote','quotation','blockquote','quote box','dialogue','speech'}
  quotes=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in c.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in names and t.has(1)]
  quotes += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in c.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
  qset=set().union(*(shingles(q) for q in quotes)) if quotes else set();meta.append({'title':title,'source_revision_id':rid,'quote_blocks':len(quotes)})
  for path,t,r in rows:
   if t!=title:continue
   if path.endswith('dawn-series-sections.jsonl') and r['revision_id']!=rid:raise ValueError('revision mismatch')
   n=len(shingles(r['text'])&qset)
   if n:matches.append({'dataset':path,'title':r['title'],'text_sha256':r.get('text_sha256') or r.get('sha256'),'matching_eight_word_sequences':n})
 root.clear()
if p.wait()!=0:raise RuntimeError('decompression failed')
if found!=targets:raise ValueError('missing pages')
out.write_text(json.dumps({'description':'Exact eight-word overlap between source page quotation blocks and older legacy or newer quote-omitted records. Older records have unknown source revisions. Does not detect unmarked excerpts or establish rights. No quote text retained.','archive_sha256':expected,'pages':meta,'records_screened':len(rows),'matches':matches},indent=2,ensure_ascii=False)+'\n');print('screened',len(rows),'records; matches',len(matches));print([(x['dataset'],x['title'],x['matching_eight_word_sequences']) for x in matches])
