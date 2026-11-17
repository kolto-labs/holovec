"""Reconcile KOTOR comic news insert leads with current text-layer URLs.

Source bibliography is secondary and does not establish reuse rights or verify
physical pages. This program copies no original news insert text.
"""
import collections,hashlib,json
from pathlib import Path
from urllib.parse import quote,unquote,urlparse
import pyarrow.parquet as pq
items=[
('holofeed-prime','The Taris Holofeed: Prime Edition',0),
('admirals-list-jimas','The Admiral\'s List: Jimas Veltraa Memorial Edition',13),
('adjudicator-outer-rim','The Adjudicator Special Report: The Outer Rim',14),
('holofeed-siege','The Taris Holofeed: Siege Edition',15),
('admirals-list-serroco','The Admiral\'s List: Remember Serroco! Edition',16),
('adascorp-chief-executive','Adascorp Fiscal Period Financial Report and Outlook: Message from the Chief Executive',17),
('holofeed-invasion','The Taris Holofeed: Invasion Edition',18),
('adascorp-black-harvest','Adascorp Fiscal Period Financial Report and Outlook: Field Report: Project Black Harvest',19),
('adjudicator-tools','The Adjudicator Special Report: Tools of the Trade',20),
('holofeed-proclamation','The Taris Holofeed Special Proclamation',21),
('admirals-list-karath','The Admiral\'s List: Karath Home Safely',22),
('adjudicator-colonies','The Adjudicator Special Report: The Colonies',23),
('ministry-daily-brief','Galactic Republic Defense Ministry Daily Brief KD0092',24)]
def norm(url):
 if not isinstance(url,str):return ''
 p=urlparse(url);return unquote(p.path).replace('_',' ').casefold().rstrip('/') if p.hostname in ('starwars.fandom.com','www.starwars.fandom.com') else ''
target={norm('https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe='/')):ident for ident,title,n in items};assert len(target)==len(items)
manifest=json.loads(Path('manifest.json').read_text());matches=collections.defaultdict(list);hashes={}
for e in manifest['input_files']:
 name=e['path'];p=Path(name)
 if not name.startswith('data/') or p.suffix not in ('.jsonl','.parquet'):continue
 with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 if digest!=e['sha256']:raise ValueError('manifest mismatch '+name)
 hashes[name]=digest
 if p.suffix=='.jsonl':
  def rows():
   with p.open(encoding='utf-8') as f:
    for line in f:
     if line.strip():yield json.loads(line)
 else:
  def rows():
   pf=pq.ParquetFile(p);cols=[c for c in ('url','source_url','revision_id','revision','text_sha256','sha256') if c in pf.schema_arrow.names]
   for batch in pf.iter_batches(columns=cols,batch_size=512):yield from batch.to_pylist()
 for row in rows():
  url=row.get('url') or row.get('source_url');k=norm(url)
  if k in target:matches[target[k]].append({'layer':name,'url':url,'revision_id':row.get('revision_id') or row.get('revision'),'text_sha256':row.get('text_sha256') or row.get('sha256')})
out=[]
for ident,title,n in items:
 out.append({'id':ident,'title':title,'parent_issue_work_id':f'kotor-2006-{n:03d}','parent_issue_number':n,'bibliographic_source':'https://starwars.fandom.com/wiki/Star_Wars:_Knights_of_the_Old_Republic_(comic_series)','secondary_article_url':'https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe='/'),'matching_text_records':matches[ident],'primary_content':'not_acquired','permission_to_redistribute_primary':'not_established','embedded':False,'qualification':'Issue and title from secondary bibliography; original page, edition and reprint fidelity not checked. A matching text record is secondary and does not establish coverage of the insert.'})
result={'description':'Thirteen issue-linked KOTOR news insert leads. Title-and-issue associations come from a secondary series bibliography; primary pages are not acquired and rights are not established. URL matching does not resolve redirects or establish coverage.','sources':['https://starwars.fandom.com/wiki/Star_Wars:_Knights_of_the_Old_Republic_(comic_series)','https://www.jedipedia.net/wiki/Jedipedia:Projekte/Knights_of_the_Old_Republic/KotOR-Comic_Liste'],'text_layer_sha256':hashes,'items':out}
Path('catalog/works/kotor-comic-news-inventory.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n');print('Insert leads',len(out),'with exact secondary URL',sum(bool(x['matching_text_records']) for x in out))
