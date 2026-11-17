"""Extract quote-omitted SWTOR chapter summaries from one pinned wiki revision.

Input contains raw markup and must stay local. This removes wiki quote/dialogue
templates, inline quotation-marked phrases, images and references. The output
is secondary prose and does not represent every class, branch or expansion.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
TITLE='Star Wars: The Old Republic';REV='15803850';SOURCE_HASH='8bfb3df8e128b16841c5c1a5013effe6df2f7997dd5bd82968e2c04f3b342feb'
HEADINGS=['Prologue','Chapter 1','Chapter 2','Chapter 3','Chapter 3 Epilogue: The Ilum Front','Chapter 4: Rise of the Hutt Cartel','Chapter 4 Interlude: The Dread War','Chapter 5 Prelude: Forged Alliances','Chapter 5: Shadow of Revan']
OUTPUT_PINS={'Prologue': '3a0531fe38a93c85ed3a116c3a7a6e1fc4b6a7f79fb5cc999fa4141b7a7bc888', 'Chapter 1': '6577a8fab5c7a6d9367bd78f793722d739f4ceda8e1829189c6906259cc201f2', 'Chapter 2': 'cc789e8a7dfeefe9504e99da4078268e26912bab094285f8297968c44429c4b8', 'Chapter 3': 'c0f40ce03c38840fbb97d775ee50e85a445cef324118cc4453afbfe88035cc1b', 'Chapter 3 Epilogue: The Ilum Front': '0be5c36014bcc6c07619ba8c826949f1d3193f7c6286587876a72bda3a13deac', 'Chapter 4: Rise of the Hutt Cartel': 'c96e219cbc99a93f7e1019ec02d82b410ab487191d80e12d5c59949a3844415a', 'Chapter 4 Interlude: The Dread War': '4667bd5c7871239205a152ae3ff5775a50172fd141e0ad259992bf4e7342c503', 'Chapter 5 Prelude: Forged Alliances': 'f03d4dd42a62c0a32d935edccf0dd1fbb259ff1300f89b6bfd4ff439bf7536d8', 'Chapter 5: Shadow of Revan': '96cc33e8042d09b124adad0a421e0c5bafd90aa37e7f4eed30cb06af621776a3'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def words(s):return re.findall(r'\w+',s.casefold())
x=json.loads(Path(sys.argv[1]).read_text())[TITLE];raw=x['raw_section']
if x['revision_id']!=REV or sha(raw)!=SOURCE_HASH or x['raw_wikitext_sha256']!=SOURCE_HASH or x['reasons']!=['quotes_or_dialogue']:raise ValueError('Source revision or screening changed')
parsed=mwparserfromhell.parse(raw);sections=parsed.get_sections(include_headings=True,flat=True);rows=[];url='https://starwars.fandom.com/wiki/'+quote(TITLE.replace(' ','_'),safe=':/()')
for s in sections:
 headers=s.filter_headings(recursive=False)
 if not headers:
  if str(s).strip():raise ValueError('Unexpected lead text')
  continue
 name=str(headers[0].title).strip()
 if name not in HEADINGS:raise ValueError('Unexpected heading: '+name)
 rawsection=str(s);s.remove(headers[0]);removed=[]
 for template in list(s.filter_templates(recursive=False)):
  if str(template.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech'):removed.append(str(template))
  s.remove(template,recursive=True)
 for tag in list(s.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:s.remove(tag,recursive=True)
   except ValueError:pass
 for link in list(s.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:')):
   try:s.remove(link,recursive=True)
   except ValueError:pass
 text=s.strip_code(normalize=True,collapse=True).strip();cleanhash=sha(text)
 result,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 if sha(result)!=OUTPUT_PINS[name] or re.search(r'["“”]',result) or 'thumb|' in result:raise ValueError('Unexpected quotation or image markup: '+name)
 a=words(result);b=words(' '.join(removed));shingles={tuple(a[i:i+10]) for i in range(max(0,len(a)-9))}
 if any(tuple(b[i:i+10]) in shingles for i in range(max(0,len(b)-9))):raise ValueError('Retained overlap with removed quote: '+name)
 rows.append({'title':TITLE+' — '+name,'url':url,'source_revision_url':url+'?oldid='+REV,'revision_id':REV,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':name,'plot_wikitext_sha256':SOURCE_HASH,'chapter_wikitext_sha256':sha(rawsection),'cleaned_text_sha256':cleanhash,'text_sha256':sha(result),'text':result,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images and quotation-marked phrases removed; inline omissions marked [quoted words omitted].','omitted_quote_template_count':len(removed),'omitted_inline_quote_count':n,'coverage':'Source chapter summary; class-specific paths and choices may be incomplete. Later expansions are not represented by this section.','embedded':False})
if [r['section'] for r in rows]!=HEADINGS:raise ValueError('Missing or reordered chapter sections')
Path('data/wookieepedia-swtor-chapter-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('Prepared',len(rows),'chapter summaries')
