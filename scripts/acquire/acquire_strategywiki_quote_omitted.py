"""Extract quote-omitted current StrategyWiki walkthrough alternatives.

This limited marker screen cannot establish rights for unmarked game-derived
material. Templates are stripped, so output is not a complete rendered page.
"""
import hashlib,json,re
from pathlib import Path
import requests,mwparserfromhell
PINS={'298481': ('1172091', '477b670fe5d29053390b9640421e8d8a98504f1213c24f606f9828d76d019608', 'KOTOR II'), '297539': ('1146431', '42363ce71fb710a0bac14075303232b07ade9f450b39b2dee3125d13367e2b7a', 'KOTOR II'), '297582': ('1146433', 'd856019b0a35c1d7e25f1019c6ebcbb8b5838d98b4ab8922e9f46dbd1f7c5d09', 'KOTOR II'), '175960': ('1143355', 'ea4822c176b6a0810904b6167b3e6d8e4500277d1a01ee5543bdc3ce1768e2f4', 'KOTOR II'), '237252': ('1192379', 'f1bddfd90658f12a024fb201acc7949755d16dbe91259456f9561841ed524ab5', 'KOTOR II'), '237158': ('1146436', 'e92be757a904c04ff6e0cfc049ba632114cda791f79d9f19d397bd5e9c2ddb73', 'KOTOR II'), '235284': ('1146538', 'dadf50b638be682410f2a02cb9f76ec8e706e67d0f118e484aa1a1f7697baa6e', 'KOTOR II'), '243792': ('1172094', '1a4e7a974ef786d359264af3cdc7bf5da2d2d137a3b92045e5b2d8a695b39b06', 'KOTOR II'), '291411': ('1146581', '034c7c273d9d13b60d82dc5f30b14b5ecb1c53c260bea74a26667c0aa26bea44', 'KOTOR II'), '211950': ('1146568', 'e58a958e3d7b3109f38af5d9aee9056fe42572ab7004b342b1d66448750f46cc', 'KOTOR II'), '259173': ('1138820', '6f570fa8b1687099868bb3d60fa393172ba5e65ea200f9a3e8c72e097627dde0', 'KOTOR II'), '298066': ('1137889', '7581759cda4f50bd7cb6640caeb922021e017ef1611277717e4ad2e0abfecdd7', 'KOTOR II'), '298373': ('1167854', '2d7cb2c2b6e89ea95497cd49bbe0dfd023edd09c40ce8783021419769e016e60', 'KOTOR II'), '235154': ('1174110', '127bc11ae0456170d60017b404a3707de3f984dfb6f1500ab9630066753c2179', 'KOTOR II'), '301378': ('1146600', 'fc622c78e8609acf46693620303fa236d57ae8dce7dad94a7b2002043dbf2577', 'KOTOR II'), '331338': ('1156211', 'ea2efb02fb614b4b51f1fa42435b2edbb9ddc46bd2c665d924e0a6ee2e0384de', 'KOTOR II'), '301420': ('1141216', 'c2a4d2927f8f3c7a4a0db067ccca761d8224c519adaefc425ad07aacf153e5a5', 'KOTOR II'), '241849': ('1191248', 'b8f0cffba99b82c3e8f3a43e7d479f539f90f2d658fe59f00ac7bd42c4766af8', 'KOTOR II'), '195612': ('1183702', '927c9786b53cd72e668d71d91274943ee969c97d5458500f621b9e84ce411a54', 'KOTOR I'), '185342': ('1189514', '96e67e6eeb13937ecc7a81dcded1dbd444162e0f25d3ca15ca63a0d270f69168', 'KOTOR I'), '202168': ('1192340', 'b7831be804a9f83905fc85bfc9ac5b81b30d04fda965c5041494f4ecc2b5b17f', 'KOTOR I'), '233319': ('1143034', '30f28bcb1775f87cc3039f2d1538c1b3b160ab62551be7beb2d3c32038873e5d', 'KOTOR I'), '185537': ('1148516', '3be7d4179ccdaf1e23732b828e6632c6a3c4b7b245bc8b64e6f68eef097f8d05', 'KOTOR I'), '214087': ('1176879', '64f8747915f8133786f4740805414ec97ce2dda98ef10d7da4143cc0ef4b7eb3', 'KOTOR I'), '217324': ('1183741', '29cc6b9509ed0fa1c8188f106db736fd57418d86145691d7c9d9fef3de5c325d', 'KOTOR I'), '169619': ('1145491', '55b695cdad9bf53011cc07f27da3f9649f19a9fe7a5dcae1a84cd2e8626cde7a', 'KOTOR I'), '213156': ('1171456', '903d4ea7322349c2d3447e01214c16ed729297fde3036040d4680f72bdf29dca', 'KOTOR I'), '186463': ('1143104', '87fa4ff3405b240b6ce63b49d825c1d3d8ddd26ebb7c544e485e9325c43fbfe7', 'KOTOR I'), '169743': ('1192865', '10a717801a9e4a6ddf27740be552604c63cdb324b7756b9a6cb45c3a683290fb', 'KOTOR I'), '185624': ('1189905', 'e05bca3806b1c5d59cc9ce2e92e194819e86c341ae21faf286397852b0f8b37e', 'KOTOR I'), '71718': ('1186231', '2e0786e16f10a49b4e76ca15b55c4f3d5ce10b2428e10bb74aa1033063aed833', 'KOTOR I'), '213524': ('1180306', '894363c304cedc057a162e840acf3a26daf17296bff701f86c52f3164236f36f', 'KOTOR I'), '184121': ('1175971', 'f7cfcca155a6170307974e305ae830060aa03b7919dca22b11514ede8ff14331', 'KOTOR I'), '207377': ('1196980', 'ce4eed6c21be26508eb2467f6fd94f1fb6b6e29848b98f36da14310f0d0c7fd2', 'KOTOR I'), '185352': ('1142751', '3b5bdaadf63716c4fb222a32d86545d20d95468ec5d004e2c1ddfe21ba0ca52b', 'KOTOR I'), '185351': ('1189765', '4c87163bac796ae9252c43d9cb145c82517d3f14e5be38dc83fce25bf8a1ec28', 'KOTOR I'), '195536': ('1147563', 'c2495452af25a5ee7dde443471b4dccb1943ae2c7e452d6b44c464c5c583081b', 'KOTOR I'), '205925': ('1183734', '50311aaa44fad696043b50f627ea01129522d68bb078546989425be84573bf21', 'KOTOR I')}
s=requests.Session();s.headers['User-Agent']='HoloVec/0.1 (https://github.com/kolto-labs/holovec)';r=s.get('https://strategywiki.org/w/api.php',params={'action':'query','format':'json','formatversion':2,'prop':'revisions|info','rvprop':'ids|timestamp|content','rvslots':'main','inprop':'url','revids':'|'.join(x[0] for x in PINS.values())},timeout=40);r.raise_for_status();pages=r.json()['query']['pages'];old={str(x['page_id']):x for x in map(json.loads,open('data/strategywiki.jsonl'))};rows=[];held=[]
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
for page in pages:
 pid=str(page['pageid']);rev,rawhash,game=PINS[pid];v=page['revisions'][0];raw=v['slots']['main']['content'];c=mwparserfromhell.parse(raw)
 if str(v['revid'])!=rev or sha(raw)!=rawhash:raise ValueError('source mismatch')
 quote_names=re.compile(r'quote|dialog|crawl|game.?text',re.I)
 risky=[t for t in c.filter_templates(recursive=True) if quote_names.search(str(t.name))]
 quote_text=[]
 for t in risky:
  for parameter in t.params:quote_text.append(str(parameter.value.strip_code(normalize=True,collapse=True)))
 def shingles(value):
  words=re.findall(r'\w+',value.casefold());return {tuple(words[i:i+8]) for i in range(max(0,len(words)-7))}
 qset=set().union(*(shingles(q) for q in quote_text)) if quote_text else set()
 for t in list(c.filter_templates(recursive=False)):
  if quote_names.search(str(t.name)):c.remove(t,recursive=True)
 for t in list(c.filter_tags(recursive=True)):
  if str(t.tag).casefold() in ('ref','references','gallery','blockquote','q'):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 for t in list(c.filter_wikilinks(recursive=True)):
  if str(t.title).strip().casefold().startswith(('file:','image:')):
   try:c.remove(t,recursive=True)
   except ValueError:pass
 clean=c.strip_code(normalize=True,collapse=True).strip()
 text,omitted=re.subn(r'["“][^"“”\n]{1,300}["”]','[quoted words omitted]',clean)
 reason='empty' if not text else 'unresolved quotation marks' if re.search(r'["“”]',text) else 'eight-word overlap with removed quote or dialogue template' if shingles(text)&qset else None
 if reason:
  held.append({'page_id':int(pid),'title':page['title'],'revision_id':rev,'page_wikitext_sha256':rawhash,'reason':reason});continue
 prior=old[pid];row={'title':page['title'],'url':page['fullurl'],'source_revision_url':'https://strategywiki.org/w/index.php?oldid='+rev,'page_id':page['pageid'],'revision_id':rev,'timestamp':v['timestamp'],'page_wikitext_sha256':rawhash,'text_sha256':sha(text),'text':text,'compares_to_snapshot_revision':prior['revision'],'compares_to_snapshot_text_sha256':prior['sha256'],'license':'CC BY-SA 4.0; contributions prior to 1 October 2024 may be CC BY-SA 3.0; third-party material may have separate terms','attribution':'StrategyWiki contributors; see linked article revision history','game':game,'continuity':'game guide','evidence_class':'secondary_walkthrough','extraction':'References, galleries, images, marked quote/dialogue/crawl/game-text templates and quotation-marked phrases removed; template code stripped without rendering. Eight-word overlap checked against removed template parameter text.', 'omitted_inline_quotations':omitted,'risky_templates_detected':len(risky),'coverage':'Partial guide text; templates, game excerpts, rendered tables, choices and complete game content are not established. The earlier source snapshot remains separately available.','embedded':False};rows.append(row)
rows.sort(key=lambda x:x['page_id'])
if {str(x['page_id']) for x in rows}|{str(x['page_id']) for x in held}!=set(PINS):raise ValueError('Missing pages')
output=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
if sha(output)!='ace2024b2bba4b8d3f794dd4369095b00f3f3a22faef5fe5bd2cd9b0d87c0651':raise ValueError('Output changed; re-screen before release')
Path('data/strategywiki-quote-omitted-walkthroughs.jsonl').write_text(output);print('prepared',len(rows),'quote-omitted walkthroughs',[(x['page_id'],x['text_sha256']) for x in rows])

Path('evaluation/strategywiki-quote-omitted-holds.json').write_text(json.dumps({'description':'Sections held by limited markup and quotation-overlap screen; no source text retained. Not rights clearance.','included':len(rows),'held':held},indent=2,ensure_ascii=False)+'\n')
print('held',len(held),[(h['page_id'],h['reason']) for h in held])
