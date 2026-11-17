"""Extract a quote-screened wiki introduction for the Dark Lords ashcan.

Input is a locally extracted pinned XML bundle; no primary comic pages are supplied.
"""
import hashlib,json,re,sys
from pathlib import Path
import mwparserfromhell
TITLE='Tales of the Jedi: Dark Lords of the Sith Special Ashcan Edition';REV='15288048';PAGE='ffb94b794b37ecaff4ee6e38aa322ef49651894a3e7d84a97e037b22f59af308';ARCHIVE='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456'
def sh(s):
 w=re.findall(r'\w+',str(s).casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
x=json.load(open(sys.argv[1]));assert x['archive_sha256']==ARCHIVE;v=x['records'][TITLE];raw=v['raw_wikitext'];assert v['revision_id']==REV and sha(raw)==PAGE
allcode=mwparserfromhell.parse(raw);marked=[]
for t in allcode.filter_templates(recursive=True):
 if re.search(r'(?i)quote|dialog|speech|crawl|lyrics|poem',str(t.name)):marked.extend(str(p.value.strip_code()) for p in t.params)
for t in allcode.filter_tags(recursive=True):
 if str(t.tag).casefold() in ('blockquote','q','poem'):marked.append(str(t.contents.strip_code()))
lead=re.split(r'(?m)^\s*==[^=].*?==\s*$',raw,maxsplit=1)[0];c=mwparserfromhell.parse(lead)
for t in list(c.filter_templates(recursive=False)):c.remove(t,recursive=True)
for t in list(c.filter_tags(recursive=True)):
 if str(t.tag).casefold() in ('ref','references','blockquote','q','poem','gallery'):
  try:c.remove(t,recursive=True)
  except ValueError:pass
text=c.strip_code(normalize=True,collapse=True).strip();assert text and not re.search(r'["“”]',text) and not any(sh(text)&sh(x) for x in marked)
url='https://starwars.fandom.com/wiki/Tales_of_the_Jedi:_Dark_Lords_of_the_Sith_Special_Ashcan_Edition';row={'title':TITLE,'url':url,'source_revision_url':url+'?oldid='+REV,'revision_id':REV,'timestamp':v['timestamp'],'source_archive_sha256':ARCHIVE,'full_page_wikitext_sha256':PAGE,'lead_wikitext_sha256':sha(lead),'text':text,'text_sha256':sha(text),'attribution':'Wookieepedia contributors; see linked revision history','license':'CC BY-SA 3.0','evidence_class':'secondary','coverage':'Partial publication introduction; not original pages. Marked quotations and templates removed; rights in unmarked excerpts remain unverified. Page and edition fidelity require inspection.','embedded':False}
out=json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n';assert sha(out)=='31139fd1d711e36ac8066232734410c777c8171459bccd56a3cf7189fe64fd91';Path('data/wookieepedia-dark-lords-ashcan-lead.jsonl').write_text(out);print('one revision-pinned lead',len(text),'characters; output sha256',sha(out))
