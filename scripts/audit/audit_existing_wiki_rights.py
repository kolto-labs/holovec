"""Metadata-only audit: flagged wiki titles in current shards and legacy inputs.

URL matches are signals, not proof that other titles or sections are cleared.
No models or inference are used.
"""
import collections,json,re,urllib.parse
from pathlib import Path
import pyarrow.parquet as pq
root=Path(__file__).resolve().parents[2]
flags=json.loads((root/'evaluation/wiki-rights-flags.json').read_text())['flagged_records']
def key(u):return urllib.parse.unquote(u or '').replace(' ','_').rstrip('/').casefold()
targets={key(x['url']) for x in flags if x.get('url')}
pattern=re.compile(r"(?im)^\s*(?:#{1,6}\s*)?(?:publisher(?:'s|s’) summary|opening crawl|official description|publisher(?:'s|s’) description|back cover(?: (?:description|summary|blurb))?)\s*$")
out={'scope':'Current local Parquet files; metadata-only URL matching and explicit heading detection. Neither scan identifies unmarked third-party excerpts or establishes rights. Earlier published repository revisions are not removed.','flagged_unique_urls':len(targets),'vector_shards':{},'legacy_wiki_layers':{}}
for p in sorted((root/'vectors').glob('*.parquet')):
 matches=collections.Counter()
 for batch in pq.ParquetFile(p).iter_batches(columns=['url']):
  for x in batch.to_pylist():
   if key(x.get('url')) in targets:matches[key(x['url'])]+=1
 out['vector_shards'][p.name]={'flagged_url_passages':sum(matches.values()),'flagged_unique_urls':len(matches)}
for p in sorted((root/'data').glob('wookieepedia*.parquet')):
 count=0;matches=[]
 for batch in pq.ParquetFile(p).iter_batches(columns=['title','url','text']):
  for x in batch.to_pylist():
   count+=1
   if pattern.search(x.get('text') or ''):matches.append({'title':x['title'],'url':x['url']})
 out['legacy_wiki_layers'][p.name]={'records':count,'matched_headings':matches}
out['totals']={'vector_shards':len(out['vector_shards']),'flagged_url_vector_passages':sum(x['flagged_url_passages'] for x in out['vector_shards'].values()),'legacy_records':sum(x['records'] for x in out['legacy_wiki_layers'].values()),'legacy_heading_matches':sum(len(x['matched_headings']) for x in out['legacy_wiki_layers'].values())}
(root/'evaluation/existing-wiki-rights-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(out['totals']))
