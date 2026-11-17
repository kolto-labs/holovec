"""Link three wiki-indexed companion adventures to existing corpus records.

A secondary category identifies leads, not a complete sourcebook contents list.
The primary book and its text have not been independently inspected or cleared.
"""
import hashlib,json
from pathlib import Path
names=['Evil Arisen','Ruins of Kabus-Dabeh','The Muza Disappearances'];data=Path('data/wookieepedia-broad-references.jsonl');cat=Path('evaluation/old-republic-category-census.json');db=json.loads(cat.read_text());rows=[]
found={}
with data.open(encoding='utf-8') as f:
 for number,line in enumerate(f):
  x=json.loads(line)
  if x.get('title') in names:
   if x['title'] in found:raise ValueError('Duplicate title')
   found[x['title']]={'source_layer':str(data),'source_row':number,'source_url':x['url'],'text_sha256':hashlib.sha256(x['text'].encode()).hexdigest(),'source_document_sha256':x['sha256']}
for title in names:
 matches=[x for x in db['items'] if x['title']==title and 'Tales of the Jedi Companion adventures' in x['matched_categories']]
 if len(matches)!=1 or title not in found:raise ValueError('Missing match: '+title)
 rows.append({'title':title,'work_type':'adventure or adventure seed (secondary classification)','parent_work_id':'totj-companion-1996','primary_content_acquired':False,'primary_rights':'not_established','secondary_category_evidence':matches[0]['url'],'secondary_context':found[title],'secondary_content_caveat':'Existing broad wiki snapshot is unembedded and its unmarked third-party excerpts have not been cleared.'})
out={'scope':'Three adventure leads in the pinned wiki category; not a complete contents census. Attribution, title, type, branches and placement need verification against the original book.','parent_work':'Tales of the Jedi Companion (1996)','source_category_audit':str(cat),'source_category_audit_sha256':hashlib.sha256(cat.read_bytes()).hexdigest(),'source_layer_sha256':hashlib.sha256(data.read_bytes()).hexdigest(),'items':rows}
Path('catalog/works/totj-companion-adventure-inventory.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print('Mapped',len(rows),'adventures to existing secondary records')
