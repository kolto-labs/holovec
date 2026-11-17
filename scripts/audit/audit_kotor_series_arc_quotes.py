"""Metadata-only full-page quote overlap screen for the comic arc sections.

Usage: PYTHONPATH=<dependencies> python audit_kotor_series_arc_quotes.py ARCHIVE OUTPUT
This does not establish rights, completeness, or absence of unmarked excerpts.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell
archive=Path(sys.argv[1]);out=Path(sys.argv[2]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
if out.exists():raise FileExistsError(out)
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('Archive hash mismatch')
rows=[json.loads(x) for x in Path('data/wookieepedia-kotor-series-arc-sections.jsonl').read_text().splitlines()]
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
p=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found=False
for ev,el in ET.iterparse(p.stdout,events=('start','end')):
 if root is None and ev=='start':root=el
 if ev!='end' or not el.tag.endswith('}page'):continue
 if el.findtext('{*}title')=='Star Wars: Knights of the Old Republic (comic series)':
  rev=el.find('{*}revision');rid=rev.findtext('{*}id')
  if any(r['revision_id']!=rid for r in rows):raise ValueError('revision mismatch')
  code=mwparserfromhell.parse(rev.findtext('{*}text') or '');names={'quote','quotation','blockquote','quote box','dialogue','speech'}
  quotes=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in names and t.has(1)]
  quotes += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in code.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
  qs=set().union(*(shingles(q) for q in quotes)) if quotes else set();matches=[{'section':r['section'],'text_sha256':r['text_sha256'],'matching_sequences':len(shingles(r['text'])&qs)} for r in rows if shingles(r['text'])&qs]
  result={'description':'Exact eight-word overlaps with quotation blocks in the complete source page at the same revision. Quote text is not stored. A clean result is not rights clearance.','archive_sha256':expected,'revision_id':rid,'quote_blocks':len(quotes),'sections_screened':len(rows),'matches':matches}
  out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('screened',len(rows),'sections; matched',len(matches));found=True;p.kill();p.wait();break
 root.clear()
if not found:raise ValueError('Source page not found')
