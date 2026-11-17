"""Check public Discord widget exposure against a private local guild inventory.

Input is a JSON object mapping guild IDs to {"channels": [channel IDs]}.
Writes only aggregate counts; does not publish guild IDs or channel names.
Widget exposure alone does not establish historical visibility, message reuse
rights, or permission to ingest. This does not access message content.
"""
import concurrent.futures, datetime, json, sys
from pathlib import Path
import requests
inventory=json.loads(Path(sys.argv[1]).read_text())
def check(item):
 guild,entry=item
 try:
  response=requests.get(f'https://discord.com/api/v10/guilds/{guild}/widget.json',timeout=15)
  response.raise_for_status(); data=response.json()
  visible={str(x['id']) for x in data.get('channels',[]) if x.get('id')}
  return {'status':'enabled','visible_count':len(visible),'overlap_count':len(visible.intersection(map(str,entry['channels'])))}
 except requests.HTTPError as e:return {'status':'http_'+str(e.response.status_code),'visible_count':0,'overlap_count':0}
 except (requests.RequestException,ValueError,KeyError):return {'status':'error','visible_count':0,'overlap_count':0}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(check,inventory.items()))
status={}
for r in results:status[r['status']]=status.get(r['status'],0)+1
report={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':'Discord public guild widget API','guilds_checked':len(results),'response_counts':status,'exposed_channels':sum(x['visible_count'] for x in results),'archived_channel_id_overlaps':sum(x['overlap_count'] for x in results),'limitation':'Widget exposure does not prove historical channel permissions, public visibility of text history, contributor consent or rights to redistribute messages. No message content was accessed.'}
print(json.dumps(report,indent=2))
