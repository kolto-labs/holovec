"""Publish five pinned contributor plot sections after quotation-marker review.

Raw candidates remain local. Markers were reviewed as short in-world names or
phrases; quote templates and image markup are rejected. No primary comic text
is intentionally included and this does not establish full source clearance.
"""
import hashlib,json,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={
 'Knights of the Old Republic 9':('14755531','80089ec21529bca6d42f5b7e42d4fb8336b1a2354974f9601b29cda05ed22002','a67af839ca53c9556d78ba9312d36f81b273f6c836c55766118c520ac953ed49','kotor-2006-009'),
 'Knights of the Old Republic 11':('14755544','7c51f3209c2d952983e409d906a87b370c21bc15f37b956ef829d659e2ae86ce','ec8c92219f8417dda0545c20c286490489ba4066997e78896baab9a278bf925e','kotor-2006-011'),
 'Knights of the Old Republic 15':('14908736','2f9d7add9099128ee4597fde5926b8f85e90dec806b7fe8eb095f6d9b9dec598','ba64e710dcb37abc89e8fad6808d8a96e39206b83d8a4bcf47303ba6b85b94e4','kotor-2006-015'),
 'Knights of the Old Republic 16':('14809768','47b5654c3f067a4c4e18db7e50831142a8d4344a998d96dc5d10e3afb0dcf07d','a441d063a7ae47b52c516d0bddd15f1a8fcb4fff10d7861d80c8d5f661cdd4dd','kotor-2006-016'),
 'Knights of the Old Republic 17':('14755557','48d23391fbd8e1b8e366bd0a69128b6ad7d39f7d3e52a7070380ea0dccf8d1f1','f40fc9e4ca1a701875df5483aded78b25ccac8dfbb31c50a5d100ffbfd182c03','kotor-2006-017')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
data=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(rev,rawhash,texthash,work) in sorted(PINS.items()):
 x=data[title];raw=x['raw_section'];code=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=rawhash or x['raw_wikitext_sha256']!=rawhash or x['reasons']!=['quotes_or_dialogue']:raise ValueError('Source changed: '+title)
 if any(str(t.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech') for t in code.filter_templates(recursive=True)):raise ValueError('Quoted template: '+title)
 if any(str(l.title).strip().casefold().startswith(('file:','image:')) for l in code.filter_wikilinks(recursive=True)):raise ValueError('Image markup: '+title)
 for t in list(code.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(t,recursive=True)
   except ValueError:pass
 for t in list(code.filter_templates(recursive=False)):
  try:code.remove(t,recursive=True)
  except ValueError:pass
 text=code.strip_code(normalize=True,collapse=True).strip()
 if sha(text)!=texthash:raise ValueError('Reviewed text changed: '+title)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':rawhash,'text_sha256':texthash,'text':text,'inventory_work_id':work,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','review_status':'marker and plot prose inspected; full article and primary comic remain held','embedded':False})
Path('data/wookieepedia-reviewed-kotor-issue-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('Published',len(rows),'secondary plot sections')
