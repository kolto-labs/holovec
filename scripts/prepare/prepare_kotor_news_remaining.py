import xml.etree.ElementTree as ET,subprocess,hashlib,json
from pathlib import Path
names={'The Taris Holofeed: Prime Edition', "The Admiral's List: Jimas Veltraa Memorial Edition", 'Adascorp Fiscal Period Financial Report and Outlook: Message from the Chief Executive', 'Adascorp Fiscal Period Financial Report and Outlook: Field Report: Project Black Harvest', 'The Adjudicator Special Report: Tools of the Trade'}
p=Path('/tmp/holovec-wookieepedia-20261108.xml.7z')
with p.open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
proc=subprocess.Popen(['7z','x','-so',str(p)],stdout=subprocess.PIPE);out={};root=None
for event,el in ET.iterparse(proc.stdout,events=('start','end')):
 if root is None and event=='start':root=el
 if event!='end' or not el.tag.endswith('}page'):continue
 title=el.findtext('{*}title')
 if title in names:
  rev=el.find('{*}revision');raw=rev.findtext('{*}text') or '';out[title]={'raw_wikitext':raw,'revision_id':rev.findtext('{*}id'),'timestamp':rev.findtext('{*}timestamp'),'sha256':hashlib.sha256(raw.encode()).hexdigest()}
 root.clear()
if proc.wait():raise RuntimeError('decompression failed')
q=Path('/tmp/holovec-kotor-news-remaining-raw.json');q.write_text(json.dumps(out,ensure_ascii=False));q.chmod(0o600)
print('Found',len(out),'titles',sorted(out),'missing',sorted(names-set(out)))
