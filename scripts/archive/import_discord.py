"""Stream explicitly approved DiscordChatExporter JSON files.

Usage: python import_discord.py approvals.json export.json [export.json ...]
Each manifest channel needs channel_id, server_id, public=true, a nonempty
visibility_evidence describing public access and its historical scope, and a
nonempty reuse_basis describing authority to publish and process messages.
Evidence is recorded, not automatically verified. Direct messages and private
threads are excluded. Requires ijson. Originals are only read.
"""
import datetime, hashlib, ijson, json, pathlib, sqlite3, sys, tempfile
if len(sys.argv)<3: raise SystemExit(__doc__)

ARCHIVE_CUTOFF = datetime.datetime(2026, 8, 1, tzinfo=datetime.timezone.utc)


def validate_export_date(meta):
    try:
        exported = datetime.datetime.fromisoformat(meta['exportedAt'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Archive needs a valid exportedAt timestamp') from error
    if exported.tzinfo is None or exported >= ARCHIVE_CUTOFF:
        raise ValueError('Archive must predate August 2026')


def nonempty(value):return isinstance(value,str) and bool(value.strip())
def validate_approval(entries):
 allowed={}
 for entry in entries:
  cid=str(entry.get('channel_id') or '');sid=str(entry.get('server_id') or '')
  if not cid.isdecimal() or not sid.isdecimal() or sid=='0' or entry.get('public') is not True or not nonempty(entry.get('visibility_evidence')) or not nonempty(entry.get('reuse_basis')):raise ValueError('Each approval needs server/channel IDs, public=true, visibility_evidence and reuse_basis')
  if cid in allowed:raise ValueError('Duplicate channel approval: '+cid)
  allowed[cid]=entry
 if not allowed:raise ValueError('No approved channels')
 return allowed
PUBLIC_CAPABLE_TYPES={'GuildTextChat','GuildVoiceChat','GuildNews','GuildNewsThread','GuildPublicThread','GuildStageVoice','GuildForum'}
def validate_channel_meta(meta,allowed):
 cid=meta.get('channel.id','');sid=meta.get('guild.id','');kind=meta.get('channel.type','')
 if cid not in allowed or sid!=str(allowed[cid]['server_id']):raise ValueError('Unapproved channel or server')
 if kind not in PUBLIC_CAPABLE_TYPES:raise ValueError('Private, direct or unknown channel type')
 return cid,sid
try:allowed=validate_approval(json.load(open(sys.argv[1],encoding='utf8'))['channels'])
except (ValueError,KeyError,TypeError) as e:raise SystemExit(str(e)) from e
files=[]
for filename in sys.argv[2:]:
 path=pathlib.Path(filename);meta={};digest=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
 with path.open('rb') as f:
  for prefix,event,val in ijson.parse(f):
   if prefix=='messages' and event=='start_array':break
   if prefix in ('guild.id','channel.id','channel.name','channel.type','channel.categoryId','exportedAt') and event in ('string','number'):meta[prefix]=str(val)
 try:
  validate_export_date(meta)
  cid,sid=validate_channel_meta(meta,allowed)
 except ValueError as e:raise SystemExit(str(e)+': '+filename) from e
 files.append((path,meta,digest.hexdigest()))
out=pathlib.Path('data/discord-approved.jsonl');out.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='holovec-discord-') as tmp:
 db=sqlite3.connect(str(pathlib.Path(tmp)/'dedupe.sqlite'));db.execute('create table messages (channel text,id text,version text,payload text,primary key(channel,id))');empty=0
 for path,meta,digest in files:
  cid=meta['channel.id'];sid=meta['guild.id']
  with path.open('rb') as f:
   for msg in ijson.items(f,'messages.item'):
    mid=str(msg.get('id',''));text=msg.get('content') or ''
    if not mid:empty+=1;continue
    stamp=msg.get('timestampEdited') or msg.get('timestamp') or ''
    try:
     parsed=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'));version=parsed.astimezone(datetime.timezone.utc).isoformat() if parsed.tzinfo else ''
    except (ValueError,AttributeError):version=''
    row={'id':mid,'server_id':sid,'channel_id':cid,'channel_name':meta.get('channel.name'),'channel_type':meta.get('channel.type'),'category_id':meta.get('channel.categoryId'),'attachment_count':len(msg.get('attachments') or []),'embed_count':len(msg.get('embeds') or []),'reaction_count':sum(int(r.get('count',0) or 0) for r in (msg.get('reactions') or [])),'timestamp':msg.get('timestamp'),'edited_timestamp':msg.get('timestampEdited'),'text':text,'text_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),'visibility_evidence_sha256':hashlib.sha256(allowed[cid]['visibility_evidence'].encode('utf8')).hexdigest(),'reply_to':(msg.get('reference') or {}).get('messageId'),'url':f'https://discord.com/channels/{sid}/{cid}/{mid}','export_sha256':digest,'reuse_basis':allowed[cid]['reuse_basis'],'evidence_class':'community_secondary'}
    row['exported_at']=meta['exportedAt']
    db.execute('insert into messages values (?,?,?,?) on conflict(channel,id) do update set version=excluded.version,payload=excluded.payload where excluded.version>messages.version',(cid,mid,version,json.dumps(row,ensure_ascii=False)))
  db.commit()
 temp=out.with_suffix('.jsonl.tmp')
 with temp.open('w',encoding='utf8') as f:
  for (payload,) in db.execute('select payload from messages order by channel,id'):f.write(payload+'\n')
 temp.replace(out);print('imported',db.execute('select count(*) from messages').fetchone()[0],'messages; skipped missing ID',empty)
