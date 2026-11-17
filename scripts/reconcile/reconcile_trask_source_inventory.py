"""Compare a historical local Trask inventory to two preserved catalogs.

Usage: python reconcile_trask_source_inventory.py HISTORICAL_INVENTORY_MARKDOWN
The historical source is untracked, so its hash pins the local evidence rather
than asserting that the inventory reflects an upstream commit.
"""
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]);b=p.read_bytes();s=b.decode('utf8').split('## All web/GitHub source entries\n',1)[1].split('\n## Reconciliation',1)[0];old=[]
for line in s.splitlines():
 parts=[x.strip() for x in line.strip().strip('|').split('|')]
 if len(parts)==3 and parts[2].startswith('http'):old.append({'id':parts[0],'name':parts[1],'url':parts[2]})
assert len(old)==81 and len({x['id'] for x in old})==81
local=json.load(open('catalog/sources/source-catalog.json'));upstream=json.load(open('catalog/sources/upstream-source-catalog.json'))['entries'];combined={}
for v in local+upstream:
 url=v.get('url') or v.get('homeUrl');previous=combined.setdefault(v['id'],url)
 if previous!=url:raise ValueError('catalog URL conflict '+v['id'])
oldids={v['id'] for v in old};missing=[v for v in old if v['id'] not in combined];changed=[{'id':v['id'],'historical_url':v['url'],'catalog_url':combined[v['id']]} for v in old if v['id'] in combined and v['url']!=combined[v['id']]];new=[{'id':k,'url':v} for k,v in sorted(combined.items()) if k not in oldids]
report={'scope':'Exact ID and URL comparison of an untracked local 2026-10-14 source inventory with the HoloVec local and upstream catalogs. These are historical, differing snapshots; membership does not establish source coverage, current availability or reuse rights.','historical_inventory_sha256':hashlib.sha256(b).hexdigest(),'historical_web_github_entries':len(old),'local_catalog_sha256':hashlib.sha256(Path('catalog/sources/source-catalog.json').read_bytes()).hexdigest(),'upstream_catalog_sha256':hashlib.sha256(Path('catalog/sources/upstream-source-catalog.json').read_bytes()).hexdigest(),'combined_catalog_unique_ids':len(combined),'historical_ids_missing_from_both':missing,'matching_id_changed_urls':changed,'combined_ids_not_in_historical_web_export':new}
Path('evaluation/trask-historical-source-reconciliation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('historical',len(old),'combined',len(combined),'missing',len(missing),'URL changes',len(changed),'new',len(new))
