"""Link exact publisher patch labels to existing named secondary sections.

Matches are discovery links, not claims of complete patch or story coverage.
"""
import hashlib,json,re
from pathlib import Path
manifest=json.loads(Path('manifest.json').read_text());known={v['path']:v for v in manifest['input_files']}
def read(p):
 b=Path(p).read_bytes();e=known.get(p);h=hashlib.sha256(b).hexdigest()
 if not e or (e['size'],e['sha256'])!=(len(b),h):raise ValueError('input changed or not registered: '+p)
 return b,h
index_bytes,index_sha=read('catalog/works/swtor-patchnote-index.json');section_bytes,section_sha=read('data/wookieepedia-swtor-expansion-sections.jsonl')
index=json.loads(index_bytes)['items'];sections=[json.loads(x) for x in section_bytes.splitlines()];links=[];matched=set()
for section in sections:
 name=section.get('section') or ''
 if len(name)<=5:continue
 pattern=re.compile(r'(?<!\w)'+re.escape(name)+r'(?!\w)',re.I);candidates=[v for v in index if pattern.search(v['publisher_label'])]
 if len(candidates)>1:raise ValueError('ambiguous patch label: '+name)
 if not candidates:continue
 patch=candidates[0];matched.add(patch['publisher_url']);text=section.get('text') or ''
 if hashlib.sha256(text.encode()).hexdigest()!=section['text_sha256']:raise ValueError('section hash mismatch: '+name)
 links.append({'publisher_label':patch['publisher_label'],'publisher_url':patch['publisher_url'],'listed_date':patch['listed_date'],'version':patch['version'],'section':name,'secondary_dataset':'data/wookieepedia-swtor-expansion-sections.jsonl','secondary_title':section['title'],'secondary_url':section['url'],'secondary_revision_id':section['revision_id'],'secondary_text_sha256':section['text_sha256'],'match_kind':'exact_label', 'scope':'Exact section-name match only; does not establish complete patch, mission, choice, language or primary content coverage.'})
if len(links)!=16 or len(matched)!=16:raise ValueError('match set changed; review before updating')
# Publisher 7.8 notes explicitly identify Galactic Threads as its storyline;
# 7.6's identically named patch is a name match, not proof of story release.
old=next(v for v in links if v['version']=='7.6' and v['section']=='Galactic Threads')
old['scope']='Patch name matches the section name, but the publisher identifies the Galactic Threads storyline with update 7.8. Do not interpret the name match as a 7.6 story-release claim.'
patch=next(v for v in index if v['publisher_url']=='https://www.swtor.com/patchnotes/12092025/game-update-7.8-pursuit-ruin')
new={**old,'publisher_label':patch['publisher_label'],'publisher_url':patch['publisher_url'],'listed_date':patch['listed_date'],'version':patch['version'],'match_kind':'publisher_confirmed_storyline','publisher_evidence_url':patch['publisher_url'],'scope':'Publisher 7.8 patch notes identify Galactic Threads as a storyline. The linked wiki section is partial secondary context, not complete patch, mission, branch or primary content coverage.'}
links.append(new);matched.add(patch['publisher_url'])
links.sort(key=lambda v:v['publisher_url']);unmatched=[{'publisher_label':v['publisher_label'],'publisher_url':v['publisher_url']} for v in index if v['publisher_url'] not in matched]
r={'scope':'Exact phrase matches between indexed publisher patch labels and one pinned secondary expansion-section layer, plus one publisher-confirmed storyline link. The 7.6 name match is not a story-release claim. Other corpus sources, aliases and indirect associations are not searched. No match is not evidence of absent coverage.','publisher_index_sha256':index_sha,'secondary_layer_sha256':section_sha,'indexed_links':len(index),'matched_links':len(links),'exact_label_matches':16,'publisher_confirmed_storyline_links':1,'unmatched_links':len(unmatched),'matches':links,'unmatched':unmatched}
Path('evaluation/swtor-patch-story-section-links.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n');print('indexed',len(index),'total links',len(links),'unmatched in this layer',len(unmatched))
