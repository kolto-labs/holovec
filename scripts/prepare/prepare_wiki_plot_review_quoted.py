"""Prepare local-only plot candidates including quoted phrases for manual redaction.

No candidate is approved by this script. Output is created exclusively at the
path supplied by the operator and MUST NOT be published without review. Uses
current dump revisions, which may differ from the earlier flat snapshot.
"""
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell

archive=Path(sys.argv[1]);output=Path(sys.argv[2]);audit=json.loads(Path('evaluation/wiki-plot-section-audit.json').read_text())
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=audit['archive_sha256']:raise ValueError('unexpected dump hash')
if output.exists():raise FileExistsError(output)
head=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$')
quote_markup=re.compile(r'(?i)\{\{\s*(?:quote|quotation|blockquote|quote[_ ]?box|dialogue|speech)\b|<\s*(?:blockquote|q)\b')
def get_section(raw,match,heads,index):
 end=next((x.start() for x in heads[index+1:] if len(x.group(1))<=len(match.group(1))),len(raw))
 return raw[match.end():end].strip()
def clean(section):
 code=mwparserfromhell.parse(section)
 for tag in list(code.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(tag,recursive=True)
   except ValueError:pass
 for template in list(code.filter_templates(recursive=False)):
  try:code.remove(template,recursive=True)
  except ValueError:pass
 return code.strip_code(normalize=True,collapse=True).strip()
def words(s):return re.findall(r'\w+',s.casefold())
def overlap(a,b,n=10):
 left=words(a);right=words(b)
 if len(left)<n or len(right)<n:return False
 shingle={tuple(left[i:i+n]) for i in range(len(left)-n+1)}
 return any(tuple(right[i:i+n]) in shingle for i in range(len(right)-n+1))
results=[];counts={'target_titles':len(audit['articles']),'matched':0,'no_plot':0,'quote_markup_or_double_quote':0,'publisher_overlap':0,'empty':0,'candidates':0}
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE)
try:
 root=None
 for event,el in ET.iterparse(proc.stdout,events=('start','end')):
  if root is None and event=='start':root=el
  if event!='end' or not el.tag.endswith('}page'):continue
  title=el.findtext('{*}title')
  if title in audit['articles']:
   counts['matched']+=1;rev=el.find('{*}revision');raw=rev.findtext('{*}text',default='') or '';heads=list(head.finditer(raw));sections={}
   for i,h in enumerate(heads):
    name=h.group(2).strip().casefold()
    if name in ('plot summary',"publisher's summary",'opening crawl','official description','back cover'):
     sections.setdefault(name,[]).append(get_section(raw,h,heads,i))
   plots=sections.get('plot summary',[])
   if not plots:counts['no_plot']+=1
   else:
    for section in plots:
     digest=hashlib.sha256(section.encode()).hexdigest();known=audit['articles'][title]['plot_sections']
     if digest not in {x['raw_wikitext_sha256'] for x in known}:raise ValueError('section hash mismatch: '+title)
     screened = re.sub(r'<ref\b[^>]*?/>|<ref\b[^>]*>.*?</ref\s*>', '', section, flags=re.I|re.S)
     if quote_markup.search(screened):counts['quote_markup_or_double_quote']+=1;continue
     text=clean(section)
     if not text:counts['empty']+=1;continue
     risk=' '.join(clean(s) for k,v in sections.items() if k!='plot summary' for s in v)
     if overlap(text,risk):counts['publisher_overlap']+=1;continue
     results.append({'title':title,'url':'https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()'), 'revision_id':rev.findtext('{*}id'),'timestamp':rev.findtext('{*}timestamp'),'source_archive_sha256':audit['archive_sha256'],'section':'Plot summary','raw_wikitext_sha256':digest,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text,'license':'CC BY-SA 3.0 (wiki contributor text; review third-party material)','status':'review_required_not_approved'})
     counts['candidates']+=1
  root.clear()
finally:
 if proc.stdout:proc.stdout.close()
 if proc.wait():raise RuntimeError('7z extraction failed')
if counts['matched']!=counts['target_titles']:raise ValueError('not all held titles found')
with output.open('x',encoding='utf-8') as f:
 for r in results:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
output.chmod(0o600)
print(json.dumps(counts))
