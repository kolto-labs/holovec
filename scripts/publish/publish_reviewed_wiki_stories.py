"""Publish specifically inspected wiki plot sections from local review candidates.

Exact revisions and text hashes are pinned; content changes require review.
These are secondary summaries, not full stories or an exhaustive corpus.
"""
import hashlib,json,sys
from pathlib import Path
APPROVED={
 'Star Wars: Knights of the Old Republic: Daze of Hate':('14744353','c73086d2785cdb86a424ef43584478442bfb119f0b31c069b26885d70c66ad75','comic-arc'),
 'The Old Republic, Blood of the Empire Act 1: Shades of the Sith':('15824598','99ca277ddc290fb99009d63257b935cf1e93b3ff222735a19e572666f2a84cb0','webcomic-act'),
 'The Old Republic, Blood of the Empire Act 2: The Broken World':('15022353','16813f4401a2d9710b45f0431b925875c26235e61a33b41bb8045bdb6d7fe059','webcomic-act'),
 'Star Wars: Tales of the Jedi – The Golden Age of the Sith (trade paperback)':('14780995','6bdac167dc2c3724ac3d9c55aa3741d284403ca8597af2753103bc81d62fabde','comic-collection'),
 'The Betrayal of Darth Revan':('15324986','6966689e8f9c32c6ea5348e13fa54b0fd08e8ac2285f35d8582221f1d509a8d7','tabletop-adventure'),
 'Lost Tribe of the Sith: Precipice':('15770241','35b2f9ea07392d30a92fa512e444428d4e4be79ac23ac7a23e4e3d732c783a11','short-story'),
 'The Old Republic: Deceived':('15695273','e32631980d4969fcbb31d735f891a9e9fc72503d9bda26c2caef275a50ab5fa5','novel'),
 'Knight Errant (novel)':('15588052','6140b5ff4524773194e41ad650029232651261b92a69949c9c7880eafeed3514','novel'),
 'The Old Republic: Revan':('15731881','a843ff8b149dcf856767789137a0b7fbc539279c97bec66b5d07e6a63862b22c','novel'),
 'Snare (short story)':('15617275','1ae03d0a403ee0aeff2ab5e9d50fbd5d65832add1f158c6364e5deeab3bdc5d4','short-story'),
 'Star Wars: Tales of the Jedi – The Golden Age of the Sith':('15551346','1a9dff3dd0fa327ba016cc2d2cf260c91c5d855797481030a9a96c4c1be7c5fd','comic-series'),
 'Red Harvest (novel)':('15668901','46558011de0334b6bd0bcb052838b2f3e79840c14c259bff5e8ae5b3dcc477f8','novel'),
 'Bottled Fury':('15720535','49c9497a2484956eb47c3f8fa1a32bfc2f2b82cd56064ec06e89b5de33b701ae','short-story'),
}
rows={}
for line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
 x=json.loads(line)
 if x['title'] not in APPROVED:continue
 rev,digest,kind=APPROVED[x['title']]
 if x['revision_id']!=rev or hashlib.sha256(x['text'].encode()).hexdigest()!=digest or x['text_sha256']!=digest:raise ValueError('reviewed source changed: '+x['title'])
 x.update(work_type=kind,evidence_class='secondary',license='CC BY-SA 3.0',attribution='Wookieepedia contributors; see linked article history',source_revision_url=x['url']+'?oldid='+rev,review_status='plot section inspected; full article remains held',continuity='unclassified')
 x.pop('status',None);rows[x['title']]=x
if set(rows)!=set(APPROVED):raise ValueError('missing reviewed candidates')
with Path('data/wookieepedia-reviewed-story-plots.jsonl').open('w',encoding='utf-8',newline='\n') as f:
 for title in sorted(rows):f.write(json.dumps(rows[title],ensure_ascii=False,sort_keys=True)+'\n')
print('reviewed story plot sections:',len(rows))
