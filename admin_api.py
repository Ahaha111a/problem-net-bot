import hashlib
import hmac
import json
import os
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web

from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS
from database import (
    get_story, get_all_stories, get_waiting_stories, get_scheduled_stories,
    get_open_dialogs, get_dialog, get_dialog_messages, get_admin_audit,
    get_extended_stats, get_analytics, get_admin_roles, get_admin_role,
    set_admin_role, get_complaints, update_complaint, get_story_versions,
    restore_story_version, get_moderator_metrics, get_top_stories,
    get_user_retention, get_sla_breaches, set_support_priority,
    get_support_priority, get_admin_notifications, mark_admin_notification_read, add_support_message,
    update_story_content, update_post, schedule_story, cancel_scheduled_story,
    publish_story, reject_story, log_admin_action,
    get_support_metrics, get_support_queue, get_category_stats, get_publication_hour_stats,
    get_funnel_stats, get_security_events, get_publication_queue, auto_plan_stories,
    create_repost_job, get_repost_jobs,
)
from ai import analyze_story, moderate_story
from post_generator import create_post
from keyboards import channel_story_keyboard, published_story_keyboard

TZ = ZoneInfo('Europe/Moscow')
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / 'miniapp'
if not WEB_DIR.exists():
    # Compatibility with the current repository layout where Mini App files
    # are still in the project root.
    WEB_DIR = BASE_DIR


def _json(row):
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return {k: row[k] for k in row.keys()}
    return row


def _rows(rows):
    return [_json(r) for r in rows]


