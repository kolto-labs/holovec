"""Publish manually inspected contributor summaries from locally prepared candidates."""
import hashlib,json,sys
from pathlib import Path
from urllib.parse import quote
APPROVED={
 "The Old Republic: Smuggler's Vanguard":('15738581','587366ddeebabccfcd2cee7a7963134d23c949c1bc8b753b5dfa49166a7844e8'),
 'The Last Battle of Colonel Jace Malcom':('15295515','cc88755cab00daa610b21036fad680f4a18f1d7f4521e7a567ee656a387fdcfd'),
 'Bedtime on Concordia':('15593392','9e78784a7514bef8a0e0bbb1a8d713e4a8f9629c104108de99c06397578e35b3'),
 "A Mother's Hope":('15507999','c2033b7b9c20de8ff688988dece66552b9a0ea47c53b7021b68ac39fa0b3d595'),
 'Trading Scars':('15322873','b66aba3eacb262e0859ec67c0dcf391146d1b9b69d4ae8387b2efc94ce56906e'),
 'Seeing Red':('15593225','f01ae39574fbf9e51da976c4aef337f7106fd733963cb76f1564383d2bc91bb8'),
}
source=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(revision,digest) in sorted(APPROVED.items()):
 x=source[title];text=x['text']
 if x['revision_id']!=revision or x['text_sha256']!=digest or hashlib.sha256(text.encode()).hexdigest()!=digest or x['reasons']:raise ValueError('Candidate changed or failed screening: '+title)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+revision,'revision_id':revision,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':x['raw_wikitext_sha256'],'text_sha256':digest,'text':text,'work_type':'short-story','evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','review_status':'plot section inspected; other sections not cleared','continuity':'Legends','embedded':False})
Path('data/wookieepedia-swtor-story-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('published reviewed summaries:',len(rows))
