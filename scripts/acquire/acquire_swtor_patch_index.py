"""Snapshot publisher patch-index metadata, not patch-note or game text.

A list of links does not prove complete patch, story or branch coverage.
"""
import datetime,hashlib,json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
import bs4,requests
url='https://www.swtor.com/patchnotes';r=requests.get(url,headers={'User-Agent':'HoloVec/0.1 (https://github.com/kolto-labs/holovec)'},timeout=35);r.raise_for_status();s=bs4.BeautifulSoup(r.text,'html.parser');items=[];seen=set()
for a in s.select('a[href*="/patchnotes/"]'):
 href=urljoin(url,a.get('href'));parts=urlsplit(href)
 if parts.hostname not in ('www.swtor.com','swtor.com') or not parts.path.startswith('/patchnotes/'):continue
 href='https://www.swtor.com'+parts.path
 if href in seen:raise ValueError('duplicate publisher link: '+href)
 seen.add(href);label=a.get_text(' ',strip=True);d=re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b',label);date=None
 if d:
  year=int(d.group(3));year=2000+year if year<100 else year
  try:date=datetime.date(year,int(d.group(1)),int(d.group(2))).isoformat()
  except ValueError:raise ValueError('invalid publisher date: '+label)
 version=re.search(r'(?i)\b(\d+(?:\.\d+){1,3}[a-z]?)\b',label)
 items.append({'publisher_label':label,'publisher_url':href,'listed_date':date,'version':version.group(1) if version else None,'status':'publisher_index_discovery','primary_content_acquired':False,'redistribution_rights':'not_established','embedded':False})
if not items:raise ValueError('index returned no links')
listing='\n'.join(x['publisher_url']+'\t'+x['publisher_label'] for x in items)
report={'source_url':url,'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_response_sha256':hashlib.sha256(r.content).hexdigest(),'normalized_listing_sha256':hashlib.sha256(listing.encode()).hexdigest(),'scope':'Links and publisher-provided labels from the live English patch index, not the patch-note bodies. The index may omit removed, regional, pre-release or unlisted builds. Listing an update does not imply its story, data, branch or reuse rights are covered.','link_count':len(items),'dated_count':sum(v['listed_date'] is not None for v in items),'items':items}
Path('catalog/works/swtor-patchnote-index.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print('publisher index links',len(items),'dated',report['dated_count'],'normalized sha256',report['normalized_listing_sha256'])
