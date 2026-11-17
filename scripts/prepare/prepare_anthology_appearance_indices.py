"""Prepare pinned local-only appearance markup for five anthology stories."""
import json,re,hashlib,sys
from pathlib import Path
src=Path(sys.argv[1]);dest=Path(sys.argv[2]);assert not dest.exists()
x=json.loads(src.read_text());assert x['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';snapshot_ids={v['work_id'] for v in json.load(open('evaluation/anthology-appearance-extraction.json'))['items']};assert len(snapshot_ids)==5;stories={v['title']:v['work_id'] for v in json.load(open('catalog/works/comics-anthology-story-inventory.json'))['stories'] if v['work_id'] in snapshot_ids};assert set(stories.values())==snapshot_ids;found={}
for title,work in stories.items():
 v=x['records'][title];raw=v['raw_wikitext'];assert hashlib.sha256(raw.encode()).hexdigest()==v['raw_wikitext_sha256'];hs=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));i,h=next((i,h) for i,h in enumerate(hs) if h.group(2).strip().casefold()=='appearances');end=next((z.start() for z in hs[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));section=raw[h.end():end].strip();found[title]={'work_id':work,'title':title,'revision_id':v['revision_id'],'timestamp':v['timestamp'],'sections':[{'raw_wikitext':section,'sha256':hashlib.sha256(section.encode()).hexdigest()}]}
assert len(found)==5
out={'source_archive_sha256':x['archive_sha256'],'target_count':5,'not_found':[],'records':found};dest.write_text(json.dumps(out,ensure_ascii=False));dest.chmod(0o600);print('Prepared',len(found),'local-only sections')
