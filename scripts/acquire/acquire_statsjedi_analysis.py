"""Extract author-written analysis from a hash-pinned CC BY-SA combat guide.

Figures, figure captions, tables, formulas and other sections are omitted. This
is not a transcription of game content, nor a verification of analysis claims.
"""
import hashlib,json,re,subprocess,sys
from pathlib import Path
pdf=Path(sys.argv[1]);digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
if digest!='8e2d67216489b78183dfe03f3bdac5934b91ec839c5c94d25c0ee6b2b830ac03':raise ValueError('Unexpected source version')
raw=subprocess.check_output(['pdftotext','-f','11','-l','23','-layout',str(pdf),'-']).decode('utf8')
raw=raw.split('4     Model Analysis and Results',1)[1].split('5    Enemy Defense and Savings Throws',1)[0]
raw=raw.replace('\x15','—').replace('\x1b','ff').replace('\x1c','fi').replace('\x1e','ffi')
assert all(ord(c)>=32 or c in '\n\r\t\f' for c in raw)
raw=re.sub(r'(?m)^\s*Figure \d+:.*(?:\noptimized)?\s*$', '\n',raw)
raw=re.sub(r'(?m)^\s*(?:1[1-9]|2[0-2])\s*$', '',raw).replace('\f','\n')
parts=re.split(r'(?m)^4\.([1-5])\s+',raw);assert len(parts)==11
rows=[];page_ranges=[[11,12],[12,15],[15,18],[18,22],[22,22]];url='https://faqs.neoseeker.com/Games/PC/star_wars_kotor_combat.pdf'
for j in range(5):
 number,body=parts[1+j*2:3+j*2];body=body.strip();paragraphs=[re.sub(r'\s+',' ',p).strip() for p in re.split(r'\n\s*\n',body) if p.strip()];text='\n\n'.join(paragraphs)
 assert len(text)>200 and 'Figure 22:' not in text and 'Figure 23:' not in text
 rows.append({'title':'StatsJedi KOTOR combat analysis — section 4.'+number,'author':'StatsJedi','url':url,'source_url':url,'version':'2.0','source_date':'2015-09-16','source_pdf_sha256':digest,'source_pages':page_ranges[j],'license':'CC-BY-SA-4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/','attribution':'StatsJedi, Star Wars: Knights of the Old Republic Combat Guide, version 2.0 (2015), section 4.'+number+'; extracted and normalized.','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'alterations':'Extracted section prose; omitted figures and captions, removed page numbers, normalized line breaks, restored PDF fi/ff/ffi ligatures and dash characters.','coverage':'Independent fan analysis; figures are not included and referenced graphs remain in the original. Claims and game-version applicability are not independently verified; game and third-party rights are separate.','embedded':False})
Path('data/statsjedi-combat-analysis.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows));print('Extracted',len(rows),'analysis sections',sum(len(r['text']) for r in rows),'characters')
