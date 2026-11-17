"""Audit existing War excerpts against quotations in pinned source templates.

Exact eight-word overlap is a review signal, not copyright clearance. This
covers marked template parameters and quote tags, not unmarked excerpts.
"""
import hashlib,json,re,sys,mwparserfromhell
from pathlib import Path
sources=json.loads(Path(sys.argv[1]).read_text());z=json.loads(Path(sys.argv[2]).read_text());sources['Zayne Carrick']=z
files=['data/wookieepedia-war-character-biographies.jsonl','data/wookieepedia-war-zayne-summary.jsonl'];rows=[]
for f in files:
 for line in open(f,encoding='utf8'):
  x=json.loads(line);x['_file']=f;rows.append(x)
def shingles(text):
 w=re.findall(r'\w+',text.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
report=[]
for subject in sorted(sources):
 relevant=[x for x in rows if x.get('subject')==subject or subject=='Zayne Carrick' and x['_file'].endswith('war-zayne-summary.jsonl')]
 if not relevant:continue
 d=sources[subject];page=mwparserfromhell.parse(d['raw']);q=[];template_names={'quote','quotation','blockquote','quote box','dialogue','speech','cquote','quote frame'}
 for t in page.filter_templates(recursive=True):
  name=str(t.name).strip().casefold().replace('_',' ')
  for p in t.params:
   if name in template_names or str(p.name).strip().casefold() in ('quote','quotation'):q.append(mwparserfromhell.parse(str(p.value)).strip_code(normalize=True,collapse=True))
 for tag in page.filter_tags(recursive=True):
  if str(tag.tag).casefold() in ('blockquote','q'):q.append(mwparserfromhell.parse(str(tag.contents)).strip_code(normalize=True,collapse=True))
 qset=set().union(*(shingles(a) for a in q)) if q else set()
 for x in relevant:
  overlap=len(shingles(x['text'])&qset);report.append({'subject':subject,'section':x['section'],'source_revision_id':d['id'],'source_wikitext_sha256':hashlib.sha256(d['raw'].encode()).hexdigest(),'dataset':x['_file'],'text_sha256':hashlib.sha256(x['text'].encode()).hexdigest(),'marked_template_or_tag_values':len(q),'overlap_eight_word_sequences':overlap})
if len(report)!=7 or any(x['overlap_eight_word_sequences'] for x in report):raise ValueError('Unexpected corpus or quotation overlap; review required')
out={'scope':'Exact eight-word comparison of seven previously published War excerpts against all parameters of marked quote templates, parameters named quote or quotation in any template, and quote tags in their pinned source pages. Does not establish rights for unmarked or altered excerpts.','items':report}
Path('evaluation/war-template-quotation-audit.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print('Audited',len(report),'sections; matched quote sequences',sum(x['overlap_eight_word_sequences'] for x in report))
