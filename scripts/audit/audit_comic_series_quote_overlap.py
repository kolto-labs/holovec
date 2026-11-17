"""Metadata-only quote overlap review for a legacy comic-series wiki article.

Run: python audit_comic_series_quote_overlap.py ARCHIVE OUTPUT
Requires the held local record at .cache/held-kotor-comic-series-record.jsonl.
An overlap is a review signal, not a rights conclusion; quote text is not saved.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
import mwparserfromhell
archive=Path(sys.argv[1])
with archive.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
title='Star Wars: Knights of the Old Republic (comic series)'
row=next(x for x in map(json.loads,open('.cache/held-kotor-comic-series-record.jsonl')) if x['title']==title)
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
corpus=shingles(row['text']);proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;found=False
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and event=='start':root=el
 if event!='end' or not el.tag.endswith('}page'):continue
 if el.findtext('{*}title')==title:
  found=True;rev=el.find('{*}revision');code=mwparserfromhell.parse(rev.findtext('{*}text') or '');matched=[];n=0
  for t in code.filter_templates(recursive=True):
   name=str(t.name).strip().casefold().replace('_',' ')
   if name in ('quote','quotation','blockquote','quote box','dialogue','speech') and t.has(1):
    n+=1; overlap=shingles(str(t.get(1).value.strip_code(normalize=True,collapse=True)))&corpus
    if overlap:matched.append({'quote_template_index':n,'distinct_eight_word_matches':len(overlap)})
  out={'title':title,'url':row['url'],'legacy_text_sha256':row['sha256'],'newer_page_revision_id':rev.findtext('{*}id'),'archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','quote_templates':n,'templates_with_eight_word_matches':len(matched),'matches':matched,'method':'Exact eight-word overlap with newer page quote-template first parameters; review signal, not rights determination. No quote text retained.'}
  Path(sys.argv[2]).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='matches'}),flush=True);proc.kill();proc.wait();break
 root.clear()
if not found:raise RuntimeError('page missing')
