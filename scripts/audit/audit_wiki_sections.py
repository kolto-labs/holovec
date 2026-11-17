"""Audit section boundaries in a local Wookieepedia XML archive without exporting text.

Reads the held title list, records current dump revision and structural signals,
not a license conclusion. The current revision may differ from the snapshot that
was originally held. Usage: python audit_wiki_sections.py PATH_TO_XML_7Z
"""
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

archive=Path(sys.argv[1])
expected_sha='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
with archive.open('rb') as f:
 if hashlib.file_digest(f,'sha256').hexdigest()!=expected_sha:raise ValueError('unexpected archive hash')
held=json.loads(Path('evaluation/wiki-rights-flags.json').read_text())['flagged_records']
titles={x['title'] for x in held}
heading=re.compile(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$')
quote_template=re.compile(r'(?i)\{\{\s*(?:quote|quotation|blockquote|quote[_ ]?box|dialogue|speech)\b|<\s*(?:blockquote|q)\b')
results={}
proc=subprocess.Popen(['7z','x','-so',str(archive)],stdout=subprocess.PIPE)
try:
 context=ET.iterparse(proc.stdout,events=('start','end'));root=None
 for event,el in context:
  if root is None and event=='start':root=el
  if event!='end' or not el.tag.endswith('}page'):continue
  title=el.findtext('{*}title')
  if title in titles:
   rev=el.find('{*}revision');raw=rev.findtext('{*}text',default='') if rev is not None else ''
   heads=list(heading.finditer(raw));sections=[]
   for i,h in enumerate(heads):
    if h.group(2).strip().casefold()!='plot summary':continue
    end=len(raw)
    for nxt in heads[i+1:]:
     if len(nxt.group(1))<=len(h.group(1)):end=nxt.start();break
    section=raw[h.end():end].strip()
    sections.append({'heading_level':len(h.group(1)),'raw_wikitext_sha256':hashlib.sha256(section.encode()).hexdigest(),'characters':len(section),'plot_placeholder_template':bool(re.search(r'(?i)\{\{\s*plot(?:\s*[|}])',section)),'quote_template_or_html':bool(quote_template.search(section)),'double_quote_characters':sum(section.count(c) for c in ('"','“','”')),'status':'review_required'})
   results[title]={'revision_id':rev.findtext('{*}id') if rev is not None else None,'timestamp':rev.findtext('{*}timestamp') if rev is not None else None,'plot_sections':sections}
  root.clear()
finally:
 if proc.stdout:proc.stdout.close()
 rc=proc.wait()
 if rc:raise RuntimeError(f'7z extraction failed: {rc}')
if set(results)!=titles:raise ValueError(f'missing {len(titles-set(results))} held titles')
report={'archive_url':'https://s3.amazonaws.com/wikia_xml_dumps/s/st/starwars_pages_current.xml.7z','archive_sha256':expected_sha,'purpose':'Metadata-only structural triage. Neither a rights grant nor proof that text is suitable for publication.','articles':results}
Path('evaluation/wiki-plot-section-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps({'held_titles':len(results),'with_plot_sections':sum(bool(x['plot_sections']) for x in results.values()),'with_quote_template_or_html':sum(any(s['quote_template_or_html'] for s in x['plot_sections']) for x in results.values())}))
