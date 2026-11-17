"""Publish two source-pinned wiki leads after markup and quotation screening."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell

pins={"Quite A Story To Tell":('14740205','9bccdc2da1c07575a0c9c99873c76ec4c29f7ca84a58459f7233cfbf1de3979b','5666e6ae1cceb6e4c182604da805ec8dd5acfdcaa9c0b1b38ddc86eb477fdfdd','6a867ac11a22baaa58e071f4f9074d210db800a3702d5332140e3ad197ad3fc1'),"All That's Left":('14903299','3787b17f8a2b17596eb887c2975c13edbde9574dfcc6a5380092c7e7d4af4964','635089ed7f8446498993064615741dd7e96dd0fb01e2628d28b0814aa5ebf771','bda98a06289eb0b86cb2a005603da8bda16d0b1c78850b99779d723a4faec239')}
def sha(x):return hashlib.sha256(x.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
x=json.loads(Path(sys.argv[1]).read_text());assert set(x)==set(pins);rows=[]
for title,v in sorted(x.items()):
 raw=v['raw'];assert v['revision']==pins[title][0] and sha(raw)==pins[title][1] and v['sha256']==sha(raw)
 head=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:head[0].start()] if head else raw;c=mwparserfromhell.parse(lead)
 for n in list(c.filter_templates(recursive=False)):c.remove(n,recursive=True)
 for n in list(c.filter_tags(recursive=True)):
  if str(n.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:c.remove(n,recursive=True)
   except ValueError:pass
 text=c.strip_code(normalize=True,collapse=True).strip().replace('"'+title+'"',title)
 assert not re.search(r'["“”]',text) and sha(lead)==pins[title][2] and sha(text)==pins[title][3]
 omitted=[];parsed=mwparserfromhell.parse(raw)
 for t in parsed.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):
   omitted.extend(p.value.strip_code() for p in t.params)
 for tag in parsed.filter_tags(recursive=True):
  if str(tag.tag).casefold() in ('blockquote','q','poem'):omitted.append(tag.contents.strip_code())
 for i,h in enumerate(head):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((n.start() for n in head[i+1:] if len(n.group(1))<=len(h.group(1))),len(raw));omitted.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
 assert not any(shingles(text)&shingles(o) for o in omitted)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()');rows.append({'title':title,'url':url,'revision_id':v['revision'],'source_revision_url':url+'?oldid='+v['revision'],'timestamp':v['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':sha(raw),'lead_wikitext_sha256':sha(lead),'text_sha256':sha(text),'text':text,'license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','evidence_class':'secondary','coverage':'Contributor introduction only; empty plot summary, original story absent, unmarked third-party text rights not independently cleared.','embedded':False})
Path('data/wookieepedia-unmatched-swtor-story-leads.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows));print('Included',len(rows),'pinned unembedded leads')
