"""Build the small manually inspected CC BY-SA wiki plot-section snapshot.

Input must be produced locally by prepare_wiki_plot_review.py. Exact source
revision and output hashes are pinned; changed content requires a new review.
The full flagged pages remain held, and this is not a general rights clearance.
"""
import hashlib,json,sys
from pathlib import Path
APPROVED={
 'Dawn of the Jedi: Force Storm 5':('15804918','de7ba2a6345f10899ccec3b3f28522d8f55ed0204ebdce2baae0f8c736a8e0f7','dawn-force-storm-005'),
 'Knight Errant 0':('14738361','e29b4ad4f22ae2f6661516cc0514ad5e8fa114e22a5ac9cde7e80e809c642128','knight-errant-000'),
 'Tales of the Jedi 1':('15804980','ab731d5263fc4f3914a75c164c1e4a6dc1f9451a0e70b9a97e3d773bec948567','totj-1993-001'),
 'Knights of the Old Republic 1':('15455769','ab41d92ffe85e878946eb86fda978ea98e3e2c9d5c1b74a779b79e5047919cfb','kotor-2006-001'),
 'Knights of the Old Republic 2':('14809684','146fe0b4147351481af9234d43cefcc1008176f17957c016fa1467a49197157b','kotor-2006-002'),
 'Knights of the Old Republic 3':('14809695','ee4dfaa688ee0762518aacb0059666a1f64ee2768fdfe59bab9b2fd549a5070e','kotor-2006-003'),
 'Knights of the Old Republic 4':('14809701','6f745928ec36352800c801b430989e041613c35a8bf93e2ab3d011e2807d11d9','kotor-2006-004'),
 'Knights of the Old Republic 5':('14773477','dd514b32a36f94cb7832d104f5d8747cf64340dee2a058f99e4f73ec04c348b9','kotor-2006-005'),
 'Knights of the Old Republic 6':('15609880','48399de0d560270ed091821e5c8c72ea19284adb7cac14d7536d61ca50e2b106','kotor-2006-006'),
 'Knights of the Old Republic 8':('14755529','341df2b6872b1ad3cfe3c3996af3f0c514b7485229e153fe3194285c1f58f0c6','kotor-2006-008'),
 'Knights of the Old Republic 10':('14755534','f535a4f638ff9ddfa67888792ce4d302a9dea4529e8159557a3b2a21938f06c8','kotor-2006-010'),
 'Knights of the Old Republic 12':('14755546','a0ec44f4e06438d252c0c53b58ed63a29780edfa69a59446dc7b70bf1f1e09aa','kotor-2006-012'),
 'Knights of the Old Republic 13':('14755551','5be7f74ff945301d9b91f24b641bfbabae73d3432dc1b9caf0c273e3ec193441','kotor-2006-013'),
 'Knights of the Old Republic 14':('14755554','fd2d88c9c3d0760340d34e53550273d371ae0e2ef5146827b151a916d1cc99c3','kotor-2006-014'),
 'Knights of the Old Republic 18':('14907383','bd0bdb7ee7becf7304f6029c8e20964bd977bc3221c0f3ce97f47588e640c8f0','kotor-2006-018'),
 'Knights of the Old Republic 31':('15818848','1489cdf09a71f2b8758c6c6c8d6f60b78fc6a73c764b59d2d66702f8bdc83d55','kotor-2006-031'),
 'Tales of the Jedi – Dark Lords of the Sith 1':('15791800','baae3ae279e09096f1d63084a0f673ed5b7012f7fcd84de0e114cb7910ac44df','totj-dark-001'),
 'Tales of the Jedi – Dark Lords of the Sith 2':('15253389','9acc1c47168b1f5800aae20fa547198bcd9a984ee8438a08e862a6f6067ca04d','totj-dark-002'),
 'Tales of the Jedi – Dark Lords of the Sith 3':('15375451','9c8906961475ada0eda0f02731c829940db49541820604e8433898e78d33cbd0','totj-dark-003'),
 'Tales of the Jedi – Dark Lords of the Sith 6':('15467547','947a5dd6fe98c37640a518c605cf819bcba142131addbe7c12dcec520fb75d93','totj-dark-006'),
 'Tales of the Jedi – The Freedon Nadd Uprising 1':('15804997','b8801278fdc8a45a39f34f6b4d3bc6f8c22fd7936b02f7114cce9ef9c4f6028a','totj-freedon-001'),
 'Tales of the Jedi 2':('14745962','004382e7438c56600edfa1c2da86967fb3f1924a1fa65892f1674b9215658270','totj-1993-002'),
 'Tales of the Jedi 5':('15550093','55ec9d7664b57749a2f8af419484dc5fa70899c058ff66264bbc181457162fab','totj-1993-005'),
 'Tales of the Jedi – The Golden Age of the Sith 1':('15805044','65176a60e0c23184b3b183d5220985b783dba2cf2c33e735b6f1a0945c1194d0','totj-golden-001'),
 'Tales of the Jedi – The Sith War 2':('14923351','a641d6aad34beb625afbb35f58cf25ac3aab4edfbb1ef14322b3f43b19df5dcf','totj-sith-war-002'),
 'Tales of the Jedi – The Sith War 5':('14806443','912e4b32eb24b3e09beea55af103671823ee47f2969efea9e9aff3de3a6cd03b','totj-sith-war-005'),
 'Tales of the Jedi – The Sith War 6':('15621449','3e95986ef760b2c8ccc3d1569bbee38270b0cfd359e7dd01af5e83c938acc3e5','totj-sith-war-006'),
 'Tales of the Jedi – The Fall of the Sith Empire 1':('15804991','5726dc727fb84a8e13462b99038777e0432a251d12b9e8e5404b8451e6298666','totj-fall-001'),
 'Tales of the Jedi – The Fall of the Sith Empire 4':('15253301','22ac5a6642ff2b1a5238fd0c8ee66d63f6ffe09cb12b29829d673264d7986ed5','totj-fall-004'),
 'Tales of the Jedi – The Fall of the Sith Empire 5':('15804996','77aa5149cd1da12dc4fb1f5214e4b1b5b6dad7dd2b8981fd8f5366a77686d64d','totj-fall-005'),
 'Tales of the Jedi – Redemption 1':('15804984','0ea57f89946cdeb098e123498b79af901b6a4b10e2b201e14ea12f2972ba46e3','totj-redemption-001'),
 'Tales of the Jedi – Redemption 4':('14925778','959cc95e9aae241aca9a880d1db0c6bec47c1daf59e6df27f7175b37258838e9','totj-redemption-004'),
 'Tales of the Jedi – Redemption 5':('15804989','a4752865be7de8aa63e8accaca29d37314973cca62a9992c863546a1ab9ff94f','totj-redemption-005'),
 'Knight Errant 1':('15418889','48e6a3473e14640d20787a7f0f49573ab2ed9de2cc2bb059b3a6045dc6de183b','knight-errant-001'),
 'Knight Errant 2':('15465386','3630f9a8cb490f0ffaf9710fa371f205e7d6d6d6e05198f40f69b8cc0ffa3d57','knight-errant-002'),
 'Knight Errant 3':('14920199','27648b81a60b7519dbdf9562795a89dee6da6ddd3a746e630d849b355a852764','knight-errant-003'),
 'Knight Errant 4':('14920201','a69485284ab07cd1872dcf601a5ab332ab45e556f303da8cad7b35a55aa58116','knight-errant-004'),
 'Knight Errant: Deluge 1':('14738367','877caff3dd4fc30a8cd8a2b6a8ef85b6914844989947493cec8780715abb356c','knight-errant-deluge-001'),
 'Knight Errant: Deluge 3':('14895581','5c66214c0f82dc4c568884ca6c42d4faae0773d470fb5725c021a65ebb746565','knight-errant-deluge-003'),
 'Knight Errant: Deluge 4':('14738370','f6d8314297e83abdb2304ae2230afb36d498d7f76bb0d543e100b71415cb8378','knight-errant-deluge-004'),
 'The Old Republic — The Lost Suns 2':('15552387','63dc410695cb02169a8c0139e4493607c5cc124695bee23721d4b44820485f6c','tor-lost-suns-002'),
 'The Old Republic — The Lost Suns 4':('15552389','a709725dcb90a822a9aaa167830f43bb23c78c9b15ac123fbc355d2d932e531c','tor-lost-suns-004'),
 'Knight Errant: Escape 3':('14738375','9f1896101ce2368fee9f2819e21a72b253845fab07417ddd0f6ca55432770b02','knight-errant-escape-003'),
 'Knight Errant: Escape 4':('14738376','c5246149ccf9cd0cc68a9b721ba7eb5069afb03607455a824303c162437e5a72','knight-errant-escape-004'),
 'Dawn of the Jedi: Force Storm 3':('15816229','811965b9c891841a6e36af48c281dbd39c35925f3d8bb697290a9aa3ccd4286d','dawn-force-storm-003'),
 'Dawn of the Jedi: Force Storm 4':('15406891','f157084c50270cd1734d9a33519b3e9dedfa7c28369c4a976456ebc79cc5ec0a','dawn-force-storm-004'),
 'Lost Tribe of the Sith — Spiral 2':('14739214','2cb987e1da13281dd18699630a9b0654a4675b745935af27a9a8483a3a4bdb5f','lost-tribe-spiral-002'),
 'Lost Tribe of the Sith — Spiral 3':('14739215','4679b19c4796388baaddc4a4a6cc47b11a3cfc35cafb6a0195557e25abaae578','lost-tribe-spiral-003'),
 'Lost Tribe of the Sith — Spiral 4':('14739216','346f7083fcfc47ff9fa8cd1e25eb163d2c54b371cf2b7e5ae5a32bad425033a2','lost-tribe-spiral-004'),
}
rows={}
with Path(sys.argv[1]).open(encoding='utf-8') as f:
 for line in f:
  x=json.loads(line)
  if x['title'] not in APPROVED:continue
  rev,digest,work=APPROVED[x['title']]
  if x['revision_id']!=rev or hashlib.sha256(x['text'].encode()).hexdigest()!=digest or x['text_sha256']!=digest:raise ValueError('reviewed source changed: '+x['title'])
  x.update(inventory_work_id=work,evidence_class='secondary',license='CC BY-SA 3.0',attribution='Wookieepedia contributors; see linked article history',source_revision_url=x['url']+'?oldid='+rev,review_status='plot section inspected; full article remains held',continuity='Legends')
  x.pop('status',None);rows[x['title']]=x
if set(rows)!=set(APPROVED):raise ValueError('missing reviewed candidates')
out=Path('data/wookieepedia-reviewed-comic-plots.jsonl')
with out.open('w',encoding='utf-8',newline='\n') as f:
 for title in sorted(rows):f.write(json.dumps(rows[title],ensure_ascii=False,sort_keys=True)+'\n')
print('reviewed plot sections:',len(rows))
