"""Recover held Arqade questions only when a licensed revision matches body and title."""
import hashlib, html, json, re, time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE = 'https://api.stackexchange.com/2.3'
FILTER = '!X-cWn5YrCQCchzB5B4*yqi7.FnN7_ijJ-pWqLgm'
session = requests.Session()
session.headers['User-Agent'] = 'HoloVec/0.1 (https://github.com/kolto-labs/holovec)'
def get(path, params):
    rows, page = [], 1
    while True:
        response = session.get(BASE + path, params={'site':'gaming','pagesize':100,'page':page,**params}, timeout=45)
        response.raise_for_status(); data = response.json()
        if data.get('error_id'): raise RuntimeError(data.get('error_name'))
        rows.extend(data['items'])
        time.sleep(max(0.2, data.get('backoff', 0)))
        if not data.get('has_more'): return rows
        page += 1
held = [r for r in json.loads(Path('evaluation/arqade-swtor-screen.json').read_text())['held'] if r['reason'] == 'unrecognized or missing post license']
ids = [r['id'].split(':')[1] for r in held if r['id'].startswith('question:')]
questions = {str(r['question_id']):r for r in get('/questions/' + ';'.join(ids), {'filter':'withbody'})}
accepted = {'CC BY-SA 2.5','CC BY-SA 3.0','CC BY-SA 4.0'}
rows, dispositions = [], []
now = int(time.time())
for ident in ids:
    post = questions.get(ident)
    if not post:
        dispositions.append({'id':'question:'+ident, 'reason':'current question unavailable'}); continue
    revisions = get('/posts/'+ident+'/revisions', {'filter':FILTER})
    matched = [r for r in revisions if r.get('content_license') in accepted and r.get('body') == post.get('body') and r.get('body') and r.get('title') == post.get('title')]
    if not matched:
        dispositions.append({'id':'question:'+ident,'reason':'no licensed revision with matching current body and title'}); continue
    rev = max(matched, key=lambda x:x['creation_date'])
    soup = BeautifulSoup(post['body'], 'html.parser'); removed = 0
    for node in list(soup.select('blockquote, q, pre, code, img, script, style')):
        if node.parent is not None: node.decompose(); removed += 1
    body = soup.get_text('\n',strip=True); title = html.unescape(post['title'])
    text, omitted = re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',title+'\n\n'+body)
    if not body.strip() or re.search(r'["“”]',text):
        dispositions.append({'id':'question:'+ident,'reason':'empty or unresolved quotation marker after screening'}); continue
    owner = post.get('owner') or {}; editor = rev.get('user') or {}
    rows.append({'id':'question:'+ident,'title':title,'url':post['link'],'question_url':post['link'],'question_id':post['question_id'],'post_type':'question','text':text,'author_name':owner.get('display_name','unknown contributor'),'author_url':owner.get('link'),'license':rev['content_license'],'license_evidence':{'basis':'API revision body and title exactly match current question','revision_guid':rev['revision_guid'],'revision_number':rev.get('revision_number'),'revision_creation_date':rev['creation_date'],'revision_url':'https://gaming.stackexchange.com/posts/'+ident+'/revisions','revision_editor_name':editor.get('display_name'),'revision_editor_url':editor.get('link')},'license_url':'https://gaming.stackexchange.com/help/licensing','source':'Arqade / Stack Exchange API','retrieved_utc':now,'creation_date':post.get('creation_date'),'last_edit_date':post.get('last_edit_date'),'score':post.get('score'),'tags':post.get('tags',[]),'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'evidence_class':'community_secondary','alterations':{'removed_html_quote_code_image_blocks':removed,'omitted_inline_quotations':omitted},'coverage':'Community contribution only; marked material removed; unmarked third-party excerpts, current game behavior and completeness are unverified.','embedded':False})
    dispositions.append({'id':'question:'+ident,'reason':'recovered','revision_guid':rev['revision_guid']})
rows.sort(key=lambda r:r['id']); out=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
Path('/tmp/holovec-arqade-revision-recovery.jsonl').write_text(out)
Path('/tmp/holovec-arqade-revision-recovery-audit.json').write_text(json.dumps({'retrieved_utc':now,'previously_held_questions':len(ids),'recovered':len(rows),'dispositions':dispositions,'output_sha256':hashlib.sha256(out.encode()).hexdigest(),'limitations':'A revision match does not establish rights in unmarked third-party excerpts or completeness. Earlier screening remains a historical snapshot.'},indent=2)+'\n')
print('Recovered',len(rows),'held',len(ids)-len(rows))
