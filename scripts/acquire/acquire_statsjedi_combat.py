"""Acquire a bounded author-written extract from the CC BY-SA 4.0 combat guide.

Pass an already downloaded PDF. The digest pins the exact version; only section 6
is included. Source figures, tables, contact information and other sections are
not redistributed. No model inference is used.
"""
import hashlib,json,re,subprocess,sys
from pathlib import Path
pdf=Path(sys.argv[1]); digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
if digest!='8e2d67216489b78183dfe03f3bdac5934b91ec839c5c94d25c0ee6b2b830ac03': raise ValueError('Unexpected PDF version')
raw=subprocess.check_output(['pdftotext','-f','23','-l','24','-layout',str(pdf),'-']).decode('utf-8')
section=raw.split('6    Conclusions and Recommendations',1)[1].split('7     Acknowledgements',1)[0]
section=re.sub(r'(?m)^\s*23\s*$', '', section).replace('\f','\n').replace('\x1b','ff').replace('\x1c','fi')
assert all(ord(c)>=32 or c in '\n\r\t' for c in section)
items=[re.sub(r'\s+',' ',x).strip() for x in section.split('•') if x.strip()]
assert len(items)==8 and items[-1].startswith('Mission should')
text='Conclusions and Recommendations\n\n'+'\n\n'.join('• '+i for i in items)
url='https://faqs.neoseeker.com/Games/PC/star_wars_kotor_combat.pdf'
r={'title':'Star Wars: Knights of the Old Republic Combat Guide — Conclusions and Recommendations','author':'StatsJedi','source_url':url,'url':url,'version':'2.0','source_date':'2015-09-16','source_pdf_sha256':digest,'source_pages':[23,24],'license':'CC-BY-SA-4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/','attribution':'StatsJedi, Star Wars: Knights of the Old Republic Combat Guide, version 2.0 (2015), section 6, pages 23–24; adapted by extracting the section and normalizing PDF text.','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'alterations':'Extracted section 6 only, normalized line breaks and restored PDF fi/ff ligatures; figures and tables omitted.','coverage':'Independent fan combat analysis, not complete game mechanics or primary game material. Recommendations are version-specific and not independently verified; charts and supporting calculations are in the linked original. Third-party and underlying game rights are separate.','embedded':False}
Path('data/statsjedi-combat-conclusions.jsonl').write_text(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
print('Extracted',len(items),'recommendations; text SHA-256',r['text_sha256'])
