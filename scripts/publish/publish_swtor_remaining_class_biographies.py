"""Create conservatively screened secondary biography sections from a pinned dump.

The local input contains raw source markup. This screen cannot establish rights in
unmarked third-party quotations or completeness of story branches.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell

PINS={
 'Cipher Nine':('15797331','aa966100bdb601be2b79f51d413a389b3d37d7e25e127105b021ec88bc593442','class-imperial-agent','dark-side game-mechanics template'),
 'Hero of Tython':('15769665','9963d273a81a82e582c998e88fd248e68510ee38125f9b06a29df1c108829591','class-jedi-knight','light-side game-mechanics template'),
 "Empire's Wrath":('15766025','1d98be4d9860581815a53a6702e09cde98fff50beef7cf58412585b3596b96bf','class-sith-warrior','dark-side game-mechanics template'),
 "The Barsen'thor":('15806931','0295b6cfae83c115c31854ec445cd57a9ab2194523b6bb6929e3f7a7d5da3354','class-jedi-consular','light-side game-mechanics template'),
 'Hunter (individual)':('15803857','c8c70ca23d60052ad1fc99e19f05b56a4964004d756e71a967aee49786bbbc1d','class-bounty-hunter','dark-side game-mechanics template'),
 'Voidhound':('15779295','fb13971d2bf427fc2f2aa933126e34dbabcb3256aac7799e44841dd9b0b086d7','class-smuggler','light-side game-mechanics template'),
}
ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
QUOTES={'quote','quotation','blockquote','dialogue','speech'}
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def words(s): return re.findall(r'\w+',s.casefold())
def shingles(s):
 w=words(s); return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
data=json.loads(Path(sys.argv[1]).read_text());rows=[];held=[]
for title,(rev,rawhash,work,choice) in sorted(PINS.items()):
 x=data[title]; raw=x['raw_section']; code=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=rawhash or x['raw_wikitext_sha256']!=rawhash or x['reasons']!=['quotes_or_dialogue']:
  raise ValueError('Source or screening changed: '+title)
 # Compare with quotes across the entire article biography, not only this section.
 quote_text=' '.join(str(t) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold() in QUOTES)
 quote_shingles=shingles(quote_text)
 for section in code.get_sections(levels=[3],include_lead=True,include_headings=True,flat=False):
  rawsection=str(section)
  if not rawsection.strip(): continue
  heads=[h for h in section.filter_headings(recursive=False) if h.level==3]
  name=str(heads[0].title).strip() if heads else 'Biography introduction'
  if heads: section.remove(heads[0])
  removed=0
  for template in list(section.filter_templates(recursive=False)):
   if str(template.name).strip().casefold() in QUOTES: removed+=1
   section.remove(template,recursive=True)
  for tag in list(section.filter_tags(recursive=True)):
   if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
    try: section.remove(tag,recursive=True)
    except ValueError: pass
  for link in list(section.filter_wikilinks(recursive=True)):
   if str(link.title).strip().casefold().startswith(('file:','image:')):
    try: section.remove(link,recursive=True)
    except ValueError: pass
  cleaned=section.strip_code(normalize=True,collapse=True).strip()
  result,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',cleaned)
  reason=None
  if not result: reason='empty after quote/template removal'
  elif re.search(r'["“”]',result) or 'thumb|' in result: reason='unresolved quotation marks or image markup'
  elif shingles(result)&quote_shingles: reason='eight-word overlap with biography quote template'
  if reason:
   held.append({'title':title,'section':name,'section_wikitext_sha256':sha(rawsection),'reason':reason});continue
  url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
  rows.append({'title':title+' — '+name,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':ARCHIVE,'section':name,'source_biography_wikitext_sha256':rawhash,'section_wikitext_sha256':sha(rawsection),'cleaned_text_sha256':sha(cleaned),'text_sha256':sha(result),'text':result,'inventory_work_id':work,'source_choice_assumption':'source biography uses '+choice,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'Templates, references, images and quotation-marked phrases removed; inline omissions marked [quoted words omitted]. Article-wide quote-template overlap screened at eight words.','omitted_quote_template_count':removed,'omitted_inline_quote_count':n,'coverage':'Partial secondary biography; class missions, alternatives, branching and updates are not complete.','embedded':False})
if len({(r['inventory_work_id'],r['section']) for r in rows})!=len(rows): raise ValueError('Duplicate section')
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='2d265c82455d7c95fa2f95397adf4602d55bc9d79d4d25793ee4026afd4cc2b5': raise ValueError('Candidate output changed; re-screen before release')
Path('data/wookieepedia-swtor-remaining-class-biographies.jsonl').write_text(output)
Path('evaluation/swtor-remaining-class-biography-holds.json').write_text(json.dumps({'description':'Sections held by automated cleaning or article-wide quote overlap screen; no raw text is stored. This is not a rights conclusion.','source_archive_sha256':ARCHIVE,'held':held},indent=2,ensure_ascii=False)+'\n')
print('Prepared',len(rows),'secondary biography sections; held',len(held))
