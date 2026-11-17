"""Publish reviewed introductions for previously held wiki document pages."""
import json,re,hashlib,sys,mwparserfromhell
from urllib.parse import quote
from pathlib import Path
source=json.loads(Path(sys.argv[1]).read_text());assert source['archive_sha256']=='a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456';x=source['records'];audit=json.load(open('evaluation/swtor-blog-citing-lead-review.json'))['items'];res=[]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def shingles(s):
 w=re.findall(r'\w+',s.casefold());return {tuple(w[i:i+8]) for i in range(max(0,len(w)-7))}
for item in audit:
 if item['reason']=='lead_included' or item['title']=='House Kuat':continue
 title=item['title'];v=x[title];raw=v['raw_wikitext'];assert hashlib.sha256(raw.encode()).hexdigest()==v['raw_wikitext_sha256'];c=mwparserfromhell.parse(raw);heads=list(re.finditer(r'(?m)^\s*(={2,6})\s*(.*?)\s*\1\s*$',raw));lead=raw[:heads[0].start()] if heads else raw;clean=mwparserfromhell.parse(lead)
 for t in list(clean.filter_templates(recursive=False)):clean.remove(t,recursive=True)
 for t in list(clean.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q','poem'):
   try:clean.remove(t,recursive=True)
   except ValueError:pass
 for l in list(clean.filter_wikilinks(recursive=True)):
  if str(l.title).strip().casefold().startswith(('file:','image:','category:')):
   try:clean.remove(l,recursive=True)
   except ValueError:pass
 text=clean.strip_code(normalize=True,collapse=True).strip().replace('"'+title+'"',title);text,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
 q=[]
 for t in c.filter_templates(recursive=True):
  if re.search(r'(?i)quote|dialog|crawl|lyrics|poem|scrollbox',str(t.name)):q.extend(p.value.strip_code() for p in t.params)
 for t in c.filter_tags(recursive=True):
  if str(t.tag).casefold() in ('blockquote','q','poem'):q.append(t.contents.strip_code())
 for i,h in enumerate(heads):
  if h.group(2).strip().casefold() in ("publisher's summary",'official description','opening crawl','back cover'):
   end=next((z.start() for z in heads[i+1:] if len(z.group(1))<=len(h.group(1))),len(raw));q.append(mwparserfromhell.parse(raw[h.end():end]).strip_code())
 reason='empty' if not text else 'quote_chars' if re.search(r'["“”]',text) else 'quote_overlap' if any(shingles(text)&shingles(v) for v in q) else 'candidate'
 res.append({'title':title,'reason':reason,'revision_id':v['revision_id'],'full_sha256':v['raw_wikitext_sha256'],'lead_sha256':sha(lead),'text_sha256':sha(text),'text':text,'omitted_quotes':n,'publisher_urls':v['publisher_urls']})

PINS={'Alliance Intelligence Summary 495-22': ['13873712', 'd05288e9784d13c754dcf17949270bd189bc5b8e9715ecd93aeeb9747eae39b8', '6ddc714ada2b63cdb48aa8002450801098aab67a69058239a2bc949dc1de20a9', '4b86ff6825ab19592b10c1a1e42606e54118508fde6985e3262232c4942ae248'], 'Disorder': ['15714097', '66b24c85a346bb0b210096b16543f9b3db601d2f4a2d82fda0ac8fd760bcbf16', 'f9b3b4dfde20b23965f1f8a8529ea71afff9811302c5b1f3580099943082aa51', '5a7738766b5adbc470fa4b2cb31bba2139044eaadaf6d59703ff555fd5a2ab27'], 'Field Report 875902-234MAK1': ['14389616', '3a59683bee483316cb1c7b4470f748319b50772a6bef3f5c8a2f1b9c45cf1518', 'ce2def2e9a961f97cd2095551ba45b54aa444ddcf63473d30084b3d58dee6b08', '51e7afbe27c277e7d41661bbe0ba7b20ba3e8dbe3fad01b3aec90c0028c68e02'], 'Intelligence Report: Historical Analysis of Manaan': ['15667346', 'b225ee8e8ac1a1831f6236cbbb48d652b585e92d1e8e9122c9b108e4cbeb27cc', '87e7060fa7914fda3e7b024cb2879d92540920ffb2d37fff1cd469d5eabf4ea2', '99bf8a751751561dc8189931bf4908db542b35005c6c030da44789751a3128df'], 'Mission Abstract: Investigate link between Darth Malgus and the planet Elom': ['15203174', '0979877cfb17e92533d0ecf217c57611e8d8572c1e7e2fe45db747e299d7038f', '83146ade2405c81b5f5a189f1ba270ea8c401531ad33aea2d908bc350c2c5634', 'd4ed2c52b81325fe5fa0d070db7ba443d4ea6fe674a2988b3f07832fa16a434e'], 'Tactical Report Assessment 0631.649': ['15600986', '0d5e265d3888e78909fc9201f925cdc1b12daa2757c85bdfa2b62808da0a3357', 'c04347968ffbbb3568294e24ef12388bfb813d2300cf2618a1e225582d44e549', '28e669e9226f54f65ef93a04ef99467b006b2417806b09c358c02b6f9cdf27ac'], 'Tactical Report Assessment 1522.423c': ['15600987', '7779ec595d7eaf458ce137aa9d4dd2075a226a2a7af1c0c6cd3d9184c5e88f7a', 'b5b6ede9c443120078ded4e73a4336bc73804b7464ff6d2196aaf3c17c801796', '26c31e4da19abd95214408043f3054432d15203d2f77efe072c050946c6b99e7'], 'Tactical Report Assessment DNT-1944.332': ['15600988', '53315388cb94632c0a005c6503e04ae2d60f77cfe4cc53dd565b44ef971582fc', 'd78e85e6b0339d3b9481018b8d6b35eee0495af3aa099ed409d26649d61cb5eb', '919f5c9180887f2b88a15ddae46b63f89f95858a879e9f7b6f02830626019bde'], 'Tactical Report Assessment DNT-2238.553b': ['15600989', '85982703a06f5a555b7a9a109c8a37cfb5023b3e1884b3d538f4134aa84287e9', '82f15e04428f314c7016e3a271d780024a01e2a226f7bda941dddd534f7b6c50', 'a614e62bd35faba6e3348e4f6c71d25bd31852fd62d202dd3549ef07e70633fa'], 'Tactical Report RSI-1003.106a': ['15600990', '5efe69d958516d2247011e0dd2432021dc2ef8cd805be24b7fb12308987d7af5', '2f65b755bd7f9fea1f3bfe1b3ca1475be095e03b6be64d6d8bf698c85bf17f21', '7d74c47f717eaffc21f2b6ce06c5769a2d90abbec95d16131b9b4e62a7152f77']}
rows=[]
for v in res:
 if v['reason']!='candidate' or [v['revision_id'],v['full_sha256'],v['lead_sha256'],v['text_sha256']]!=PINS.get(v['title']):raise ValueError('unreviewed or changed: '+v['title'])
 title=v['title'];u='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()');kind='real-world media description' if title in ('Disorder','Intelligence Report: Historical Analysis of Manaan','Mission Abstract: Investigate link between Darth Malgus and the planet Elom') else 'fictional document description';rows.append({'title':title+' — lead','url':u,'source_revision_url':u+'?oldid='+v['revision_id'],'revision_id':v['revision_id'],'timestamp':x[title]['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','full_page_wikitext_sha256':v['full_sha256'],'lead_wikitext_sha256':v['lead_sha256'],'text_sha256':v['text_sha256'],'text':v['text'],'cited_publisher_urls':v['publisher_urls'],'source_kind':kind,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','omitted_inline_quotations':v['omitted_quotes'],'coverage':'Short wiki-written description only; not the original report, film or short story. Unmarked excerpts and third-party rights not independently cleared.','embedded':False})
if len(rows)!=10:raise ValueError('coverage changed')
rows.sort(key=lambda x:x['title']);out=''.join(json.dumps(v,ensure_ascii=False,sort_keys=True)+'\n' for v in rows)
if sha(out)!='0e5e6c78a7a3c613ec58ce52ad8d843bfcbcca005c524e0e8c6e0130ceb640f4':raise ValueError('Output changed; review again')
Path('data/wookieepedia-swtor-blog-held-leads.jsonl').write_text(out);print('Included',len(rows),'leads; sha256',sha(out))
