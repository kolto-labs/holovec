"""Acquire screened, attributed Science Fiction & Fantasy Old Republic Q&A via the Stack Exchange API.

Stack Exchange licensing: https://scifi.stackexchange.com/help/licensing
API method: https://api.stackexchange.com/docs/questions
Marked quote blocks, code blocks and quotation-marked text are omitted. This
cannot establish rights in unmarked third-party material; this is a live,
incomplete community snapshot, not game dialogue or a complete mission list.
"""
import hashlib,html,json,re,time,requests
from pathlib import Path
from bs4 import BeautifulSoup
BASE='https://api.stackexchange.com/2.3'; session=requests.Session();session.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';meta={'requests':0,'minimum_quota':None}
def fetch(path,params):
 out=[];page=1
 while True:
  r=session.get(BASE+path,params={'site':'scifi','pagesize':100,'page':page,'filter':'withbody',**params},timeout=45);r.raise_for_status();d=r.json();meta['requests']+=1
  if 'error_id' in d:raise RuntimeError('API error '+str(d.get('error_name')))
  if d.get('quota_remaining') is not None:meta['minimum_quota']=min(meta['minimum_quota'] or d['quota_remaining'],d['quota_remaining'])
  out.extend(d['items']);time.sleep(max(0.2,d.get('backoff',0)))
  if not d.get('has_more'):return out
  page+=1
questions={}
for tag in ['star-wars-the-old-republic','darth-bane']:
 for q in fetch('/questions',{'tagged':tag,'sort':'creation','order':'asc'}):questions[q['question_id']]=q
ids=sorted(questions);answers=[]
for i in range(0,len(ids),100):answers.extend(fetch('/questions/'+';'.join(map(str,ids[i:i+100]))+'/answers',{'sort':'creation','order':'asc'}))
accepted={'CC BY-SA 2.5','CC BY-SA 3.0','CC BY-SA 4.0'}
# The list endpoint occasionally omits licenses. Check individual posts in batches
# and accept a license only when the body and last-edit timestamp still match.
for kind,posts,key in [('questions',list(questions.values()),'question_id'),('answers',answers,'answer_id')]:
 missing={p[key]:p for p in posts if p.get('content_license') not in accepted}
 for i in range(0,len(missing),100):
  detail=fetch('/'+kind+'/'+';'.join(map(str,list(missing)[i:i+100])),{})
  for d in detail:
   original=missing[d[key]]
   if d.get('body')==original.get('body') and d.get('last_edit_date')==original.get('last_edit_date') and d.get('content_license') in accepted:original['content_license']=d['content_license'];original['_license_evidence']='individual batch lookup'
existing=set();rows=[];held=[];now=int(time.time())
for kind,posts in [('question',questions.values()),('answer',answers)]:
 for post in posts:
  parent=questions[post['question_id']];ident=post['question_id'] if kind=='question' else post['answer_id'];pid='scifi:'+kind+':'+str(ident)
  if pid in existing:held.append({'id':pid,'reason':'already present'});continue
  lic=post.get('content_license')
  if lic not in accepted:held.append({'id':pid,'reason':'unrecognized or missing post license'});continue
  soup=BeautifulSoup(post.get('body',''),'html.parser');removed=0
  for node in list(soup.select('blockquote, q, pre, code, img, script, style')):
   if node.parent is not None:node.decompose();removed+=1
  body=soup.get_text('\n',strip=True);title=html.unescape(parent['title']);text=title+'\n\n'+body
  text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
  if not body.strip():held.append({'id':pid,'reason':'empty after marked material removal'});continue
  if re.search(r'["“”]',text):held.append({'id':pid,'reason':'unresolved quotation marker'});continue
  owner=post.get('owner') or {};url=parent['link'] if kind=='question' else 'https://scifi.stackexchange.com/a/'+str(ident)
  rows.append({'id':pid,'title':title,'url':url,'question_url':parent['link'],'question_id':post['question_id'],'post_type':kind,'text':text,'author_name':owner.get('display_name','unknown contributor'),'author_url':owner.get('link'),'license':lic,'license_evidence':post.get('_license_evidence','tag or answer listing'),'license_url':'https://scifi.stackexchange.com/help/licensing','source':'Science Fiction & Fantasy Stack Exchange API','retrieved_utc':now,'creation_date':post.get('creation_date'),'last_edit_date':post.get('last_edit_date'),'score':post.get('score'),'accepted':post.get('is_accepted'),'tags':parent.get('tags',[]),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'scope':'Old Republic-tagged or adjacent Darth Bane discussion; canon and Legends require review','evidence_class':'community_secondary','alterations':{'removed_html_quote_code_image_blocks':removed,'omitted_inline_quotations':n},'coverage':'Community contribution only; marked material removed; unmarked third-party excerpts, current game behavior and completeness are unverified.','embedded':False})
rows.sort(key=lambda r:r['id']);out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows);Path('/tmp/holovec-scifi-old-republic-candidates.jsonl').write_text(out);Path('/tmp/holovec-scifi-old-republic-screen.json').write_text(json.dumps({'source_tags':['star-wars-the-old-republic','darth-bane'],'retrieved_utc':now,'questions_retrieved':len(questions),'answers_retrieved':len(answers),'published_candidates':len(rows),'held':held,'api':meta,'output_sha256':hashlib.sha256(out.encode()).hexdigest(),'limitations':'Live public tag snapshot; marked-material screening is incomplete and does not determine unmarked quotation rights, latest game behavior, deleted posts or completeness.'},indent=2)+'\n');print('Questions',len(questions),'answers',len(answers),'candidates',len(rows),'held',len(held),'quota',meta['minimum_quota'],'sha256',hashlib.sha256(out.encode()).hexdigest())
