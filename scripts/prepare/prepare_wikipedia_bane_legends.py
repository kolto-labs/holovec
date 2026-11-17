"""Extract quote-omitted Legends sections from a fixed Wikipedia revision.

This source is secondary and may combine different works and continuities.
Requires requests and mwparserfromhell. No model inference is involved.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
REV=1384323675;API='https://en.wikipedia.org/w/api.php';URL='https://en.wikipedia.org/wiki/Darth_Bane';source_url='https://en.wikipedia.org/w/index.php?title=Darth_Bane&oldid='+str(REV)
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';res=s.get(API,params={'action':'query','format':'json','formatversion':2,'prop':'revisions','rvprop':'ids|timestamp|content','rvslots':'main','revids':REV},timeout=30);res.raise_for_status();page=res.json()['query']['pages'][0];v=page['revisions'][0];raw=v['slots']['main']['content']
if page['title']!='Darth Bane' or v['revid']!=REV or hashlib.sha256(raw.encode()).hexdigest()!='547a90343c259b026cdaaf4e74f2718e32d1e5af6dc8b74edd40a225871fa393':raise ValueError('unexpected revision')
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
code=mwparserfromhell.parse(raw);names={'quote','quotation','blockquote','quote box','dialogue','speech','cquote','quote frame'}
quotes=[str(t.get(1).value.strip_code(normalize=True,collapse=True)) for t in code.filter_templates(recursive=True) if str(t.name).strip().casefold().replace('_',' ') in names and t.has(1)]
quotes += [str(t.contents.strip_code(normalize=True,collapse=True)) for t in code.filter_tags(recursive=True) if str(t.tag).casefold() in ('blockquote','q')]
qset=set().union(*(shingles(q) for q in quotes)) if quotes else set()
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$');hs=list(head.finditer(raw));legends=next(i for i,h in enumerate(hs) if len(h.group(1))==3 and mwparserfromhell.parse(h.group(2)).strip_code().strip()=='Legends');end=next((i for i in range(legends+1,len(hs)) if len(hs[i].group(1))<=3),len(hs));rows=[];held=[]
for i in range(legends+1,end):
 h=hs[i]
 if len(h.group(1))!=4:continue
 name=mwparserfromhell.parse(h.group(2)).strip_code(normalize=True,collapse=True).strip();stop=next((hs[j].start() for j in range(i+1,len(hs)) if len(hs[j].group(1))<=4),len(raw));source=raw[h.end():stop].strip();c=mwparserfromhell.parse(source)
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
 text,unbalanced=re.subn(r'(?m)(?:^|(?<=[.!?])\s+)[^.!?\n]*[\"“”][^.!?\n]*[.!?]?', ' [sentence omitted due to unbalanced quotation]', text)
 reason='empty' if not text else 'unresolved quote or image marker' if re.search(r'["“”]',text) or 'thumb|' in text else 'eight-word overlap with full-page quotation block' if shingles(text)&qset else None
 if reason:held.append({'section':name,'section_wikitext_sha256':sha(source),'reason':reason});continue
 rows.append({'title':'Darth Bane — '+name,'url':URL,'source_revision_url':source_url,'revision_id':REV,'timestamp':v['timestamp'],'page_wikitext_sha256':sha(raw),'section_wikitext_sha256':sha(source),'cleaned_text_sha256':sha(clean),'text_sha256':sha(text),'section':name,'text':text,'license':'CC BY-SA 4.0','attribution':'Wikipedia contributors; see linked article revision history','continuity':'Legends','evidence_class':'secondary','extraction':'References, templates, images, quotation-marked phrases and sentences containing unbalanced quote marks omitted; full-page quotation-block overlap screened at eight words.','omitted_inline_quotations':n,'omitted_unbalanced_quote_sentences':unbalanced,'coverage':'Partial secondary account; individual comics and novels, visual narrative and primary text are not included.','embedded':False})
if len(rows)+len(held)!=5:raise ValueError('Unexpected legends sections')
output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
if sha(output)!='94a7270bf579e96328a13a2b06979a81ac375ef2e22f69c15b50961850cd2963':raise ValueError('Output changed; re-screen before release')
Path('data/wikipedia-bane-legends-sections.jsonl').write_text(output)
Path('evaluation/wikipedia-bane-legends-screen.json').write_text(json.dumps({'description':'Limited quotation screen; absent matches do not clear unmarked excerpts or establish primary coverage.','revision_id':REV,'page_wikitext_sha256':sha(raw),'quote_blocks':len(quotes),'included':len(rows),'held':held},indent=2,ensure_ascii=False)+'\n')
print('sections',len(rows),'held',[(x['section'],x['reason']) for x in held],'quote blocks',len(quotes))
