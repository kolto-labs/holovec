"""Extract attributed editorial appearance links for eight KOTOR news inserts.

Input is the private raw JSON produced from the pinned public wiki dump by
prepare_kotor_news_appearances.py. No primary news text or inference is used.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={
'The Adjudicator Special Report: The Outer Rim':('15538656','59d08ba4b5f4e93bc1c2f2b9c3bb8b3867a1cf9282121ecd8259a3d4cc286662'),
"The Admiral's List: Remember Serroco! Edition":('15366751','57cad856782799f7af9c3b5484d31425e370fa80765ad8360bd74f4c5d1786cd'),
'The Taris Holofeed: Siege Edition':('15366714','16b93a91bee80cb1c6ff53b3ea3303d385522131e0dd4141379bcd58359849f5'),
'The Taris Holofeed: Invasion Edition':('15366754','1331ad3b7a1fc926d6ea35fa4ce7601e8661d4449fe99d6d0b5506e2dd42d145'),
'The Taris Holofeed Special Proclamation':('15366778','c07face75ca13d33ce30c660918056de9d52c9353c57dd3919a26c724d75b264'),
"The Admiral's List: Karath Home Safely":('15491749','ff46c5538ebfeab4bb2545feb08c11ce59936ef8148a5eea93997634ca0898c2'),
'The Adjudicator Special Report: The Colonies':('15692236','0e4a399db50f94807b9116ec73e3237612cce5ba128abfaac44a4b7ea2ca9f54'),
'Galactic Republic Defense Ministry Daily Brief KD0092':('15241111','219fbfd677d51afc6c0563e06382f54208152e87958776c29968fb2b56964b54')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
x=json.loads(Path(sys.argv[1]).read_text()); inventory={r['title']:r for r in json.loads(Path('catalog/works/kotor-comic-news-inventory.json').read_text())['items']};rows=[]
for title,(rev,digest) in sorted(PINS.items()):
 rec=x[title];raw=rec['raw_wikitext'];heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));found=[(i,h) for i,h in enumerate(heads) if h.group(2).strip().casefold()=='appearances'];assert rec['revision_id']==rev and len(found)==1
 i,h=found[0];end=next((z.start() for z in heads[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));section=raw[h.end():end].strip();assert sha(section)==digest
 apps=[t for t in mwparserfromhell.parse(section).filter_templates(recursive=False) if str(t.name).strip().casefold()=='app'];assert len(apps)==1
 links=[];unlinked=0
 for param in apps[0].params:
  category=str(param.name).strip();ancestors={}
  for line in str(param.value).splitlines():
   match=re.match(r'^\s*(\*+)\s*(.*)$',line)
   if not match:continue
   depth=len(match.group(1));code=mwparserfromhell.parse(match.group(2))
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
    target=str(link.title).strip();label=link.text.strip_code(normalize=True,collapse=True).strip() if link.text is not None else target
    if not target or len(target)>180 or target.startswith(('#','File:','Image:','Category:')):raise ValueError('unexpected target '+title)
    item={'category':category,'target':target,'target_url':'https://starwars.fandom.com/wiki/'+quote(target.replace(' ','_'),safe=':/()#'),'label':label,'depth':depth,'marker_templates':markers}
    if depth>1 and depth-1 in ancestors:item['parent_target']=ancestors[depth-1]
    links.append(item)
   ancestors[depth]=str(wikilinks[-1].title).strip()
   for k in list(ancestors):
    if k>depth:del ancestors[k]
 if not links:raise ValueError('empty index '+title)
 groups={}
 for l in links:groups.setdefault(l['category'],[]).append(l['label'])
 text='\n'.join(k+': '+'; '.join(v) for k,v in groups.items());url=inventory[title]['secondary_article_url']
 rows.append({'title':title+' — appearance index','url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':rec['timestamp'],'source_archive_sha256':ARCH,'source_section_wikitext_sha256':digest,'work_id':inventory[title]['id'],'parent_issue_work_id':inventory[title]['parent_issue_work_id'],'text':text,'text_sha256':sha(text),'appearances':links,'unlinked_bullet_lines_omitted':unlinked,'evidence_class':'secondary_index','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends per source bibliography','extraction':'App template bullet links and marker names only; no news insert prose or images.','coverage':'Editorial index of appearances; not primary content or proof of complete or accurate issue coverage.','embedded':False})
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);Path('data/wookieepedia-kotor-news-appearance-indices.jsonl').write_text(output);print('Indices',len(rows),'linked occurrences',sum(len(r['appearances']) for r in rows),'unlinked omitted',sum(r['unlinked_bullet_lines_omitted'] for r in rows))
