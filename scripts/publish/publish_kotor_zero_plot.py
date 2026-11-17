"""Publish the screened KOTOR 0 wiki plot section from a local pinned review.

Original comic opening crawl, dialogue, artwork and marked quotations are excluded.
A quotation screen cannot establish rights for unmarked third-party material.
"""
import json,re,hashlib,sys
from pathlib import Path
import mwparserfromhell
sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());assert x['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';v=x['records']['Knights of the Old Republic 0'];raw=v['raw_wikitext'];assert (v['revision_id'],sha(raw))==('15241108','bf6c86e54bb935e3ba64564174d2a6aa4fca40617e1aaf1ecf7e41027b7c4c10')
heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));plot=[(i,h) for i,h in enumerate(heads) if h.group(2).strip().casefold()=='plot summary'];assert len(plot)==1
i,h=plot[0];end=next((z.start() for z in heads[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));section=raw[h.end():end];c=mwparserfromhell.parse(raw);omitted=[]
for t in c.filter_templates(recursive=True):
 if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):omitted.extend(p.value.strip_code() for p in t.params)
for t in c.filter_tags(recursive=True):
 if str(t.tag).casefold() in ('blockquote','q','poem'):omitted.append(t.contents.strip_code())
for j,h2 in enumerate(heads):
 if h2.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
  e=next((z.start() for z in heads[j+1:] if len(z.group(1))<=len(h2.group(1))),len(raw));omitted.append(mwparserfromhell.parse(raw[h2.end():e]).strip_code())
code=mwparserfromhell.parse(section)
for t in list(code.filter_templates(recursive=False)):code.remove(t,recursive=True)
for t in list(code.filter_tags(recursive=True)):
 if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
  try:code.remove(t,recursive=True)
  except ValueError:pass
text=code.strip_code(normalize=True,collapse=True).strip();text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
assert text and not re.search(r'["“”]',text) and not any(shingles(text)&shingles(z) for z in omitted)
row={'title':'Knights of the Old Republic 0 — plot summary','url':v['source_url'],'source_revision_url':v['source_url']+'?oldid='+v['revision_id'],'revision_id':v['revision_id'],'timestamp':v['timestamp'],'source_archive_sha256':x['archive_sha256'],'full_page_wikitext_sha256':sha(raw),'plot_wikitext_sha256':sha(section),'text_sha256':sha(text),'text':text,'work_id':'kotor-2006-000','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','coverage':'Wiki plot summary only; quoted words, comic opening crawl, original dialogue and artwork omitted. Unmarked third-party excerpts remain unverified.','embedded':False,'omitted_inline_quotations':n}
out=json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n';Path('data/wookieepedia-kotor-zero-plot.jsonl').write_text(out);print('Included KOTOR #0 secondary plot, text hash',sha(text),'output hash',sha(out))
