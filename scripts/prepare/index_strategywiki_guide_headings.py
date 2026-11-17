"""Index raw headings from pinned StrategyWiki revisions; no page body is published.

API documentation: https://www.mediawiki.org/wiki/API:Revisions
"""
import json,hashlib,re,requests,sys
from pathlib import Path
import mwparserfromhell
source=Path('data/strategywiki.jsonl');pages=[json.loads(l) for l in source.read_text().splitlines() if l.strip()];assert len(pages)==302
byrev={str(p['revision']):p for p in pages};assert len(byrev)==len(pages)
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';found={};errors=[]
for start in range(0,len(pages),40):
 group=pages[start:start+40];ids='|'.join(str(p['revision']) for p in group)
 try:
  r=s.get('https://strategywiki.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main','revids':ids},timeout=60);r.raise_for_status();x=r.json();assert 'query' in x
  for v in x['query']['pages']:
   for rev in v.get('revisions',[]):
    rid=str(rev['revid']);p=byrev[rid];raw=rev['slots']['main']['content'];parsed=mwparserfromhell.parse(raw);plain=parsed.strip_code(normalize=True,collapse=True).strip();digest=hashlib.sha256(plain.encode()).hexdigest()
    if digest!=p['sha256']:errors.append({'revision_id':rid,'title':p['title'],'error':'archive_text_hash_mismatch'});continue
    heads=[]
    for h in parsed.filter_headings(recursive=False):
     label=mwparserfromhell.parse(str(h.title)).strip_code(normalize=True,collapse=True).strip()
     if label:heads.append({'level':h.level,'label':label})
    found[rid]={'title':p['title'],'url':p['url'],'page_id':p['page_id'],'revision_id':rid,'timestamp':p['timestamp'],'source_record_sha256':p['sha256'],'raw_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'headings':heads}
  print('Batch',start//40+1,'retrieved',len(found),'errors',len(errors),flush=True)
 except (requests.RequestException,ValueError,KeyError,AssertionError) as e:
  errors.extend({'revision_id':str(p['revision']),'title':p['title'],'error':type(e).__name__} for p in group);print('Batch',start//40+1,'failed',type(e).__name__,flush=True)
missing=[{'title':p['title'],'revision_id':str(p['revision'])} for p in pages if str(p['revision']) not in found]
report={'description':'Raw wikitext headings from the 302 revision-pinned StrategyWiki game-guide records, verified against the archived stripped-text hashes. Heading labels are a navigational aid and may include locations, mechanics or incidental material, not a complete quest list. Template-rendered headings are not included; quest choices, transclusions, later revisions and rights in game excerpts are not established. No page body is copied.','license':'StrategyWiki contributors: CC BY-SA 4.0; older contributions may be CC BY-SA 3.0; game excerpts may have separate rights','attribution':'StrategyWiki contributors; follow each page revision history','source_dataset':'data/strategywiki.jsonl','source_dataset_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'expected_pages':len(pages),'matched_pages':len(found),'heading_count':sum(len(x['headings']) for x in found.values()),'pages':sorted(found.values(),key=lambda x:x['title']),'missing_pages':missing,'errors':errors}
Path('evaluation/strategywiki-guide-heading-index.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('TOTAL',len(found),'pages',report['heading_count'],'headings',len(missing),'missing',flush=True)
