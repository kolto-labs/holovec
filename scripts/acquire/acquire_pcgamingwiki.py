"""Reproduce the reviewed PCGamingWiki section selection from the 2023 history dump.

Requires 7z and mwparserfromhell. This streams the 11.9 GB XML; it does not
extract it to disk. --cached-targets accepts an intermediate only if all four
revision texts match the pinned digests.
"""
import argparse, hashlib, json, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell

ARCHIVE_SHA = '3d68f6d375a4decf26399ee0343ed8a19476963512358ffb393174a6155f0432'
ARCHIVE_URL = 'https://archive.org/download/wikidump-pcgamingwikicom_w/pcgamingwikicom_w-20230223-history.xml.7z'
PINS = {
 'Star Wars: Knights of the Old Republic': ('1379285','565da02c15651fe2c3156ce419592a00d351362cde75fd998636844c3b115354'),
 'Star Wars: Knights of the Old Republic II - The Sith Lords': ('1379286','8ea196b6e98f31b8990fe2f5111a0ccfcfee5492ca4299799f72abacad37aacf'),
 'Star Wars: The Old Republic': ('1379287','521bc80d9d037632bf6ca065135b2affdda759362ce9134747e28e805a85bec7'),
 'PCGamingWiki:Copyrights': ('1286668','102a5965346e7f1e124b3ba11af86fa2ad803e011d520efe53ba9c10c0624bcd'),
}
SELECTION = {
 'Star Wars: Knights of the Old Republic': ['Patches','[https://deadlystream.com/files/file/1258-kotor-1-community-patch/ KotOR 1 Community Patch (K1CP)]'],
 'Star Wars: Knights of the Old Republic II - The Sith Lords': ['Version differences','Patches','[https://deadlystream.com/files/file/578-tsl-restored-content-mod/ Restored Content Mod (TSLRCM)]','[https://deadlystream.com/files/file/1280-kotor-2-community-patch/ KotOR 2 Community Patch (K2CP)]','Stuttering or Freezing after combat / Unable to move the character'],
 'Star Wars: The Old Republic': ['Disable Bitraider'],
}
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def scan(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
 if h.hexdigest()!=ARCHIVE_SHA: raise ValueError('Archive digest mismatch')
 proc=subprocess.Popen(['7z','x','-so',str(path),'pcgamingwikicom_w-20230223-history.xml'],stdout=subprocess.PIPE)
 best={}; title=None; root=None
 for event,el in ET.iterparse(proc.stdout,events=('start','end')):
  tag=el.tag.rsplit('}',1)[-1]
  if root is None and event=='start': root=el
  if event=='start' and tag=='page': title=None
  if event=='end' and tag=='title': title=el.text or ''
  if event=='end' and tag=='revision':
   if title in PINS:
    rev=el.findtext('{*}id'); ts=el.findtext('{*}timestamp') or ''; raw=el.findtext('{*}text') or ''
    if title not in best or ts>best[title]['timestamp']: best[title]={'revision':rev,'timestamp':ts,'wikitext':raw}
   el.clear()
  if event=='end' and tag=='page': root.clear()
 if proc.wait()!=0: raise RuntimeError('Archive decompression failed')
 return best

def main():
 parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--archive'); group.add_argument('--cached-targets')
 parser.add_argument('--output',default='data/pcgamingwiki-sections.jsonl'); args=parser.parse_args()
 pages=scan(args.archive) if args.archive else json.loads(Path(args.cached_targets).read_text())
 for title,(revision,digest) in PINS.items():
  page=pages[title]
  if str(page['revision'])!=revision or sha(page['wikitext'])!=digest: raise ValueError('Revision pin mismatch: '+title)
 records=[]
 for title,headings in SELECTION.items():
  page=pages[title]; sections=mwparserfromhell.parse(page['wikitext']).get_sections(include_headings=True,flat=True)
  for heading in headings:
   matched=[s for s in sections if s.filter_headings() and str(s.filter_headings()[0].title).strip()==heading]
   if len(matched)!=1: raise ValueError(f'Expected one section: {title} / {heading}')
   section=matched[0]; raw=str(section); section.remove(section.filter_headings()[0])
   for tag in list(section.filter_tags(recursive=True)):
    if str(tag.tag).lower() in ('ref','gallery'): section.remove(tag,recursive=True)
   text=' '.join(section.strip_code().split())
   if not text: raise ValueError('Empty selected section')
   url='https://www.pcgamingwiki.com/wiki/'+quote(title.replace(' ','_'),safe=':()_-')
   records.append({'title':title,'section':str(mwparserfromhell.parse(heading).strip_code()).strip(),'text':text,'url':url,'attribution':'PCGamingWiki contributors; see linked article history','license':'CC BY-NC-SA 3.0','license_url':'https://creativecommons.org/licenses/by-nc-sa/3.0/','license_evidence':'PCGamingWiki:Copyrights revision 1286668 in the pinned archive','revision_id':page['revision'],'revision_timestamp':page['timestamp'],'page_wikitext_sha256':PINS[title][1],'section_wikitext_sha256':sha(raw),'text_sha256':sha(text),'archive_url':ARCHIVE_URL,'archive_sha256':ARCHIVE_SHA,'extraction':'Manually selected contributor-text section; markup, templates, references and transclusions omitted. Historical snapshot; technical advice may be outdated.','embedded':False})
 Path(args.output).write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in records))
 print(f'Wrote {len(records)} sections to {args.output}')
if __name__=='__main__': main()
