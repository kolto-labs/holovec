"""Acquire KOTOR-tagged Arqade questions and answers through the Stack Exchange API.

Each post is independently attributed and retains the API-reported license.
The snapshot is public community content and can change on subsequent runs.
"""
import hashlib,json,pathlib,time,requests
from bs4 import BeautifulSoup
base='https://api.stackexchange.com/2.3';session=requests.Session();session.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
def fetch(path,params):
 page=1;out=[]
 while True:
  r=session.get(base+path,params={'site':'gaming','pagesize':100,'page':page,'filter':'withbody',**params},timeout=30);r.raise_for_status();d=r.json()
  if 'error_id' in d:raise RuntimeError(str(d.get('error_name')))
  out.extend(d['items']);time.sleep(max(0.2,d.get('backoff',0)))
  if not d.get('has_more'):return out
  page+=1
questions={}
for tag in ['star-wars-kotor','star-wars-kotor-2']:
 for q in fetch('/questions',{'tagged':tag,'sort':'creation','order':'asc'}):questions[q['question_id']]=q
ids=sorted(questions);answers=[]
for i in range(0,len(ids),100):
 group=';'.join(str(x) for x in ids[i:i+100]);answers+=fetch('/questions/'+group+'/answers',{'sort':'creation','order':'asc'})
rows=[]
for kind,posts in [('question',questions.values()),('answer',answers)]:
 for item in posts:
  parent=questions[item['question_id']];ident=item['question_id'] if kind=='question' else item['answer_id'];url=parent['link'] if kind=='question' else 'https://gaming.stackexchange.com/a/'+str(ident);owner=item.get('owner') or {};license=item.get('content_license');license_evidence='tag or answer listing'
  if license not in ('CC BY-SA 2.5','CC BY-SA 3.0','CC BY-SA 4.0'):
   details=fetch('/'+('questions' if kind=='question' else 'answers')+'/'+str(ident),{})
   if details:
    if details[0].get('last_edit_date')!=item.get('last_edit_date') or details[0].get('body')!=item.get('body'):raise RuntimeError('Post changed while checking license '+str(ident))
    license=details[0].get('content_license');license_evidence='individual post lookup'
  if license not in ('CC BY-SA 2.5','CC BY-SA 3.0','CC BY-SA 4.0'):raise RuntimeError('Missing recognized license for post '+str(ident))
  body=BeautifulSoup(item.get('body',''),'html.parser').get_text('\n',strip=True);title=BeautifulSoup(parent['title'],'html.parser').get_text();text=title+'\n\n'+body
  if not body:continue
  rows.append({'id':kind+':'+str(ident),'title':title,'url':url,'question_url':parent['link'],'question_id':item['question_id'],'post_type':kind,'text':text,'body_html':item['body'],'author_name':owner.get('display_name','unknown contributor'),'author_url':owner.get('link'),'license':license,'license_evidence':license_evidence,'license_url':'https://gaming.stackexchange.com/help/licensing','source':'Arqade / Stack Exchange API','retrieved_utc':int(time.time()),'creation_date':item.get('creation_date'),'last_edit_date':item.get('last_edit_date'),'score':item.get('score'),'accepted':item.get('is_accepted'),'tags':parent.get('tags',[]),'sha256':hashlib.sha256(text.encode()).hexdigest(),'evidence_class':'community_secondary'})
rows.sort(key=lambda x:x['id']);pathlib.Path('data').mkdir(exist_ok=True);pathlib.Path('data/arqade.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows));print('questions',len(questions),'answers',len(answers),'published records',len(rows))
