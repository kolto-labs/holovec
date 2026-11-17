"""Publish a quote-omitted secondary plot summary from a pinned local wiki scan.

Usage: PYTHONPATH=<dependencies> python publish_swtor_short_story_quote_omitted.py LOCAL_REVIEW_JSON
The screen cannot clear unmarked excerpts or provide the primary story.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
TITLE='Last Road to Khar Shian';REV='15619246';RAW='0f52b42941cd331ec5a48c4794f83e383790ba7cb833569e5f182dcaf5f11444';ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
x=json.loads(Path(sys.argv[1]).read_text())[TITLE];raw=x['raw_section']
if x['revision_id']!=REV or sha(raw)!=RAW or x['raw_wikitext_sha256']!=RAW or x['reasons']!=['quotes_or_dialogue']:raise ValueError('source or screen changed')
c=mwparserfromhell.parse(raw)
for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
for t in list(c.filter_tags(recursive=True)):
 if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
  try:c.remove(t,recursive=True)
  except ValueError:pass
for link in list(c.filter_wikilinks(recursive=True)):
 if str(link.title).strip().casefold().startswith(('file:','image:')):
  try:c.remove(link,recursive=True)
  except ValueError:pass
clean=c.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',clean)
if n!=1 or not text or sha(text)!='8a54f08037895a6db0258d2a466c4e1f337b260f03293f1e14ec6dd1171df626' or re.search(r'["“”]',text) or 'thumb|' in text:raise ValueError('quote screen changed')
url='https://starwars.fandom.com/wiki/Last_Road_to_Khar_Shian'
row={'title':TITLE,'url':url,'source_revision_url':url+'?oldid='+REV,'revision_id':REV,'timestamp':x['timestamp'],'source_archive_sha256':ARCH,'section':'Plot summary','section_wikitext_sha256':RAW,'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'text':text,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images and one quotation-marked phrase removed. The source scan checks for overlap with publisher sections at ten words.','coverage':'Partial secondary story summary; not the primary story. Unmarked excerpts are not cleared.','embedded':False}
Path('data/wookieepedia-swtor-last-road-summary.jsonl').write_text(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
print('prepared one quote-omitted plot section; output',sha(text))
