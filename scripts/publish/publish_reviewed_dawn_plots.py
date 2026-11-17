"""Publish two manually inspected contributor plot sections from local review data.

Input contains raw wiki markup and must remain local. The War issue's publisher
quotation, references and embedded image are removed; the remaining prose is
not the primary comic. Exact source and output hashes guard the review.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
SOURCE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={
 'Dawn of the Jedi: The Prisoner of Bogan 1':('15416996','62bfaab16aae38d9bada00f380555853f0e310dca7e82609b4ecdb4770ed5912','dawn-prisoner-001'),
 'Dawn of the Jedi: Force War 1':('15383021','e89503073e91fc309f6571c440913319f5bb1d062619749bca8de1c2ae061810','dawn-force-war-001'),
}
OUTPUT_PINS={'Dawn of the Jedi: Force War 1':'ea20a35a53faf15da454c11fb112eb2f0da79672f528303f9d48a071ec4ba25e','Dawn of the Jedi: The Prisoner of Bogan 1':'96725ce6f5863d9413434f07bd829ca0c4b83f200a75e2a81c8ff51f9755493f'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
raw=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(rev,digest,work) in sorted(PINS.items()):
 x=raw[title];section=x['raw_section']
 if x['revision_id']!=rev or sha(section)!=digest or x['raw_wikitext_sha256']!=digest:raise ValueError('Source revision/section changed: '+title)
 code=mwparserfromhell.parse(section);removed=[]
 for template in list(code.filter_templates(recursive=False)):
  name=str(template.name).strip().casefold()
  if name=='quote':removed.append(str(template))
  code.remove(template,recursive=True)
 for tag in list(code.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(tag,recursive=True)
   except ValueError:pass
 for link in list(code.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:')):
   try:code.remove(link,recursive=True)
   except ValueError:pass
 text=code.strip_code(normalize=True,collapse=True).strip()
 if sha(text)!=OUTPUT_PINS[title] or (title.endswith('Force War 1') and len(removed)!=1) or (not title.endswith('Force War 1') and removed):raise ValueError('Unexpected source markup: '+title)
 # Guard against accidentally retaining the removed publisher blurb.
 def words(s):return re.findall(r'\w+',s.casefold())
 a=words(text);b=words(' '.join(removed));shingles={tuple(a[i:i+10]) for i in range(max(0,len(a)-9))}
 if any(tuple(b[i:i+10]) in shingles for i in range(max(0,len(b)-9))):raise ValueError('Overlap with removed quote: '+title)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':SOURCE,'section':'Plot summary','raw_wikitext_sha256':digest,'text_sha256':sha(text),'text':text,'inventory_work_id':work,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','review_status':'plot prose manually inspected; full article and comic remain held','extraction':'Removed wiki references, templates and embedded image markup; publisher quotation removed where present. Quotation marks in Prisoner of Bogan denote short in-world terms.','embedded':False})
Path('data/wookieepedia-reviewed-dawn-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('Published',len(rows),'secondary plot sections')
