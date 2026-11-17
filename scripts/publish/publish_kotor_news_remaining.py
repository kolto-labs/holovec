"""Extract attributed editorial appearance links for five KOTOR news inserts.

Input is the private raw JSON produced from the pinned public wiki dump by
prepare_kotor_news_remaining.py. No primary news text or inference is used.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={
'The Taris Holofeed: Prime Edition':('15355966','2113da8c291909c82980082adf17e507a14aa4f025b944e68c525d228bdc63f3'),
"The Admiral's List: Jimas Veltraa Memorial Edition":('15366707','c1a2b069df695fbbbf40a78c95d1806c25a5ace09b7815d5678b8a835ac7af3c'),
'Adascorp Fiscal Period Financial Report and Outlook: Message from the Chief Executive':('15366755','b3dc63f956a11aae477d81676f9a6598e92de45b5122e3f7bad2789984f0a640'),
'Adascorp Fiscal Period Financial Report and Outlook: Field Report: Project Black Harvest':('15366766','f30968d547dacd70d8a5b25b9f68073544e9f4f18a42e4f381525de15a981d79'),
'The Adjudicator Special Report: Tools of the Trade':('15609882','13151743fd73f9340ddd3f575f74bb17fe0e6badda238fae4d10c868216ade07')}
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
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);Path('data/wookieepedia-kotor-news-remaining-appearance-indices.jsonl').write_text(output);print('Indices',len(rows),'linked occurrences',sum(len(r['appearances']) for r in rows),'unlinked omitted',sum(r['unlinked_bullet_lines_omitted'] for r in rows))
