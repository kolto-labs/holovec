"""Publish quote-omitted contributor summaries from local review candidates.

Raw wiki sections must stay local. Exact source, cleaned and edited output
hashes are pinned. Short quotation-marked phrases are omitted; remaining prose
is secondary and does not reproduce the primary publications.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={'Lost Tribe of the Sith: Skyborn': ('15770242', 'c4ec040c2fb4954f1c0621223473b175abbbd71426dcb7f8367ac20a520229c1', 'cc5b9d22fa178f2d0bdcec9e1dd951e38b7cad0957149085188fb05f50659134', '857a230064c3e7964d3173cc816507436d112cf10945c5acc2834b45a74abd06', 'short-story', 4), 'Lost Tribe of the Sith: Paragon': ('15770246', '373a8b956463df5c7c2e8a2625abb94c6b8ba6376ccc658b66f88158e819e103', 'a7f9050b5f86cc5d96f4c7dc7317f7acb32e39b793c5e316d20a645639afb589', '78af9644edc32cbe91d24a31c00d5d5417fbf532b7ba452eaa4b67b570af7ac5', 'short-story', 5), 'Lost Tribe of the Sith: Savior': ('15770247', 'a81f13cf8d3ee7552a68b4765a5fd36ab7ab59e155a0075fdacf75f29b9eeea0', '7927645fef4327a6ff7b71425afcfa8c8ab02eae3bd5e3fcb0eac0cd947fb011', 'f526141767f928b3f946bc36007cb929f3866ab925e84e67d67b06a3c6d253f1', 'short-story', 2), 'Star Wars: The Old Republic, Blood of the Empire': ('15657616', '3ebc51bf41856e92faa66a58ec2e01394e921a543adc49df5aca5e31eeeff43c', '9dfbb0b3302d50b6055ae14bf3568e3b99aebdcbdf91112cf58613ce2cd663a8', '2ffa7c5ef8b2a3aae97f42213c27d3c2f0a56d239f2755010bc7520fab7c944d', 'webcomic-series', 1), 'Lost Tribe of the Sith: Purgatory': ('15770248', '75f49a43b33c01d47e7ad1c3bf9fc736ec359c07e4de487c51e901bbbe0698cf', 'b4b82b25aeb9b5e694022f74d5135b9780a4e58afaaef3109885295a8beca0c3', '55a7163be723d2cdb15aaaf364b193d176e7e4db0dfc42d1a36252c14010e6ca', 'short-story', 2), 'Lost Tribe of the Sith: Sentinel': ('15770249', '82fdd4152f845223bba1d05eca987b16dd8797a50e96649abf16f7350a6f051d', '56fcdc07bf299247cdba61c8b36769e00ae41ac94766be93ac18c65e28c83b48', '664c61918230ddf89f7e9bde1b934b0913bece818509d852372223e2dd0b15b1', 'short-story', 3), 'Lost Tribe of the Sith: Pantheon': ('15770250', '333bd1cd3fb28fd3659233a01afb267e76ff3ca1eba2d8d291e60e753986edc9', '2f06b17e9d62e7e5675745dc3e38906d495e947e1f073ba69f03f4026fe27a7b', 'ca731f5c8fab017a8d817ec8bc42d2a693d2808dfc8f24986cab0f01ae40a0fc', 'short-story', 8), 'Lost Tribe of the Sith: Secrets': ('15770251', '643c9f5e89559000e1a278f4a7213609541b126086ade9a866aa477550efc627', '146c2adbea9e68aaa578a17b83c12e07654d489dadde30a714675b5feba36856', '1313fc7056d8eb17e8333653fe23c218aec06c8bbb2e8c70b058aececf08e14f', 'short-story', 1), 'The Old Republic, Blood of the Empire Act 3: Burn the Future': ('14747653', '783ab7e8d9bd2fc55206b9792f22cff3567ab3bb37c9ee3f59c8eae493c44455', '15fb3e404350a729d48ff0b5e620e04fb25ded4999ae17c0354875e1ee7acf70', 'b2c65469df57f5f0649a066bd3553eaa2d1da40d49e36a9d869373896dfe546e', 'webcomic-act', 1)}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
data=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(rev,rawhash,cleanhash,outputhash,kind,expected_omissions) in sorted(PINS.items()):
 x=data[title];raw=x['raw_section'];code=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=rawhash or x['raw_wikitext_sha256']!=rawhash or x['reasons']!=['quotes_or_dialogue']:raise ValueError('source or screening changed: '+title)
 if any(str(t.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech') for t in code.filter_templates(recursive=True)):raise ValueError('quote template: '+title)
 if any(str(l.title).strip().casefold().startswith(('file:','image:')) for l in code.filter_wikilinks(recursive=True)):raise ValueError('embedded image: '+title)
 for tag in list(code.filter_tags(recursive=True)):
  if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:code.remove(tag,recursive=True)
   except ValueError:pass
 for t in list(code.filter_templates(recursive=False)):
  try:code.remove(t,recursive=True)
  except ValueError:pass
 text=code.strip_code(normalize=True,collapse=True).strip()
 if sha(text)!=cleanhash:raise ValueError('cleaned source changed: '+title)
 result,n=re.subn(r'["“][^"“”\n]{1,160}["”]','[quoted words omitted]',text)
 if n!=expected_omissions or re.search(r'["“”]',result) or sha(result)!=outputhash:raise ValueError('edited result changed: '+title)
 url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':rawhash,'cleaned_text_sha256':cleanhash,'text_sha256':outputhash,'text':result,'work_type':kind,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References and templates removed; all quotation-marked phrases replaced with [quoted words omitted].','omitted_quote_count':n,'review_status':'quote-omitted plot prose; full page and primary comic remain held','embedded':False})
Path('data/wookieepedia-publication-quote-omitted-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('Published',len(rows),'quote-omitted secondary plot sections')