def validate_init_data(init_data: str) -> dict | None:
    if not init_data:
        return None
    try:
        data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = data.pop('hash', None)
        if not received_hash:
            return None
        check = '\n'.join(f'{k}={data[k]}' for k in sorted(data))
        secret = hmac.new(
        b'WebAppData',
        BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None
        auth_date = int(data.get('auth_date', '0'))
        if abs(datetime.now().timestamp() - auth_date) > 86400:
            return None
        user = json.loads(data.get('user', '{}'))
        data['user'] = user
        return data
    except Exception:
        return None


def auth(request, allowed=None):
    init_data = request.headers.get('X-Telegram-Init-Data', '')
    data = validate_init_data(init_data)
    if not data:
        raise web.HTTPUnauthorized(text='Invalid Telegram initData')
    user = data.get('user') or {}
    uid = int(user.get('id', 0))
    if uid not in ADMIN_IDS:
        raise web.HTTPForbidden(text='Admin access required')
    role = get_admin_role(uid)
    if allowed and role not in allowed:
        raise web.HTTPForbidden(text='Insufficient role')
    return uid


async def index(request):
    return web.FileResponse(WEB_DIR / 'index.html')

async def health(request):
    return web.json_response({
        'ok': True,
        'service': 'problem-net-admin',
        'timezone': 'Europe/Moscow',
    })

async def static_file(request):
    name = request.match_info['name']
    if '/' in name or '\\' in name:
        raise web.HTTPNotFound()
    path = WEB_DIR / name
    if not path.exists():
        raise web.HTTPNotFound()
    return web.FileResponse(path)


async def dashboard(request):
    uid=auth(request)
    stats=get_extended_stats()
    return web.json_response({
        'me': {'id':uid,'role':get_admin_role(uid)},
        'stats': stats,
        'analytics': get_analytics(),
        'complaints': _rows(get_complaints('new', 20)),
        'sla_breaches': _rows(get_sla_breaches()),
        'notifications': _rows(get_admin_notifications(uid, False, 20)),
        'top_stories': _rows(get_top_stories(10)),
        'retention': _json(get_user_retention()),
    })

async def stories(request):
    auth(request)
    status=request.query.get('status')
    rows=get_all_stories()
    if status:
        rows=[r for r in rows if r['status']==status]
    return web.json_response({'items':_rows(rows[:100])})

async def story(request):
    auth(request, {'owner','moderator','editor','analyst'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    return web.json_response({'story':_json(row),'versions':_rows(get_story_versions(sid))})

async def story_edit(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); payload=await request.json()
    row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    text=str(payload.get('text', row['text']))[:20000]
    post=str(payload.get('post_text', row['post_text'] or ''))[:10000]
    update_story_content(sid,text,post,uid); log_admin_action(uid,'miniapp_edit_story',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_ai(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    result=await analyze_story(row['text']);
    from database import update_ai_result
    update_ai_result(sid,result); log_admin_action(uid,'miniapp_ai_retry',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_moderate_ai(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    result=await moderate_story(row['text'])
    from database import update_ai_moderation_result
    update_ai_moderation_result(sid,result); log_admin_action(uid,'miniapp_ai_moderate',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_publish(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    text=(row['post_text'] or '').strip()
    if not text: raise web.HTTPBadRequest(text='Post is empty')
    bot=request.app['bot']
    sent=await bot.send_message(CHANNEL_ID,text,reply_markup=channel_story_keyboard(sid,None))
    publish_story(sid,sent.message_id); log_admin_action(uid,'miniapp_publish',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid)),'message_id':sent.message_id})

async def story_reject(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    payload=await request.json(); reason=str(payload.get('reason',''))[:1000]
    reject_story(sid,reason); log_admin_action(uid,'miniapp_reject',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_schedule(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    payload=await request.json(); raw=str(payload.get('scheduled_at',''))
    try:
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if dt.tzinfo is None: dt=dt.replace(tzinfo=TZ)
        if dt <= datetime.now(dt.tzinfo): raise ValueError()
    except Exception:
        raise web.HTTPBadRequest(text='Invalid future datetime')
    schedule_story(sid,dt.astimezone(ZoneInfo('UTC')).isoformat(),uid)
    log_admin_action(uid,'miniapp_schedule',story_id=sid,user_id=row['user_id'],details=dt.isoformat())
    return web.json_response({'story':_json(get_story(sid))})

async def story_unschedule(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    cancel_scheduled_story(sid); log_admin_action(uid,'miniapp_unschedule',story_id=sid)
    return web.json_response({'story':_json(get_story(sid))})

async def bulk(request):
    uid=auth(request, {'owner','moderator','editor'}); payload=await request.json(); ids=[int(x) for x in payload.get('ids',[])]; action=payload.get('action')
    changed=[]
    for sid in ids[:100]:
        row=get_story(sid)
        if not row: continue
        if action=='reject': reject_story(sid,'Массовое отклонение через Mini App'); changed.append(sid)
        elif action=='unschedule': cancel_scheduled_story(sid); changed.append(sid)
    log_admin_action(uid,f'miniapp_bulk_{action}',details=json.dumps(changed))
    return web.json_response({'changed':changed})

async def versions(request):
    auth(request); sid=int(request.match_info['id']); return web.json_response({'items':_rows(get_story_versions(sid))})

async def restore_version(request):
    uid=auth(request, {'owner','moderator','editor'}); vid=int(request.match_info['version_id']); row=restore_story_version(vid,uid)
    if not row: raise web.HTTPNotFound()
    log_admin_action(uid,'miniapp_restore_version',story_id=row['id'])
    return web.json_response({'story':_json(row)})

async def dialogs(request):
    auth(request, {'owner','moderator','support'}); return web.json_response({'items':_rows(get_open_dialogs())})

async def dialog(request):
    auth(request, {'owner','moderator','support'}); did=int(request.match_info['id']); d=get_dialog(did)
    if not d: raise web.HTTPNotFound()
    return web.json_response({'dialog':_json(d),'messages':_rows(get_dialog_messages(did)),'sla':_json(get_support_priority(did))})

async def dialog_update(request):
    uid=auth(request, {'owner','moderator','support'}); did=int(request.match_info['id']); d=get_dialog(did)
    if not d: raise web.HTTPNotFound()
    p=await request.json()
    if 'priority' in p: set_support_priority(did,p['priority'])
    if 'assigned_admin_id' in p:
        from database import assign_dialog
        assign_dialog(did,int(p['assigned_admin_id']) if p['assigned_admin_id'] else uid)
    if 'status' in p:
        from database import set_dialog_status
        set_dialog_status(did,p['status'])
    log_admin_action(uid,'miniapp_dialog_update',dialog_id=did,user_id=d['user_id'])
    return web.json_response({'dialog':_json(get_dialog(did)),'sla':_json(get_support_priority(did))})

async def complaints(request):
    auth(request, {'owner','moderator','support'}); return web.json_response({'items':_rows(get_complaints(request.query.get('status'),100))})

async def complaint_update(request):
    uid=auth(request, {'owner','moderator','support'}); cid=int(request.match_info['id']); p=await request.json(); update_complaint(cid,p.get('status'),p.get('priority'),p.get('assigned_admin_id')); log_admin_action(uid,'miniapp_complaint_update',details=str(cid)); return web.json_response({'ok':True})

async def roles(request):
    uid=auth(request, {'owner'})
    if get_admin_role(uid)!='owner': raise web.HTTPForbidden()
    return web.json_response({'items':_rows(get_admin_roles())})

async def role_update(request):
    uid=auth(request, {'owner'})
    if get_admin_role(uid)!='owner': raise web.HTTPForbidden()
    target=int(request.match_info['id']); p=await request.json(); role=p.get('role')
    if role not in {'owner','moderator','support','analyst','editor'}: raise web.HTTPBadRequest(text='Invalid role')
    set_admin_role(target,role); log_admin_action(uid,'miniapp_role_update',user_id=target,details=role); return web.json_response({'ok':True})

async def audit(request):
    auth(request, {'owner','analyst'}); return web.json_response({'items':_rows(get_admin_audit(200))})

async def analytics(request):
    auth(request, {'owner','analyst'}); return web.json_response({'analytics':get_analytics(),'moderators':_rows(get_moderator_metrics(30)),'top':_rows(get_top_stories(20)),'retention':_json(get_user_retention())})

async def notifications(request):
    uid=auth(request, {'owner','moderator','support','analyst','editor'}); return web.json_response({'items':_rows(get_admin_notifications(uid,False,100))})

async def notification_read(request):
    uid=auth(request, {'owner','moderator','support','analyst','editor'}); nid=int(request.match_info['id']); mark_admin_notification_read(nid,uid); return web.json_response({'ok':True})


async def dialog_message(request):
    uid=auth(request, {'owner','moderator','support'}); did=int(request.match_info['id']); d=get_dialog(did)
    if not d: raise web.HTTPNotFound()
    p=await request.json(); text=str(p.get('text','')).strip()
    if not text: raise web.HTTPBadRequest(text='Empty message')
    if d['status']!='open': raise web.HTTPBadRequest(text='Dialog closed')
    add_support_message(did,uid,'admin',text[:4000])
    try:
        await request.app['bot'].send_message(d['user_id'], '💬 <b>Сообщение поддержки:</b>\n\n'+text[:4000], parse_mode='HTML')
    except Exception as e:
        print('MINIAPP SUPPORT SEND ERROR:',e)
    log_admin_action(uid,'miniapp_support_message',dialog_id=did,user_id=d['user_id'])
    return web.json_response({'dialog':_json(get_dialog(did)),'messages':_rows(get_dialog_messages(did))})

async def story_contact(request):
    uid=auth(request); sid=int(request.match_info['id']); s=get_story(sid)
    if not s: raise web.HTTPNotFound()
    try:
        await request.app['bot'].send_message(s['user_id'],'💬 С вами хочет связаться сотрудник поддержки. Если вы готовы продолжить диалог, откройте «🆘 Экстренная поддержка».')
    except Exception as e:
        print('MINIAPP CONTACT ERROR:',e)
    log_admin_action(uid,'miniapp_contact_user',story_id=sid,user_id=s['user_id'])
    return web.json_response({'ok':True})

async def dialog_action(request):
    uid=auth(request, {'owner','moderator','support'}); did=int(request.match_info['id']); d=get_dialog(did)
    if not d: raise web.HTTPNotFound()
    action=request.match_info['action']
    from database import set_dialog_status, assign_dialog, unassign_dialog, close_dialog
    if action=='assign': assign_dialog(did,uid)
    elif action=='waiting': set_dialog_status(did,'waiting_user')
    elif action=='resolved': set_dialog_status(did,'resolved')
    elif action=='close': close_dialog(did)
    elif action=='exit': unassign_dialog(did); set_dialog_status(did,'new')
    else: raise web.HTTPBadRequest(text='Unknown action')
    log_admin_action(uid,'miniapp_dialog_'+action,dialog_id=did,user_id=d['user_id'])
    return web.json_response({'dialog':_json(get_dialog(did))})


async def support_metrics(request):
    auth(request, {'owner','moderator','support','analyst'})
    return web.json_response({'metrics': _json(get_support_metrics()), 'queue': _rows(get_support_queue())})

async def support_queue(request):
    auth(request, {'owner','moderator','support','analyst'})
    return web.json_response({'items': _rows(get_support_queue())})

async def content_analytics(request):
    auth(request, {'owner','analyst','moderator','editor'})
    return web.json_response({
        'categories': _rows(get_category_stats()),
        'hours': _rows(get_publication_hour_stats()),
        'funnel': _json(get_funnel_stats()),
        'queue': _rows(get_publication_queue()),
    })

async def auto_plan(request):
    uid = auth(request, {'owner','moderator','editor'})
    p = await request.json()
    ids = [int(x) for x in p.get('ids', [])][:100]
    start_raw = str(p.get('start_at','')).strip()
    interval = max(5, min(int(p.get('interval_minutes', 60)), 10080))
    if not start_raw:
        raise web.HTTPBadRequest(text='start_at required')
    try:
        dt = datetime.fromisoformat(start_raw.replace('Z','+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        if dt <= datetime.now(dt.tzinfo):
            raise ValueError
    except Exception:
        raise web.HTTPBadRequest(text='Invalid future start_at')
    result = auto_plan_stories(ids, dt.astimezone(ZoneInfo('UTC')).isoformat(), interval, uid)
    return web.json_response({'items': _rows(result)})

async def repost(request):
    uid = auth(request, {'owner','moderator','editor'})
    sid = int(request.match_info['id'])
    p = await request.json()
    raw = str(p.get('scheduled_at','')).strip()
    if not raw:
        raise web.HTTPBadRequest(text='scheduled_at required')
    try:
        dt = datetime.fromisoformat(raw.replace('Z','+00:00'))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=TZ)
        if dt <= datetime.now(dt.tzinfo): raise ValueError
    except Exception:
        raise web.HTTPBadRequest(text='Invalid future datetime')
    job_id = create_repost_job(sid, dt.astimezone(ZoneInfo('UTC')).isoformat(), uid)
    log_admin_action(uid, 'miniapp_repost_schedule', story_id=sid, details=dt.isoformat())
    return web.json_response({'job_id': job_id})

async def reposts(request):
    auth(request, {'owner','moderator','editor','analyst'})
    return web.json_response({'items': _rows(get_repost_jobs(100))})

async def security(request):
    auth(request, {'owner'})
    return web.json_response({'items': _rows(get_security_events(300))})

def create_app(bot):
    app=web.Application()
    app['bot']=bot
    app.router.add_get('/', index)
    app.router.add_get('/health', health)
    app.router.add_get('/admin', index)
    app.router.add_get('/admin/', index)
    app.router.add_get('/admin/{name}', static_file)
    app.router.add_get('/assets/{name}', static_file)
    app.router.add_get('/admin/api/dashboard', dashboard)
    app.router.add_get('/admin/api/stories', stories)
    app.router.add_get('/admin/api/story/{id}', story)
    app.router.add_put('/admin/api/story/{id}', story_edit)
    app.router.add_post('/admin/api/story/{id}/ai', story_ai)
    app.router.add_post('/admin/api/story/{id}/ai-moderate', story_moderate_ai)
    app.router.add_post('/admin/api/story/{id}/publish', story_publish)
    app.router.add_post('/admin/api/story/{id}/contact', story_contact)
    app.router.add_post('/admin/api/story/{id}/reject', story_reject)
    app.router.add_post('/admin/api/story/{id}/schedule', story_schedule)
    app.router.add_post('/admin/api/story/{id}/unschedule', story_unschedule)
    app.router.add_post('/admin/api/bulk', bulk)
    app.router.add_get('/admin/api/story/{id}/versions', versions)
    app.router.add_post('/admin/api/version/{version_id}/restore', restore_version)
    app.router.add_get('/admin/api/dialogs', dialogs)
    app.router.add_get('/admin/api/dialog/{id}', dialog)
    app.router.add_put('/admin/api/dialog/{id}', dialog_update)
    app.router.add_post('/admin/api/dialog/{id}/message', dialog_message)
    app.router.add_post('/admin/api/dialog/{id}/{action}', dialog_action)
    app.router.add_get('/admin/api/complaints', complaints)
    app.router.add_put('/admin/api/complaint/{id}', complaint_update)
    app.router.add_get('/admin/api/roles', roles)
    app.router.add_put('/admin/api/role/{id}', role_update)
    app.router.add_get('/admin/api/audit', audit)
    app.router.add_get('/admin/api/analytics', analytics)
    app.router.add_get('/admin/api/notifications', notifications)
    app.router.add_post('/admin/api/notification/{id}/read', notification_read)
    app.router.add_get('/admin/api/support/metrics', support_metrics)
    app.router.add_get('/admin/api/support/queue', support_queue)
    app.router.add_get('/admin/api/content/analytics', content_analytics)
    app.router.add_post('/admin/api/content/auto-plan', auto_plan)
    app.router.add_post('/admin/api/story/{id}/repost', repost)
    app.router.add_get('/admin/api/reposts', reposts)
    app.router.add_get('/admin/api/security', security)
    return app


async def start_admin_web(bot):
    app=create_app(bot)
    runner=web.AppRunner(app); await runner.setup()
    port=int(os.getenv('PORT','8080'))
    site=web.TCPSite(runner,'0.0.0.0',port); await site.start()
    print(f'🖥 Admin Mini App server listening on :{port}')
    return runner
