"""Reproduce quote-marker-reviewed Old Republic date/category records.
Selection is discovery, not evidence of full era or rights coverage. No model calls.
"""
import hashlib,re
import pyarrow as pa,pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
REV='5d19bba512fa8c65b225c1819d7971db316b871c';REPO='rafa-rrayes/wookieelm-corpus';PINS={'wookieepedia/A/Aratech_Repulsor_Company_Legends.md': '1201d69be9d1f7de596d5a80e7b2e1e4177d227397002bc23e9730968196ad4e', "wookieepedia/A/Asli_Krimsan's_holocron.md": '273185c38d8aed4e3c79486c83be989e0506ffb5258a63bb63d324c4aeba7627', 'wookieepedia/B/Berluk.md': '945e225a79c192a89d7898a5a1c90e1972842b0c88cccb9a7fd618f958a00c75', 'wookieepedia/C/Clan_Awaud_Legends.md': 'cb5816140de84e4659d87b625ead1e32fd0e3c91db616d5e8e291bc2ba4d02df', 'wookieepedia/D/Daimanate_officer.md': 'b05a4fc526eb385879b803e18e21240caa35846d2a312f8a1060d19a56c30fa8', 'wookieepedia/D/Daimanate_starfighter.md': 'bc257f6bbd857799a34a77ebaf30e9257f4547f09488170cde2b1c6e29f3839d', 'wookieepedia/D/Darkknell_Legends.md': '69c5f848258ee0ba5f925c1647a116c44323977cf73312622e309e3a489b6782', 'wookieepedia/D/Derrica_Praji.md': '956b07b671a1d206e442a3030c9f5e2b3240300b46efb1b96cc72ec9584a5b8d', 'wookieepedia/D/Dorvin_Eltrom.md': '4285b298fd48b61cadc49de5eddd7b956693b7acf8c43ed96d53bfcc1b45cd25', 'wookieepedia/D/Droid_Statutes.md': '146d7c1916b4d00cafc483a0462c46940fa2ae7477a0bfd4661702a863978beb', 'wookieepedia/H/High_Lord_(Circle_of_Lords).md': 'fc15ae8aab4806aa812e3ff1da07e2220bd4a67db5a7dd1f672e4967578fa11e', 'wookieepedia/M/Metanecrons.md': '0e2d4de12ef1962f3eb0ee11aa41f8228bb75f21f221ea9dda604668a9a1d35f', 'wookieepedia/M/Mrssk.md': '58a42a1c7222a2f3f792617298fc8fd9bdaf9a157183d23fee8818a320c784dd', 'wookieepedia/P/Pernicar.md': '5068b955d0c357aa1544cb5d43ecdd6c155bc55ebf6f49e89e4f7924b2b0a00f', 'wookieepedia/S/Shikkar.md': '32257f4b0525f629144b90d610df9a661e74ded0e83cb38f03f2d69d156ee2e7', 'wookieepedia/V/Verdanth.md': 'ef6af75935aed7828ed758ae0c8f79d185a4ed6801da9fe34300dec8418b1a9b'}
DATE=re.compile(r'\b(?:[1-4]\d{3}|5000)\s*BBY\b',re.I);CATEGORY=re.compile(r'\b(?:Jedi|Mandalorian|Galactic Republic|Sith|Zakuul)\b',re.I)
rows=[]
for i in range(2):
 p=hf_hub_download(REPO,f'pretrain/wookieepedia-{i:05d}-of-00002.parquet',repo_type='dataset',revision=REV)
 for b in pq.ParquetFile(p).iter_batches(batch_size=1000):
  for x in b.to_pylist():
   if x['doc_id'] not in PINS:continue
   text=x['text'] or '';digest=hashlib.sha256(text.encode()).hexdigest();dates=sorted(set(m.group() for m in DATE.finditer(text)));categories=[c for c in x['categories'] or [] if CATEGORY.search(c)]
   if digest!=PINS[x['doc_id']] or x['continuity']!='legends' or x['license']!='CC BY-SA 3.0' or not categories or not any(int(d.split()[0])%100 for d in dates) or re.search(r'(?m:^\s*>)',text):raise ValueError('changed or unsuitable record: '+x['doc_id'])
   x.update(sha256=digest,upstream_revision=REV,evidence_class='secondary',selection_categories=categories,selection_date_mentions=dates);rows.append(x)
if len(rows)!=len(PINS) or len({x['doc_id'] for x in rows})!=len(PINS):raise ValueError('missing or duplicate source rows')
rows.sort(key=lambda x:x['doc_id']);pq.write_table(pa.Table.from_pylist(rows),'data/wookieepedia-era-marker-reviewed.parquet',compression='zstd')
print('Selected',len(rows),'unembedded articles')
