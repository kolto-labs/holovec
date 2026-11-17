"""Build quote-omitted class biography sections from a pinned wiki archive.

Local input contains raw wiki markup. Removed: quote/dialogue templates, all
other top-level templates, inline quoted phrases, references and image links.
This is incomplete secondary prose with a limited rights screen, not game text.
"""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import quote
import mwparserfromhell
PINS={'Darth Nox':('15764225','dc86e1c080b82e6cc2efac02a311856edcebfb28e42357fb10ba49d9fd9243a2','class-sith-inquisitor','source biography uses dark-side game-mechanics template'),'Meteor (Havoc Squad)':('15807890','cb6d2570679fcbe4223f899961316ecde4f9b2b9f8ea9073c7570e340e37863b','class-trooper','source biography uses light-side game-mechanics template')}
OUTPUT_PINS={'Darth Nox — Biography introduction': '6884835aeb3113a96aaf5e28b146ca8dcb75523934bee28a3d07fa7da3857a85', 'Darth Nox — The Dashade and final trials': 'f0298a0d48fafa90b118b0c802891099ae141394ac7b772c48ea2411d84b3b99', 'Darth Nox — Apprenticeship to Zash': 'db9e92bbc11c49c36babb9563b5de7a6a6f1fe5204eb74cd14b3250152ce7374', 'Darth Nox — Defeating Darth Skotia': '27acc877ca9ad283887d6daf99df7ec51cb710921e6eeda8355c58b9ffd47642', "Darth Nox — The search for Tulak Hord's artifacts": '3e876739946da08e82fa9c57246bf58646baba2c50e44c04e77a3aca29706d90', 'Darth Nox — Balmorra': '1e056b106545ba082662b2f8435317633252177367a5e86898de10abe84e78cf', 'Darth Nox — Nar Shaddaa': 'e1dba41fe8418a5d9a5e38201a2c01c8ee109420abce771341bf6fa0342de08d', "Darth Nox — Kallig's Countenance": '5a57af2098290994c2d783c56ea1f1e5897eecebd43cc2419acb87e3e9e2c0e5', 'Darth Nox — Tatooine': '0ecccdd049438426bac089627cc81d7589770b5dfcff70f1ac7664c685b51183', 'Darth Nox — Alderaan': '7e26dd497e29d161e63958f2491f38b38a8b93b99f8eff63f644e62aa6fb4bbd', "Darth Nox — Kallig's lightsaber": 'e1fed4643b0e0eb95690d4336ed9d0b4e9e595cecfdc5de530239bb103bb7fa8', "Darth Nox — Zash's ritual": '8e6738462f35f89f0a5e66b3a5fc93dad4576aa62451a21d0d07ca1c5a7b20e4', 'Darth Nox — Force walking': 'a3333cad5f489feedb71268eeb7075d21404b3e718c18e7cb210eb0952766687', 'Darth Nox — Taris': '39f2ddd25be44cc8b30088dbb5c976215c2b5a2abf15c4f3fae30ce550986f5e', 'Darth Nox — Hoth': '6d2f55d30a878c94a4650b6bd0a9c3b31f10c680427f67975e4e06e5992b8911', 'Darth Nox — Confronting Darth Thanaton': '83837d8a5211d4f96e93c5e98f86bfebb1b6624ac0612fe62436584a63d563b2', 'Darth Nox — Locating a cure': '90aa1d5e799f548161eb058c0b8add00f3c081dfa6e5d3d6ae4c32098c5796fd', 'Darth Nox — Belsavis': 'a74fced671952a7682179ff5579d91a6a9da1a1139a0f7bd0fdc05ffa5727530', 'Darth Nox — A new ally': 'bfc29e2d7f59fd46861c16485089a7e0ed8f19a9173348f4f5965633cf334c68', 'Darth Nox — Mysteries of Voss': '9125bce80efd00b16dc12c5050fdea5349010817c9cef90cef2f294ca47a576d', 'Darth Nox — The second apprentice': '1359d736de29a4621504029b166debad79a1fbf48808359751777ba23bc5d247', 'Darth Nox — Testing the Silencer': 'e27249124bb66c34753d47044f6fdb191f51b479a1607445d14176a132bcbb39', 'Darth Nox — Final confrontation': '21191c21a8e9ff71572302dbf1006fa57d82bee6e8679895102faf6232bfb53f', 'Darth Nox — Quest for immortality': '10191d673d417ccf49f746395a60bf62de92f54b31b9913a5ffc1a276a9f6879', 'Darth Nox — The Eternal Empire conquest': 'c8c2f1fd411bf0f01916a98fa6e8e057cc7d75026ec6bc41e7d4ee22686555a3', 'Meteor (Havoc Squad) — Ord Mantell civil war': '6b0049b6332622d93d28777285972f6695004ba7f5dde7a6ba2e3587a1ffc4af', 'Meteor (Havoc Squad) — Progress on Ord Mantell': '44903a8b739a144e0a0b76e9862a91c001a330910bf30d4a166c5d3700b5285e', 'Meteor (Havoc Squad) — Promotion': '22c1baa8fcec9dd87771b5dc2103e3ba91854d470812ec69dd76e2a067382723', 'Meteor (Havoc Squad) — The hunt begins': '4b725a75397431db3de2d7136cf8ddc4ad37f7472be595e48571d13067c35c09', 'Meteor (Havoc Squad) — Phase two': '1e7873a8306b02606cf89db6b42ab73887ecc94cf0b220fcdef500ec8cb179dc', 'Meteor (Havoc Squad) — Galactic War': '31b0d95188a8374133c570d69c7b0d183a5230762684e7d1a6471ea09978feda', 'Meteor (Havoc Squad) — Eclipse': 'cbdff3166ab2700cdf3092a42fc1d28529f32853985bbb377a90a7277db4436b', 'Meteor (Havoc Squad) — Becoming Chief Military Advisor': '41fe1ab1f51fd5affab823d6260b99a00f115b8264332edab69570c62346b611', 'Meteor (Havoc Squad) — Disappearance': '5c6122df54401b2e13bc154da14eeba26feb63091743ca9a73d4f5ee69c619a2'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def words(s):return re.findall(r'\w+',s.casefold())
data=json.loads(Path(sys.argv[1]).read_text());rows=[];held=[]
for title,(rev,rawhash,work,choice) in sorted(PINS.items()):
 x=data[title];raw=x['raw_section'];code=mwparserfromhell.parse(raw)
 if x['revision_id']!=rev or sha(raw)!=rawhash or x['raw_wikitext_sha256']!=rawhash or x['reasons']!=['quotes_or_dialogue']:raise ValueError('Source or screening changed: '+title)
 sections=code.get_sections(levels=[3],include_lead=True,include_headings=True,flat=False)
 for index,s in enumerate(sections):
  rawsection=str(s);heads=[h for h in s.filter_headings(recursive=False) if h.level==3]
  if not rawsection.strip():continue
  name=str(heads[0].title).strip() if heads else 'Biography introduction'
  if heads:s.remove(heads[0])
  removed=[]
  for template in list(s.filter_templates(recursive=False)):
   if str(template.name).strip().casefold() in ('quote','quotation','blockquote','dialogue','speech'):removed.append(str(template))
   s.remove(template,recursive=True)
  for tag in list(s.filter_tags(recursive=True)):
   if str(tag.tag).casefold() in ('ref','references','gallery','blockquote','q'):
    try:s.remove(tag,recursive=True)
    except ValueError:pass
  for link in list(s.filter_wikilinks(recursive=True)):
   if str(link.title).strip().casefold().startswith(('file:','image:')):
    try:s.remove(link,recursive=True)
    except ValueError:pass
  text=s.strip_code(normalize=True,collapse=True).strip();cleanhash=sha(text)
  result,n=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',text)
  if not result:
   held.append({'title':title,'section':name,'section_wikitext_sha256':sha(rawsection),'reason':'empty after quote/template removal'});continue
  if re.search(r'["“”]',result) or 'thumb|' in result:raise ValueError('Unexpected quote, image or empty text: '+title+' / '+name)
  a=words(result);b=words(' '.join(removed));shingles={tuple(a[i:i+8]) for i in range(max(0,len(a)-7))}
  if any(tuple(b[i:i+8]) in shingles for i in range(max(0,len(b)-7))):
   held.append({'title':title,'section':name,'section_wikitext_sha256':sha(rawsection),'reason':'eight-word overlap with removed quote template'});continue
  if sha(result)!=OUTPUT_PINS[title+' — '+name]:raise ValueError('reviewed output changed: '+title+' / '+name)
  url='https://starwars.fandom.com/wiki/'+quote(title.replace(' ','_'),safe=':/()')
  rows.append({'title':title+' — '+name,'url':url,'source_revision_url':url+'?oldid='+rev,'revision_id':rev,'timestamp':x['timestamp'],'source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','section':name,'source_biography_wikitext_sha256':rawhash,'section_wikitext_sha256':sha(rawsection),'cleaned_text_sha256':cleanhash,'text_sha256':sha(result),'text':result,'inventory_work_id':work,'source_choice_assumption':choice,'evidence_class':'secondary','license':'CC BY-SA 3.0','attribution':'Wookieepedia contributors; see linked article history','continuity':'Legends','extraction':'References, templates, images and quotation-marked phrases removed; inline omissions marked [quoted words omitted].','omitted_quote_template_count':len(removed),'omitted_inline_quote_count':n,'coverage':'Partial secondary biography; class missions, alternatives, branching and updates are not complete.','embedded':False})
if len(rows)!=len(OUTPUT_PINS) or len({(r['inventory_work_id'],r['section']) for r in rows})!=len(rows):raise ValueError('Missing or duplicate sections')
Path('data/wookieepedia-swtor-class-biographies.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
Path('evaluation/swtor-class-biography-holds.json').write_text(json.dumps({'description':'Sections held after cleaning; quote overlap is a review signal, not a rights conclusion. No quote text is stored.','source_archive_sha256':'a624dfda8f09d80faeb3af744e0f601e99eeddd99eec5e465136ba519f306456','held':held},indent=2,ensure_ascii=False)+'\n')
print('Prepared',len(rows),'secondary biography sections; held',len(held))
