"""Find exact publisher-path references in a pinned Wookieepedia dump.

Usage: python reconcile_swtor_blog_references.py ARCHIVE
The report retains page titles and hashes, never page text. A citation is a
research lead and does not establish relevance, completeness, or reuse rights.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote,urlsplit
import pyarrow.parquet as pq
archive=Path(sys.argv[1]);expected='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected:raise ValueError('archive changed')
m=json.loads(Path('manifest.json').read_text());registered={v['path']:v for v in m['input_files']}
def verify(p):
 b=p.read_bytes();digest=hashlib.sha256(b).hexdigest();v=registered.get(str(p))
 if not v or (v['size'],v['sha256'])!=(len(b),digest):raise ValueError('unregistered or changed: '+str(p))
 return digest
inventory=Path('catalog/works/swtor-narrative-blog-inventory.json');inventory_hash=verify(inventory);leads=json.loads(inventory.read_text())['items'];needles={}
for v in leads:
 path=unquote(urlsplit(v['publisher_url']).path).lstrip('/').casefold()
 if path in needles:raise ValueError('duplicate path')
 needles[path]={'title':v['title'],'publisher_url':v['publisher_url'],'wiki_pages':[]}
if len(needles)!=33:raise ValueError('lead count changed')
original_leads=list(needles.values());aliases=Path('catalog/works/swtor-narrative-blog-aliases.json');aliases_hash=verify(aliases)
by_url={v['publisher_url']:needles[unquote(urlsplit(v['publisher_url']).path).lstrip('/').casefold()] for v in leads}
for alias in json.loads(aliases.read_text())['items']:
 if not alias.get('verified_same_article'):continue
 path=unquote(urlsplit(alias['date_url']).path).lstrip('/').casefold();target=by_url[alias['source_url']]
 if path in needles and needles[path] is not target:raise ValueError('alias collision')
 needles[path]=target
pattern=re.compile('|'.join('(?<![a-z0-9_/-])'+re.escape(x)+'(?![a-z0-9_/%-])' for x in sorted(needles,key=len,reverse=True)),re.I)
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE);root=None;pages=0
for ev,e in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 title=e.findtext('{*}title') or '';ns=e.findtext('{*}ns');rev=e.find('{*}revision');raw=rev.findtext('{*}text') or '' if rev is not None else ''
 if ns=='0':
  pages+=1;decoded=unquote(raw).casefold();matched={t.group() for t in pattern.finditer(decoded)} if ('blog/' in decoded or 'info/news/' in decoded) else set()
  for path in matched:
   needles[path]['wiki_pages'].append({'title':title,'revision_id':rev.findtext('{*}id'),'source_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'matched_publisher_path':path,'corpus_matches':[]})
 root.clear()
if proc.wait()!=0:raise RuntimeError('archive decompression failed')
wiki_index={}
for lead in needles.values():
 for page in lead['wiki_pages']:wiki_index.setdefault(page['title'],[]).append(page)
scanned=[]
for p in sorted(Path('data').iterdir()):
 if p.suffix not in ('.jsonl','.parquet'):continue
 scanned.append({'file':str(p),'sha256':verify(p)})
 if p.suffix=='.jsonl':
  with p.open(encoding='utf8') as f:docs=[json.loads(x) for x in f if x.strip()]
 else:docs=pq.read_table(p).to_pylist()
 for d in docs:
  u=d.get('url') or d.get('source_url') or '';parts=unquote(urlsplit(u).path).split('/wiki/',1)
  if urlsplit(u).hostname!='starwars.fandom.com' or len(parts)!=2:continue
  title=parts[1].replace('_',' ')
  for page in wiki_index.get(title,[]):
   page['corpus_matches'].append({'file':str(p),'url':u,'title':d.get('title'),'text_sha256':hashlib.sha256((d.get('text') or '').encode()).hexdigest()})
for v in original_leads:v['wiki_pages'].sort(key=lambda x:x['title'])
items=sorted(original_leads,key=lambda x:x['title']);report={'scope':'Exact publisher path matches including verified date aliases in main-namespace pages of one pinned dump; other URL aliases and alternate paths can be missed. Citation occurrence does not prove relevant content, story coverage, or text rights. No publisher prose is included.','source_archive_sha256':expected,'inventory_sha256':inventory_hash,'alias_observations_sha256':aliases_hash,'verified_alias_paths':sum(v.get('verified_same_article',False) for v in json.loads(aliases.read_text())['items']),'wiki_pages_scanned':pages,'data_layers':scanned,'leads':len(items),'leads_with_wiki_citations':sum(bool(x['wiki_pages']) for x in items),'leads_with_existing_corpus_page':sum(any(p['corpus_matches'] for p in x['wiki_pages']) for x in items),'items':items}
Path('evaluation/swtor-narrative-blog-citations.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print('wiki pages',pages,'leads',len(items),'cited',report['leads_with_wiki_citations'],'corpus matches',report['leads_with_existing_corpus_page'])
