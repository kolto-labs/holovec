"""Produce quote-omitted Dawn of the Jedi series and arc plot sections.

Usage: PYTHONPATH=<dependencies> python publish_dawn_series_plot_sections.py LOCAL_REVIEW_JSON
Plot-section quotation overlap is a limited screen, not rights clearance.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
ARCH='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
PINS={'Star Wars: Dawn of the Jedi':('15790953','59bd24c6514ca385b8c166781010418bf40d4f3ff3800e8ecbb38ff90f2b5833'),'Star Wars: Dawn of the Jedi: Force Storm':('15790956','6d814442740a18ae2a5906d52f29b7c057d3207f9ad53df84e55b153abb8e0ab'),'Star Wars: Dawn of the Jedi: The Prisoner of Bogan':('15686385','82e5f417e3a85cb46273873113674fda9814a2fdc7aee24bb522a72dae61cc67'),'Star Wars: Dawn of the Jedi: Force War':('15686386','7fdda410884f9359c8c4be567a63149f13ab3e8a4a3dc352fd72fd1e59f44e83')}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
data=json.loads(Path(sys.argv[1]).read_text());rows=[];held=[];names={'quote','quotation','blockquote','dialogue','speech'}
for title,(rev,digest) in sorted(PINS.items()):
 x=data[title];raw=x['raw_section'];c=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=digest or x['raw_wikitext_sha256']!=digest or x['reasons']!=['quotes_or_dialogue']:raise ValueError('source or publisher overlap screen changed: '+title)
 qs=[]
 for t in c.filter_templates(recursive=True):
  if str(t.name).strip().casefold() in names and t.has(1):qs.append(str(t.get(1).value.strip_code(normalize=True,collapse=True)))
 for tag in c.filter_tags(recursive=True):
  if str(tag.tag).casefold() in ('blockquote','q'):qs.append(str(tag.contents.strip_code(normalize=True,collapse=True)))
 qset=set().union(*(shingles(q) for q in qs)) if qs else set()
 for section in c.get_sections(levels=[3],include_lead=True,include_headings=True,flat=False):
  source=str(section)
  if not source.strip():continue
  heads=[h for h in section.filter_headings(recursive=False) if h.level==3];name=heads[0].title.strip_code(normalize=True,collapse=True).strip() if heads else 'Plot summary'
  if heads:section.remove(heads[0])
  removed=0
  for t in list(section.filter_templates(recursive=False)):
   if str(t.name).strip().casefold() in names:removed+=1
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
  reason='empty' if not text else 'unresolved quote or image marker' if re.search(r'["“”]',text) or 'thumb|' in text else 'eight-word overlap with plot quotation block' if shingles(text)&qset else None
  if reason:held.append({'title':title,'section':name,'section_wikitext_sha256':sha(source),'reason':reason});continue
  url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
  rows.append({'title':title+' — '+name,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':ARCH,'source_plot_wikitext_sha256':digest,'section_wikitext_sha256':sha(source),'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'text':text,'section':name,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images and quotation-marked phrases removed; inline omissions marked [quoted words omitted]. Eight-word overlap checked against quotation blocks within the plot section.','omitted_quote_templates':removed,'omitted_inline_quotations':n,'coverage':'Partial arc or series-level secondary summary; not individual issue coverage or primary comic pages.','embedded':False})
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='209aee288064df5b1dca99889dc8cfab5f4e26826522bb733acdd111076cbe02':raise ValueError('Output changed; re-screen before release')
Path('data/wookieepedia-dawn-series-sections.jsonl').write_text(output);Path('evaluation/dawn-series-quote-holds.json').write_text(json.dumps({'description':'Held sections from limited plot quote screening, without raw text. This is not rights clearance.','source_archive_sha256':ARCH,'held':held},indent=2,ensure_ascii=False)+'\n');print('prepared',len(rows),'sections held',len(held));print([(x['title'],x['section'],x['reason']) for x in held])
