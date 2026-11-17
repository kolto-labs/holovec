"""Publish manually reviewed wiki contributor plot summaries from pinned candidates.

Quotation markers in these four records were manually checked as quoted names,
ordinary phrasing, or ref attributes; no quote/dialogue template was present.
This is not a clearance of their full pages or primary novels.
"""
import hashlib,json,sys
from pathlib import Path
from urllib.parse import quote
APPROVED={
 'Darth Bane: Path of Destruction':('15826666','03482ab9b6ce2a722abe6729acf761ece5f7a99be533fb4073b1c5505ea6c01a','quoted character name'),
 'The Old Republic: Fatal Alliance':('15762153','62323973c886d734b1c1d1a8f8008477719ff5576ebd0a397e7c1c40c3eddcef','quotation marks are reference attributes removed during extraction'),
 'The Old Republic: Annihilation':('15733179','1e7074cefb7ee54b6d7ab74cace318d69cc1adad17cfa2b18d3dad80d59e2a1d','quoted ordinary words'),
 'Dawn of the Jedi: Into the Void':('15683141','0d722d45295c856c32a00efc489132544b6e4819fb2fbd518616a2222c832dcd','quoted name of a rite'),
}
candidates=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(revision,digest,marker) in sorted(APPROVED.items()):
 x=candidates[title];text=x['text'];url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 if x['revision_id']!=revision or x['text_sha256']!=digest or hashlib.sha256(text.encode()).hexdigest()!=digest or x['reasons']!=['quotes_or_dialogue']:raise ValueError('reviewed candidate changed: '+title)
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':x['raw_wikitext_sha256'],'text_sha256':digest,'text':text,'work_type':'novel','evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','review_status':'manually inspected plot section; full article remains held','marker_review':marker,'continuity':'Legends','embedded':False})
Path('data/wookieepedia-reviewed-novel-plots.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))
print('Reviewed novel summaries:',len(rows))
