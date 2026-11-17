"""Check registered source links without acquiring their content."""
import json,requests,datetime,time
sources=json.load(open('catalog/sources/source-inventory.json'));session=requests.Session();session.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
for x in sources:
 try:
  r=session.head(x['url'],allow_redirects=True,timeout=10);x['head_status']=r.status_code;x['resolved_url']=r.url
 except requests.RequestException as e:x['head_status']=None;x['error_type']=type(e).__name__
 time.sleep(.2)
out={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'note':'HEAD status is only a connectivity hint; it does not prove permission or content availability.','sources':sources}
open('catalog/sources/source-link-status.json','w').write(json.dumps(out,indent=2)+'\n')
print('checked',len(sources))
