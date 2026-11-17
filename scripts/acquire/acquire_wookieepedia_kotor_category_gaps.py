"""Recover pinned category-selected KOTOR-era wiki articles.

Selection by category and simple quote markers does not establish relevance,
complete coverage, or rights for unmarked third-party excerpts.
"""
import hashlib,json,re
from pathlib import Path
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from wiki_rights_filter import requires_review
REV='5d19bba512fa8c65b225c1819d7971db316b871c';REPO='rafa-rrayes/wookieelm-corpus'
PINS={'wookieepedia/A/Acklay_Legends.md': '4b1525fefa5ebb0ae0978a935cb1a8664b5d79bb0dd2d8930c292a51cfd44f42', 'wookieepedia/A/Asset_I-29.md': '28967cf2884fbe6c889fef7836c382286d35fd76d7f9fea7c42bdc13c4aab8a0', "wookieepedia/C/Ceh'let.md": '15a48eee227db5c055a56551fff17e77c029e3618c7324f8a7cd3c00079d7557', 'wookieepedia/D/Daritha.md': '61e9f8f89ae9b052756bc4e0a82c9536ecf68724dcd14c686b7b1abccccdf95e', 'wookieepedia/E/Expedition_to_Lehon.md': 'e5ae68485a8c3a094af0bc594735bb8f8d23453cfdcbaefa42b231db00a4e52f', 'wookieepedia/F/Fitomp.md': '242898d6d6dbc8cbf34f8d976bbf387684b7c5c0a29393548faf75e5f7cf94c4', 'wookieepedia/G/Griwstrick.md': 'eecd0dba197aac8ccb9634e0194c725ead55059b72658bf5c4217e2f8071833c', 'wookieepedia/M/Makatak_tribe.md': '31b0ed35b5c90aa04ff9ff04eff900d0ca39dc3f05d4eaf14967c40c8e2e64b6', 'wookieepedia/M/Malata.md': 'b84ea60eb86d3ab423ca797be01ef24ee92ce8fe4996f7b62119ff3d4a1b5860', "wookieepedia/O/Ore'mun.md": 'df88c95b0d050c5ab2bdca047bef579df7f22e3982993cf31853f37894de49b2', 'wookieepedia/P/Persappa.md': 'b0a967211c63febd9b922e31c78ab3197b8da25bbaba5a1c78388487dcd25cc4', 'wookieepedia/R/Rakatan_Archipelago.md': '2765db133313652694689f4f9eee85c0e0ddb6214685ec4c505d68f6a7141bc6', 'wookieepedia/R/Ruthic.md': '82d00c270328cec5b3453bdf0fde0d3f8c22fd0319372367e2776ac4331de015', "wookieepedia/S/Skal'nas.md": 'c359bd5d19c696a20bf10ea765f383cd6ab93c556762a9bd45d08261955ca94e', 'wookieepedia/S/Star_Forge_(Makatak).md': '3da9570736cc3179af6aa9ad0b7f2fcf4c077f45b5b9b34938f3df2b5a239c40', 'wookieepedia/S/Star_Forge_(Tulpaa).md': '4fc5c581be23f52d6ab7e744979d93192135524944a518a5ceb74462bcf3c611', "wookieepedia/T/Tul'kar.md": 'ded39b1a460eac7fa936995ce8087e4654518baccd8592e9555c599e6d8541d5', 'wookieepedia/T/Tulpaa.md': 'a80c01b1b514add812786f816469fdd7961afe7a06ecee56ab4adc39015ec359', 'wookieepedia/T/Tulpaa_tribe.md': '5107227405791c07378e14f86306cdfe70dbcc9a99022cd678982aa87b138192'}
PAT=re.compile(r'(?i)\b(?:revanchists|revanites|(?:darth )?revan.s sith empire|jedi civil war|mandalorian wars|rakata(?:n)?|tarisian outcasts)\b')
rows=[]
for i in range(2):
 path=hf_hub_download(REPO,f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV)
 for batch in pq.ParquetFile(path).iter_batches(batch_size=2048):
  for x in batch.to_pylist():
   if x['doc_id'] not in PINS:continue
   text=x['text'] or '';digest=hashlib.sha256(text.encode()).hexdigest();cats=[c for c in x['categories'] or [] if PAT.search(c)]
   if digest!=PINS[x['doc_id']] or x['continuity']!='legends' or not cats or not text or re.search(r'["“”]|(?m:^\s*>)',text) or requires_review(text):raise ValueError('source or screen changed: '+x['doc_id'])
   x.update(sha256=digest,upstream_repository=REPO,upstream_revision=REV,evidence_class='secondary',selection_categories=cats,license='CC BY-SA 3.0 (wiki contributor text; third-party material may have separate terms)',attribution='Wookieepedia contributors; see linked article history',embedded=False)
   rows.append(x)
if len(rows)!=len(PINS) or len({r['doc_id'] for r in rows})!=len(PINS):raise ValueError('missing or duplicate')
rows.sort(key=lambda x:x['doc_id']);output=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
if hashlib.sha256(output.encode()).hexdigest()!='87d0c185ecbb375614ad764d4b75dc2f813f1ecb51b19798b2f0e77c7e169ce4':raise ValueError('Output changed; re-screen before release')
Path('data/wookieepedia-kotor-era-category-gaps.jsonl').write_text(output);print('selected',len(rows),'unembedded category records')
