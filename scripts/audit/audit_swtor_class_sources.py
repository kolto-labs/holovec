"""Metadata-only class-story source and existing-vector quotation-marker audit.

Does not infer, clear rights or decide canonical player choices. Quote markers
can denote names, short terms or protected quotations; manual review is required.
"""
import collections,hashlib,json,re
from pathlib import Path
import pyarrow.parquet as pq
root=Path(__file__).resolve().parents[2]
CLASSES={'class-jedi-knight':'Hero of Tython','class-jedi-consular':"The Barsen'thor",'class-trooper':'Meteor (Havoc Squad)','class-smuggler':'Voidhound','class-sith-warrior':"Empire's Wrath",'class-sith-inquisitor':'Darth Nox','class-bounty-hunter':'Hunter (individual)','class-imperial-agent':'Cipher Nine'}
source=root/'data/wookieepedia-legends.parquet';records={r['title']:r for r in pq.read_table(source,columns=['title','url','text','sha256']).to_pylist() if r['title'] in CLASSES.values()}
holds={r['title']:r for r in json.loads((root/'evaluation/wiki-class-rights-holds.json').read_text())['articles']}
assert set(records)|set(holds)==set(CLASSES.values())
stats=collections.defaultdict(collections.Counter)
for f in sorted((root/'vectors').glob('*.parquet')):
 for batch in pq.ParquetFile(f).iter_batches(columns=['title','text']):
  for x in batch.to_pylist():
   if x['title'] in records:
    stats[x['title']]['passages']+=1;stats[x['title']]['quote_marker_passages']+=bool(re.search(r'["“”]',x['text'] or ''))
items=[]
for id,title in CLASSES.items():
 r=records.get(title) or holds[title];text=r.get('text');assert text is None or hashlib.sha256(text.encode()).hexdigest()==r['sha256'];s=stats[title]
 items.append({'class_id':id,'article_title':title,'url':r['url'],'dataset':'data/wookieepedia-legends.parquet','text_sha256':r['sha256'],'article_revision_id':None,'held_prior_vector_passages':25 if title=='Darth Nox' else 27 if title=='Meteor (Havoc Squad)' else 0,'text_characters':len(text) if text is not None else None,'quotation_marker_characters':len(re.findall(r'["“”]',text)) if text is not None else None,'vector_passages':s['passages'],'vector_passages_with_quote_markers':s['quote_marker_passages'],'status':'held_from_current_release' if title in holds else 'source_and_vectors_public_rights_review_required','scope':'Secondary player-character narrative; player choice, faction, alignment, mission and update coverage is not established.'})
report={'description':'Metadata-only audit of eight class-character articles and current vector passages. Marker counts are review signals, not evidence of a quotation or rights conclusion. Source may contain unmarked excerpts; two full articles and their vector passages are held in current files, but remain in public history.','upstream_repository':'rafa-rrayes/wookieelm-corpus','upstream_revision':'5d19bba512fa8c65b225c1819d7971db316b871c','items':items,'totals':{'class_articles':len(items),'vector_passages':sum(x['vector_passages'] for x in items),'vector_passages_with_quote_markers':sum(x['vector_passages_with_quote_markers'] for x in items)}}
(root/'evaluation/swtor-class-source-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report['totals']))
