"""Extract contributor prose from a pinned Essien island article; no inference."""
import hashlib,json,re,sys,mwparserfromhell
from pathlib import Path
x=json.loads(Path(sys.argv[1]).read_text())['Unidentified island (Essien)'];raw=x['raw'];sha=lambda s:hashlib.sha256(s.encode()).hexdigest()
if x['id']!='14173490' or sha(raw)!='b3cf11fc5542cbff0f20de912bce3e88df67db70756785968a4a67103196f867':raise ValueError('revision mismatch')
intro=raw.split('==Appearances==',1)[0];code=mwparserfromhell.parse(intro);qs=[]
for t in code.filter_templates(recursive=True):
 if str(t.name).strip().casefold()=='quote':qs.extend(str(p.value) for p in t.params)
for t in list(code.filter_templates(recursive=False)):code.remove(t,recursive=True)
for tag in list(code.filter_tags(recursive=True)):
 if str(tag.tag).casefold() in ('ref','references','blockquote','q'):
  try:code.remove(tag,recursive=True)
  except ValueError:pass
text=code.strip_code(normalize=True,collapse=True).strip();assert text and not re.search(r'["“”]',text)
def sh(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
assert not any(sh(text)&sh(q) for q in qs)
url='https://starwars.fandom.com/wiki/Unidentified_island_(Essien)';out={'title':'Unidentified island (Essien)','url':url,'source_url':url,'source_revision_url':url+'?oldid='+x['id'],'revision_id':x['id'],'timestamp':x['timestamp'],'source_wikitext_sha256':sha(raw),'text':text,'text_sha256':sha(text),'license':'CC BY-SA 3.0','license_url':'https://creativecommons.org/licenses/by-sa/3.0/','attribution':'Wookieepedia contributors; see linked revision history','continuity':'Legends','evidence_class':'secondary','issue_context':['kotor-war-001'],'extraction':'Templates, marked quotation, references and images omitted; exact eight-word overlap against marked quotation parameters screened.','coverage':'Contributor-written introduction; not original comic material or full story. The wiki title is conjectural. Unmarked third-party excerpts remain unverified.','embedded':False}
Path('data/wookieepedia-war-essien-island.jsonl').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True)+'\n');print('included island introduction',len(text),'characters')
