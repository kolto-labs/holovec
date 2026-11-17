"""Publish a pinned wiki contributor arc summary with one quoted phrase omitted.

Input is a local-only candidate from prepare_wiki_plot_review_quoted.py. Source
section and cleaned output hashes are verified before publication. No embeddings.
"""
import hashlib,json,sys
from pathlib import Path
TITLE='Star Wars: Knights of the Old Republic: Knights of Suffering'
REV='14744361';RAW='b450f7bf5f99eb5e4de45a4d9199617917ab3ccfb5d4c20de660c96450d8e4b4';CLEAN='62e011f65f36012932987d96b709b099f7b9663281c49d14dd0df65b565f2593'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
rows=[json.loads(l) for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()];found=[x for x in rows if x['title']==TITLE]
if len(found)!=1:raise ValueError('expected one source candidate')
x=found[0];text=x['text']
if x['revision_id']!=REV or x['raw_wikitext_sha256']!=RAW or x['text_sha256']!=CLEAN or sha(text)!=CLEAN:raise ValueError('source revision or text changed')
phrase='"occupy her mind"'
if text.count(phrase)!=1 or sum(text.count(c) for c in ('"','“','”'))!=2:raise ValueError('unexpected quote markup')
text=text.replace(phrase,'[quoted words omitted]')
x.update(text=text,text_sha256=sha(text),cleaned_text_sha256=CLEAN,source_revision_url=x['url']+'?oldid='+REV,license='CC BY-SA 3.0',attribution='Wookieepedia contributors; see linked article history',evidence_class='secondary',work_type='comic-arc',continuity='Legends',extraction='References and templates removed; one quotation-marked phrase replaced with [quoted words omitted].',review_status='plot summary inspected; full article and primary comics remain held',embedded=False,inventory_arc_id='kotor-arc-knights-of-suffering')
x.pop('status',None)
Path('data/wookieepedia-reviewed-kotor-arc.jsonl').write_text(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
print('Published quote-omitted arc summary')
