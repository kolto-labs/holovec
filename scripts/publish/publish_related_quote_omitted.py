"""Publish quote-omitted contributor summaries from local review candidates.

Raw wiki sections must stay local. Exact source, cleaned and edited output
hashes are pinned. Short quotation-marked phrases are omitted; remaining prose
is secondary and does not reproduce the primary comics.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={'Knight Errant 5': ('14920203', 'c090a5861b0c5df51029258d5ec6476d912b49d088ac0d55264f7766217cb22f', '42d55831362bc629bb0f8f2713feb61dbd4b01a8fdf43206195ca5b77b395c4c', 'f46e1cb4a949cd54497adab1e77abdd06d8108bcd3f237c2a43d30d328326fc9', 'knight-errant-005', 2), 'The Old Republic — The Lost Suns 1': ('15552386', 'b5c1828348cf84e9288270b5981e1b54bdffe086ecfe0ae17c2bb251ee0cbbdd', 'c7d62690d1ef4ab527aad75dcd7dbbe815fe5c8da41edf0edcf12c4ba8315828', 'd085736c4c7fe35870934e546ee0acd6641e1c169d3118c6fa7ef61d7a8c2155', 'tor-lost-suns-001', 2), 'Knight Errant: Deluge 2': ('14908974', '75ba7f9da61d6565d255343f576d5eeef2ecc994390f34b62ce859eec4bc6e96', 'c38154c7334474c75544e35e869890431a6db9af34c5b8e1026b85781c384d8d', '62e33e236b8c25ef1cc4bb303ea993dd4a862323eeae686da62cbd0f10494254', 'knight-errant-deluge-002', 1), 'Knight Errant: Deluge 5': ('14908975', '9f0125ca12d470ed872bf44073e4fa94337795b843244e0a866ccf7270caefa1', '157da12147504d5994b84915009dab032aa333010485781a84323d44912265c3', 'b5818791b8305d41a3f886bbb4ace323e6564b89199f3d08704a6874131cbc16', 'knight-errant-deluge-005', 1), 'The Old Republic — The Lost Suns 3': ('15552388', 'd465d596c30016d7849ab3791456090fb58f31d9ed6a65c13692937c2e11f9ae', 'a6617ba83ae96d8ced6e4edaa0ffddb26a2308f7aa0191513158998a637729ff', 'c206139294bc97591099ecfbeed2bb76d63af8a6abe0dd2a4c0d70892bc1c01d', 'tor-lost-suns-003', 3), 'Knight Errant: Escape 1': ('15426393', '02b05ea47444e2e7f4de7f3d2c11e48e23bd40f6298df7af3b5cebec68c0df12', '89b9420fcbcc8ae027e16f60fe8e247f0d51ebbc1bd35369717cb30f9afde9db', 'cefff3b598f80234b0b68a466b9dc46812655640f2e1cebe8fc7ede6189cfbb3', 'knight-errant-escape-001', 1), 'Knight Errant: Escape 2': ('14738374', 'e01dacdb0635d4c4619cc9d8c763792e09fb5aa9f319732a9b163ab6fefc59e2', '68ee2f3cf557850edc1299b0e96be5096f482123308b4702aae9258fbe5dbbc9', '3f70fe35719d9a6f2ce86346b1b47cc66fd3fe0dd7d93c2cec168297f2f8caea', 'knight-errant-escape-002', 1), 'Lost Tribe of the Sith — Spiral 1': ('15253712', '374f3bb2865632b8fe2fa6bdc65e935df6c577e563a92c8821681bae97c43700', 'aa89db3cb0c32b039e6150e9c34ad8227317f77a862dd7b94e28067b5ad4cd80', 'a8b804298ea9aa8e09826f9696f757364c17f7e668b90d532e0005378589a90c', 'lost-tribe-spiral-001', 1), 'Knight Errant: Escape 5': ('14738377', 'a088cb8cf07f0c09e763aa7e7cb2d58aef4747172afb83b7036fac5be0673a9e', 'd6fa8ad6197a785ac049c17c4c97b4dc7d0183fa0cbef4bdd3ff20deaa9186aa', '52059c4423130f1edf28700d939ff8b7ea9ecdac36e943faa62072b0cf54803c', 'knight-errant-escape-005', 1), 'Lost Tribe of the Sith — Spiral 5': ('14739217', '7b7b5d6e89974293a39708f1b6d5e791a36a5a3748440019f505497bf158e5bb', 'ea701b29e3c74474777f8690df69fcc8f241d19996268e54733d1d30ecf0cfe5', 'b114f92280360d302157072c6e824b48ee954d7f097aeddc819d35aff1ef4403', 'lost-tribe-spiral-005', 1)}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
data=json.loads(Path(sys.argv[1]).read_text());rows=[]
for title,(rev,rawhash,cleanhash,outputhash,work,expected_omissions) in sorted(PINS.items()):
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
 rows.append({'title':title,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':'Plot summary','raw_wikitext_sha256':rawhash,'cleaned_text_sha256':cleanhash,'text_sha256':outputhash,'text':result,'inventory_work_id':work,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References and templates removed; all quotation-marked phrases replaced with [quoted words omitted].','omitted_quote_count':n,'review_status':'quote-omitted plot prose; full page and primary comic remain held','embedded':False})
Path('data/wookieepedia-related-quote-omitted-plots.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
print('Published',len(rows),'quote-omitted secondary plot sections')
