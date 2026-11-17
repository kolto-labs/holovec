"""Extract webcomic-act-to-entity metadata from pinned Wookieepedia App sections.

Usage: PYTHONPATH=<dependencies> python publish_comic_appearance_metadata.py LOCAL_RAW_JSON
Only linked names and uninterpreted marker names are retained, not comic prose.
Source lists are editorial secondary data and can be incomplete or inaccurate.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'threat-1': ('14747654', '6e6057ba319f0e52bfca2852c9b2fe610a0c17ebc5c6d95eeff1f10b40186f4a'), 'threat-2': ('14747655', '6332d1babca01e5596522805b51bd5f85365dde6d2f80a1f67cc55a270d6cd1c'), 'threat-3': ('14747656', '987416710d331bb1480f153fd46a498f665ab85534e5a9e2a5a8524d1700707b')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
x=json.loads(Path(sys.argv[1]).read_text());
if x['source_archive_sha256']!=ARCH or x['target_count']!=3:raise ValueError('source mismatch')
rows=[];audit=[]
for rec in sorted(x['records'].values(),key=lambda r:r['work_id']):
 work=rec['work_id'];sections=rec['sections'];url='https://starwars.fandom.com/wiki/'+quote(rec['title'].replace(' ','_'),safe=':/()')
 if not sections:
  audit.append({'work_id':work,'title':rec['title'],'revision_id':rec['revision_id'],'status':'no_appearances_heading'});continue
 if len(sections)!=1 or work not in PINS:raise ValueError('unexpected section '+work)
 rev,digest=PINS[work];section=sections[0]['raw_wikitext']
 if rec['revision_id']!=rev or sha(section)!=digest or sections[0]['sha256']!=digest:raise ValueError('section changed '+work)
 c=mwparserfromhell.parse(section);apps=[t for t in c.filter_templates(recursive=False) if str(t.name).strip().casefold()=='app']
 if len(apps)!=1:raise ValueError('unexpected App template '+work)
 links=[];unlinked=0
 for param in apps[0].params:
  category=str(param.name).strip();ancestors={}
  for line in str(param.value).splitlines():
   m=re.match(r'^\s*(\*+)\s*(.*)$',line)
   if not m:continue
   depth=len(m.group(1));code=mwparserfromhell.parse(m.group(2))
   for tag in list(code.filter_tags(recursive=True)):
    if str(tag.tag).casefold() in ('ref','references'):
     try:code.remove(tag,recursive=True)
     except ValueError:pass
   wikilinks=code.filter_wikilinks(recursive=True)
   if not wikilinks:
    if code.strip_code(normalize=True,collapse=True).strip():unlinked+=1
    continue
   markers=sorted({str(t.name).strip() for t in code.filter_templates(recursive=True)})
   for link in wikilinks:
    target=str(link.title).strip();label=(link.text.strip_code(normalize=True,collapse=True).strip() if link.text is not None else target)
    if not target or len(target)>180 or target.startswith(('#','File:','Image:','Category:')):raise ValueError('unexpected target '+work)
    entry={'category':category,'target':target,'target_url':'https://starwars.fandom.com/wiki/'+quote(target.replace(' ','_'),safe=':/()#'),'label':label,'depth':depth,'marker_templates':markers}
    if depth>1 and depth-1 in ancestors:entry['parent_target']=ancestors[depth-1]
    links.append(entry)
   ancestors[depth]=str(wikilinks[-1].title).strip()
   for k in list(ancestors):
    if k>depth:del ancestors[k]
 if not links:raise ValueError('empty appearance extraction '+work)
 grouped={}
 for link in links:grouped.setdefault(link['category'],[]).append(link['label'])
 text='\n'.join(k+': '+ '; '.join(v) for k,v in grouped.items())
 rows.append({'title':rec['title']+' — appearance index','url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':rec['timestamp'],'source_archive_sha256':ARCH,'source_section_wikitext_sha256':digest,'work_id':work,'text':text,'text_sha256':sha(text),'appearances':links,'unlinked_bullet_lines_omitted':unlinked,'evidence_class':'secondary_index','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'App template bullet wikilinks and marker template names only; no comic dialogue, prose, images or unlinked bullet text. Nested parent links retained where available.','coverage':'Secondary editorial index; not proof of accurate or exhaustive act contents, print issue contents, pages, branches or source rights for third-party material.','embedded':False})
 audit.append({'work_id':work,'title':rec['title'],'revision_id':rev,'source_section_wikitext_sha256':digest,'status':'linked_names_extracted','link_occurrences':len(links),'unlinked_bullet_lines_omitted':unlinked})
if len(rows)!=len(PINS) or len(audit)!=3 or x['not_found']:raise ValueError('missing or unexpected pages')
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='3e726bdae4d898b7de96e6a073f2dbd52611db8ea4071db3f5b07032c5465f4b':raise ValueError('output changed')
Path('data/wookieepedia-threat-webcomic-appearance-indices.jsonl').write_text(output);Path('evaluation/threat-webcomic-appearance-extraction.json').write_text(json.dumps({'description':'Pinned wiki issue appearances: linked-name occurrences, not primary comics or proof of complete coverage. Unlinked bullet text is omitted.','source_archive_sha256':ARCH,'act_pages':3,'indices':len(rows),'link_occurrences':sum(len(r['appearances']) for r in rows),'unlinked_bullet_lines_omitted':sum(r['unlinked_bullet_lines_omitted'] for r in rows),'items':audit},indent=2,ensure_ascii=False)+'\n');print('issues',len(rows),'links',sum(len(r['appearances']) for r in rows),'unlinked lines omitted',sum(r['unlinked_bullet_lines_omitted'] for r in rows))
