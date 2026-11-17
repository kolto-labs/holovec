"""Create attributed, quote-omitted plot summaries for the two KOTOR games.

Input is local-only raw markup from prepare_kotor_game_review.py. Wiki images,
references, templates and quotation-marked phrases are removed. The source itself
is one specific player-choice interpretation, not complete game-branch coverage.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={
 'Star Wars: Knights of the Old Republic':('15753482','7c5f262226222dd631a0b3cddaf6bb7d075a761b8ec05694b34ef2ba4d208572',6,'male light-side path, specified planet order'),
 'Star Wars: Knights of the Old Republic II: The Sith Lords':('15816087','afb83d2f02864603a3ef37a7ee6188e63b9731083e883de2a0b5f16968ec6524',5,'female light-side path; source contains a Plot placeholder'),
}
OUTPUT_PINS={'Star Wars: Knights of the Old Republic':'3a0ff0b79d106d9cb8ae1b933c4e327c06e37f097d8f0bd0f3641dc3af987eb2','Star Wars: Knights of the Old Republic II: The Sith Lords':'86df91aa32d1e161689e15317cbe63902b7fdbf63238bf7713374327b65051ed'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
data=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(rev,rawhash,expected,choice) in sorted(PINS.items()):
 x=data[title];raw=x['raw_section'];code=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=rawhash or x['raw_wikitext_sha256']!=rawhash or x['reasons']!=['quotes_or_dialogue']:raise ValueError('Source or screening changed: '+title)
 if any(str(t.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech') for t in code.filter_templates(recursive=True)):raise ValueError('quote template: '+title)
 for tag in list(code.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(tag,recursive=True)
   except ValueError:pass
 for link in list(code.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:')):
   try:code.remove(link,recursive=True)
   except ValueError:pass
 for t in list(code.filter_templates(recursive=False)):
  try:code.remove(t,recursive=True)
  except ValueError:pass
 text=code.strip_code(normalize=True,collapse=True).strip();cleanhash=sha(text)
 result,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 if sha(result)!=OUTPUT_PINS[title] or n!=expected or re.search(r'["“”]',result) or 'thumb|' in result:raise ValueError('Unexpected quote or image remnants: '+title)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':rawhash,'cleaned_text_sha256':cleanhash,'text_sha256':sha(result),'text':result,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','source_choice_assumption':choice,'extraction':'References, templates and image markup removed; all quotation-marked phrases replaced with [quoted words omitted].','omitted_quote_count':n,'review_status':'limited markup screening; full page and primary game text remain held','embedded':False})
Path('data/wookieepedia-kotor-game-plots.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows))
print('Created',len(rows),'secondary game plot summaries')
