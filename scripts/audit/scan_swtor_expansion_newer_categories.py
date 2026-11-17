import json,hashlib,subprocess,re,xml.etree.ElementTree as E
from pathlib import Path
p=Path('/tmp/holovec-wookieepedia-20261108.xml.7z')
with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
old=json.load(open('evaluation/swtor-expansion-category-census.json'));cats={k.casefold():k for k in old['category_counts']};oldnames={v['title'].replace('_',' ').casefold() for v in old['items']};result=[];scanned=0
proc=subprocess.Popen(['7z','x','-so',str(p)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);root=None
for ev,e in E.iterparse(proc.stdout,events=('start','end')):
 if root is None and ev=='start':root=e
 if ev!='end' or not e.tag.endswith('}page'):continue
 if e.findtext('{*}ns')=='0':
  scanned+=1;title=e.findtext('{*}title') or '';v=e.find('{*}revision');raw=v.findtext('{*}text') or '';matches=sorted({cats[y.strip().replace('_',' ').casefold()] for y in re.findall(r'\[\[\s*Category\s*:\s*([^\]|]+)',raw,re.I) if y.strip().replace('_',' ').casefold() in cats})
  if matches and title.replace('_',' ').casefold() not in oldnames:
   result.append({'title':title,'revision_id':v.findtext('{*}id'),'timestamp':v.findtext('{*}timestamp'),'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'matched_explicit_categories':matches,'redirect':raw.lstrip().casefold().startswith('#redirect')})
 root.clear()
assert proc.wait()==0
out={'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','old_census_sha256':hashlib.sha256(Path('evaluation/swtor-expansion-category-census.json').read_bytes()).hexdigest(),'scope':'Explicit category tags from 19 categories in the older snapshot; main namespace only; may omit template-generated categories, aliases, and other relevant topics. New relative to exact old census title only; no rights or content completeness determined.','pages_scanned':scanned,'old_category_names':len(cats),'new_title_candidates':len(result),'items':sorted(result,key=lambda v:v['title'])}
Path('/tmp/holovec-swtor-expansion-new-review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('Scanned',scanned,'new title candidates',len(result));print([(x['title'],x['redirect']) for x in result])
