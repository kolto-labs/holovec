"""Extract two contributor-written sections from a pinned Wikipedia revision.

Reviews and explicit quotations are omitted. No model inference is performed.
"""
import hashlib,json,re,requests,mwparserfromhell
from pathlib import Path
rev=1384509833;api='https://en.wikipedia.org/w/api.php';s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
r=s.get(api,params={'action':'query','format':'json','formatversion':2,'prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main','revids':rev},timeout=30);r.raise_for_status();p=r.json()['query']['pages'][0];v=p['revisions'][0];raw=v['slots']['main']['content']
if p['title']!='Tales of the Jedi Companion' or hashlib.sha256(raw.encode()).hexdigest()!='5d4958324875a36cf2a804e46d82cc36b31cf10339c45232731cb3c8e67fc647':raise ValueError('unexpected revision')
intro=raw.split('{{Italic title}}',1)[1].split('==Contents==',1)[0];contents=raw.split('==Contents==',1)[1].split('==Publication history==',1)[0];out=[];url='https://en.wikipedia.org/wiki/Tales_of_the_Jedi_Companion'
for label,part in [('Introduction',intro),('Contents',contents)]:
 code=mwparserfromhell.parse(part)
 for tag in list(code.filter_tags(recursive=True)):
  if str(tag.tag).lower()=='ref':code.remove(tag,recursive=True)
 text=code.strip_code(normalize=True,collapse=True).strip();assert text and not re.search(r'["“”]',text)
 out.append({'title':'Tales of the Jedi Companion — '+label,'section':label,'url':url,'source_url':url,'source_revision_url':'https://en.wikipedia.org/w/index.php?oldid='+str(rev),'revision_id':rev,'timestamp':v['timestamp'],'page_wikitext_sha256':hashlib.sha256(raw.encode()).hexdigest(),'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'license':'CC BY-SA 4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/','attribution':'Wikipedia contributors; see linked revision history','continuity':'Legends','evidence_class':'secondary','extraction':'Introduction and contents description only; references, reviews and quoted passages excluded.','coverage':'Partial secondary description of a roleplaying sourcebook, not the original book or comic stories. Claims and unmarked third-party excerpts are not independently cleared.','embedded':False})
Path('data/wikipedia-totj-companion.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out));print('Included',len(out),'sections at revision',rev)
