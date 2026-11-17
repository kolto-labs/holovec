"""Verify publisher-stated dates for selected undated index entries.

Only metadata and response hashes are retained; no publisher prose is copied.
"""
import concurrent.futures,hashlib,json,re
from pathlib import Path
import bs4,requests
I=json.loads(Path('catalog/works/swtor-patchnote-index.json').read_text());items=I['items']
# index version, date, supporting URL, uniquely identifying date expression, date meaning
facts=[
('2.5','2013-12-03','https://www.swtor.com/galactic-starfighter',r'(?i)SUBSCRIBER\s+EARLY\s+ACCESS\s+BEGINS:\s*DECEMBER\s+3,\s*2013','subscriber early-access start'),
('2.4.0','2013-10-01','https://www.swtor.com/gameupdates/the-dread-war',r'(?i)Release Date:\s*October\s+1,\s*2013','publisher release date'),
('2.3','2013-08-06','https://www.swtor.com/patchnotes/2.3/titans-industry',r'(?i)Game Update\s+2\.3:\s*Titans of Industry\s+8/6/2013','publisher patch-page date'),
('2.2','2013-06-12','https://www.swtor.com/gameupdates/operation_nightmare',r'(?i)Release Date:\s*Part\s+1\s*\(Game Update\s+2\.2\)\s*Live\s+June\s+12,\s*2013','publisher part-one release date'),
('2.1.0','2013-05-14','https://www.swtor.com/gameupdates/customization',r'(?i)Release Date:\s*May\s+14,\s*2013','publisher release date'),
('2.0','2013-04-09','https://www.swtor.com/gameupdates/2.0-scum-and-villainy',r'(?i)Release Date:\s*April\s+9,\s*2013','publisher release date'),
('1.7.0','2013-02-12','https://www.swtor.com/gameupdates/1.7-return-of-the-gree',r'(?i)Release Date:\s*February\s+12,\s*2013','publisher release date'),
('1.6.0','2012-12-11','https://www.swtor.com/gameupdates/1.6-ancient-hypergate',r'(?i)Release Date:\s*December\s+11,\s*2012','publisher release date'),
('1.5.0','2012-11-15','https://www.swtor.com/gameupdates/1.5-hk51-activated',r'(?i)Release Date:\s*November\s+15,\s*2012','publisher release date'),
('1.4.0','2012-09-26','https://www.swtor.com/gameupdates/1.4-terror-from-beyond',r'(?i)Release Date:\s*September\s+26th,\s*2012','publisher release date'),
('1.3.0','2012-06-26','https://www.swtor.com/gameupdates/1.3-allies',r'(?i)Release Date:\s*June\s+26th,\s*2012','publisher release date'),
('1.2.0','2012-04-12','https://www.swtor.com/gameupdates/1.2-legacy',r'(?i)Release Date:\s*04\.12\.2012','publisher release date (US month-day-year notation)'),
('1.1.0','2012-01-18','https://www.swtor.com/gameupdates/1.1-rise-of-the-rakghouls',r'(?i)Release Date:\s*January\s+18,\s*2012','publisher release date')]
def check(f):
 version,date,url,pattern,meaning=f;matches=[x for x in items if x['version']==version and x['listed_date'] is None]
 if len(matches)!=1:raise ValueError('ambiguous undated index version: '+version)
 r=requests.get(url,headers={'User-Agent':'HoloVec/0.1 (https://github.com/kolto-labs/holovec)'},timeout=30);r.raise_for_status();text=bs4.BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
 if not re.search(pattern,text):raise ValueError('publisher evidence changed: '+version)
 return {'version':version,'publisher_label':matches[0]['publisher_label'],'patch_url':matches[0]['publisher_url'],'date':date,'date_meaning':meaning,'evidence_url':url,'evidence_response_sha256':hashlib.sha256(r.content).hexdigest(),'original_index_date':None}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:out=list(pool.map(check,facts))
r={'scope':'Selected explicit dates on publisher pages for 13 labels undated in the English patch index. The Galactic Starfighter date is subscriber early access, not general availability. This does not cover patch contents or all versions.','publisher_index_sha256':hashlib.sha256(Path('catalog/works/swtor-patchnote-index.json').read_bytes()).hexdigest(),'items':out}
Path('evaluation/swtor-undated-patch-release-evidence.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');print('Verified publisher date evidence for',len(out),'undated index entries')
