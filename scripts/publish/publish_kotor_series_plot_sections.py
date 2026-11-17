"""Build quote-omitted comic-series plot sections from a pinned local review file.

Usage: PYTHONPATH=<dependencies> python publish_kotor_series_plot_sections.py RAW_REVIEW_JSON
No primary comic text is implied. Automated screening cannot clear unmarked excerpts.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
TITLE='Star Wars: Knights of the Old Republic (comic series)'
REV='15829847';RAW='e3e15ae147a272d5f7b1c3ddde9f6df596a64e7464a2da86d880efc4328519b3';ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
URL='https://starwars.fandom.com/wiki/Star_Wars:_Knights_of_the_Old_Republic_(comic_series)'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text())[TITLE];raw=x['raw_section']
if x['revision_id']!=REV or sha(raw)!=RAW or x['raw_wikitext_sha256']!=RAW or x['reasons']!=['quotes_or_dialogue']:raise ValueError('Source or publisher overlap screen changed')
code=mwparserfromhell.parse(raw);quote_names={'quote','quotation','blockquote','quote box','dialogue','speech'}
quote_blocks=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in quote_names and t.has(1)]
quote_blocks += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in code.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
quote_shingles=set().union(*(shingles(t) for t in quote_blocks)) if quote_blocks else set()
arcs=json.loads(Path('catalog/works/comics-arc-inventory.json').read_text())['arcs'];by_title={a['title'].casefold():a for a in arcs};rows=[];held=[]
for section in code.get_sections(levels=[3],include_lead=True,include_headings=True,flat=False):
 source=str(section)
 if not source.strip():continue
 hs=[h for h in section.filter_headings(recursive=False) if h.level==3]
 if len(hs)!=1:raise ValueError('Unexpected section heading')
 name=hs[0].title.strip_code(normalize=True,collapse=True).strip();section.remove(hs[0]);a=by_title.get(name.casefold())
 if not a:raise ValueError('Unmapped arc '+name)
 quote_count=0
 for t in list(section.filter_templates(recursive=False)):
  if str(t.name).strip().casefold().replace('_',' ') in quote_names:quote_count+=1
  section.remove(t,recursive=True)
 for tag in list(section.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:section.remove(tag,recursive=True)
   except ValueError:pass
 for link in list(section.filter_wikilinks(recursive=True)):
  if str(link.title).strip().casefold().startswith(('file:','image:')):
   try:section.remove(link,recursive=True)
   except ValueError:pass
 clean=section.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',clean)
 reason='empty after removal' if not text else 'unresolved quotation marks or image markup' if re.search(r'["“”]',text) or 'thumb|' in text else 'eight-word overlap with plot quotation block' if shingles(text)&quote_shingles else None
 if reason:held.append({'arc_id':a['id'],'section':name,'section_wikitext_sha256':sha(source),'reason':reason});continue
 rows.append({'title':TITLE+' — '+name,'url':URL,'source_revision_url':URL+'?oldid='+REV,'revision_id':REV,'timestamp':x['timestamp'],'source_archive_sha256':ARCHIVE,'source_plot_wikitext_sha256':RAW,'section_wikitext_sha256':sha(source),'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'text':text,'section':name,'inventory_arc_id':a['id'],'issue_ids':a['issue_ids'],'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images and quotation-marked phrases removed; inline omissions marked [quoted words omitted]. Screened for eight-word overlap with quotation blocks in the plot section.','omitted_quote_templates':quote_count,'omitted_inline_quotations':n,'coverage':'Arc-level secondary plot summary, not a complete issue-level account or primary comic pages.','embedded':False})
if len(rows)+len(held)!=18:raise ValueError('Unexpected number of arc sections')
out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(out)!='ddb109e933ac92c3d097e371da1d784185a409bb96b81901be10feb7c463b2b5': raise ValueError('Output changed; re-screen before release')
Path('data/wookieepedia-kotor-series-arc-sections.jsonl').write_text(out)
Path('evaluation/kotor-series-arc-section-holds.json').write_text(json.dumps({'description':'Automated screening outcomes; no source text stored. A clean screen is not rights clearance.','source_archive_sha256':ARCHIVE,'source_revision_id':REV,'held':held},indent=2,ensure_ascii=False)+'\n')
print('Prepared',len(rows),'sections; held',len(held));print([(x['section'],x['reason']) for x in held])
