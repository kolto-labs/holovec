"""Cross-reference official story leads with existing exact-title secondary records.

Records are discovery links, not proof of primary-story coverage or rights.
"""
import hashlib,json
from pathlib import Path
import pyarrow.parquet as pq

manifest=json.loads(Path('manifest.json').read_text());registered={v['path']:v for v in manifest['input_files']}
def verify(p):
 b=p.read_bytes(); e=registered.get(str(p)); digest=hashlib.sha256(b).hexdigest()
 if not e or e['sha256']!=digest or e['size']!=len(b):raise ValueError('unregistered or changed input: '+str(p))
 return digest
sources=Path('catalog/sources/source-inventory.json');review=Path('evaluation/swtor-story-plot-review.json');source_hash=verify(sources);review_hash=verify(review)
leads=[v for v in json.loads(sources.read_text()) if v['id'].startswith('swtor-short-story-')];
if len(leads)!=23:raise ValueError('official lead set changed')
aliases={
 'swtor-short-story-brothers':('Brothers (short story)','https://starwars.fandom.com/wiki/Category:Star_Wars:_The_Old_Republic_short_stories'),
 'swtor-short-story-snare':('Snare (short story)','https://starwars.fandom.com/wiki/Snare_(short_story)'),
 'swtor-short-story-sixth-line-one':('The Sixth Line','https://www.swtor.com/info/news/blog?page=3'),
 'swtor-short-story-sixth-line-two':('The Sixth Line','https://www.swtor.com/info/news/blog?page=3'),
}
items=[]
for v in leads:
 if ': ' not in v['name']:raise ValueError('unknown title format')
 title=v['name'].split(': ',1)[1];items.append({'source_id':v['id'],'title':title,'official_url':v['url'],'primary_story_acquired':False,'primary_redistribution_rights':'not_established','exact_title_secondary_matches':[],'reviewed_alias_secondary_matches':[],'earlier_plot_review':[]})
source_by_id={v['id']:v for v in leads}
for item in items:
 item['related_secondary_context']=source_by_id[item['source_id']].get('related_secondary_context',[])
lookup={v['title'].casefold():v for v in items};alias_lookup={}
for v in items:
 if v['source_id'] in aliases:
  target,evidence=aliases[v['source_id']];alias_lookup.setdefault(target.casefold(),[]).append((v,evidence))
if len(lookup)!=len(items):raise ValueError('duplicate titles')
for v in json.loads(review.read_text())['items']:
 k=v['title'].casefold()
 recipients=([lookup[k]] if k in lookup else [])+[x[0] for x in alias_lookup.get(k,[])]
 for target in recipients:target['earlier_plot_review'].append({'title':v['title'],'status':v['status'],'revision_id':v.get('revision_id')})
scanned=[]
for p in sorted(Path('data').iterdir()):
 if p.suffix not in ('.jsonl','.parquet'):continue
 scanned.append({'file':str(p),'sha256':verify(p)})
 if p.suffix=='.jsonl':
  with p.open(encoding='utf8') as fp:docs=[json.loads(s) for s in fp if s.strip()]
 else:docs=pq.read_table(p).to_pylist()
 for d in docs:
  title=(d.get('title') or '').strip();section=(d.get('section') or '').strip();keys={title.casefold(),section.casefold()}
  if title.endswith(' — lead'):keys.add(title[:-len(' — lead')].casefold())
  for key in keys & lookup.keys():
   text=d.get('text') or ''
   lookup[key]['exact_title_secondary_matches'].append({'file':str(p),'title':title,'section':section or None,'url':d.get('url') or d.get('source_url'),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'license':d.get('license') or d.get('license_spdx'),'embedded':d.get('embedded')})
  for key in keys & alias_lookup.keys():
   for target,evidence in alias_lookup[key]:
    target['reviewed_alias_secondary_matches'].append({'file':str(p),'title':title,'section':section or None,'url':d.get('url') or d.get('source_url'),'text_sha256':hashlib.sha256((d.get('text') or '').encode()).hexdigest(),'license':d.get('license') or d.get('license_spdx'),'alias_evidence_url':evidence,'scope':'Shared story page; does not prove installment-specific narrative coverage.'})
items.sort(key=lambda x:x['source_id']);report={'scope':'23 official short-story leads from source inventory; exact title or section matches only, case-insensitive. Selected aliases are explicitly linked to supporting evidence; other aliases, redirects and indirect mentions are not resolved. Matches are secondary records and do not establish full coverage or content rights.','source_inventory_sha256':source_hash,'earlier_review_sha256':review_hash,'scanned_data_layers':scanned,'stories':len(items),'stories_with_exact_title_match':sum(bool(v['exact_title_secondary_matches']) for v in items),'stories_without_exact_title_match':sum(not v['exact_title_secondary_matches'] for v in items),'stories_with_reviewed_alias_matches':sum(bool(v['reviewed_alias_secondary_matches']) for v in items),'stories_without_exact_or_alias_match':sum(not v['exact_title_secondary_matches'] and not v['reviewed_alias_secondary_matches'] for v in items),'items':items}
Path('evaluation/swtor-official-short-story-reconciliation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print('stories',report['stories'],'matched',report['stories_with_exact_title_match'],'unmatched',report['stories_without_exact_title_match'],'alias matches',report['stories_with_reviewed_alias_matches'],'still unmatched',report['stories_without_exact_or_alias_match'],'layers',len(scanned))
