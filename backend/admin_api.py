import hashlib
import hmac
import json
import os
import urllib.parse
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web

from config import BOT_TOKEN, MODERATOR_BOT_TOKEN, CHANNEL_ID, ADMIN_IDS
from database import (
    get_connection,
    get_all_settings, set_setting, get_ai_checks, set_ai_check, lock_story, get_story_lock, unlock_story,
    get_system_errors, get_system_health, integrity_check, get_moderator_goals, set_moderator_goal,
    get_moderator_performance, get_training, assign_training, set_training_status, get_ai_priority_queue, create_ai_priority,
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
    create_repost_job, get_repost_jobs, record_kpi_event,
    founder_dashboard, get_ai_model_configs, set_ai_model_config, get_ai_model_health,
    get_ai_safety_events, get_latest_safety_decision, get_deployment_events, get_kpi_dashboard, get_lms_full, submit_lms_test,
)
from ai import analyze_story, moderate_story
from post_generator import create_post
from keyboards import channel_story_keyboard, published_story_keyboard
from rate_limit import allowed as rate_limit_allowed
from ops import (
    workload, sla_dashboard, prompts, save_prompt, activate_prompt, policies, set_policy,
    shadow_runs, incidents, create_incident, resolve_incident, railway_rollback, record_rollback,
)
from staff_ops import employees,employee,change_role,set_status,set_permission,permissions,role_history,promotion_history,violations,courses,assignments,assign_course,update_assignment,leaderboard

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
        (MODERATOR_BOT_TOKEN or BOT_TOKEN).encode(),
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
    # Fired employees lose access immediately, even if their old role remains in admin_roles.
    con = None
    try:
        con = get_connection()
        row = con.execute('SELECT status FROM employee_profiles WHERE admin_id=?', (uid,)).fetchone()
        if row and row['status'] == 'fired':
            raise web.HTTPForbidden(text='Доступ сотрудника отключён')
    except web.HTTPException:
        raise
    except Exception:
        pass
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass
    if allowed and role not in allowed:
        raise web.HTTPForbidden(text='Insufficient role')
    return uid


async def index(request):
    return web.FileResponse(WEB_DIR / 'index.html')

async def health(request):
    return web.json_response({
        'ok': True,
        'ready': True,
        'service': 'problem-net-admin',
        'timezone': 'Europe/Moscow',
    }, status=200)


async def static_file(request):
    name = request.match_info['name']
    if '/' in name or '\\' in name or name in {'.', '..'}:
        raise web.HTTPNotFound()
    path = WEB_DIR / name
    if not path.is_file():
        raise web.HTTPNotFound(text='Static file not found')
    response = web.FileResponse(path)
    response.headers['Cache-Control'] = 'no-store'
    return response


@web.middleware
async def rate_limit_middleware(request, handler):
    if request.path.startswith('/admin/api/'):
        key = request.remote or 'unknown'
        if not await rate_limit_allowed(key):
            raise web.HTTPTooManyRequests(text='Слишком много запросов. Попробуйте через минуту.')
    return await handler(request)


@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:
        print('\n================ MINI APP SERVER ERROR ================')
        print(f'Method: {request.method}')
        print(f'Path: {request.path_qs}')
        print(f'Error: {type(exc).__name__}: {exc}')
        traceback.print_exc()
        print('========================================================\n')
        return web.json_response(
            {'ok': False, 'error': 'Внутренняя ошибка сервера', 'details': str(exc)},
            status=500,
        )



async def api_health(request):
    uid = auth(request)
    return web.json_response({'ok': True, 'user_id': uid, 'timezone': 'Europe/Moscow'})

async def dashboard(request):
    uid = auth(request)
    return web.json_response({
        'me': {'id': uid, 'role': get_admin_role(uid)},
        'timezone': 'Europe/Moscow',
        'stats': get_extended_stats(),
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
    existing_lock=get_story_lock(sid)
    if existing_lock and int(existing_lock['admin_id']) != uid:
        return web.json_response({'ok':False,'locked':True,'admin_id':existing_lock['admin_id'],'expires_at':existing_lock['expires_at']}, status=409)
    text=str(payload.get('text', row['text']))[:20000]
    post=str(payload.get('post_text', row['post_text'] or ''))[:10000]
    update_story_content(sid,text,post,uid); record_kpi_event(uid,'edit',0,correction=bool(row['post_text'] and post != row['post_text'])); log_admin_action(uid,'miniapp_edit_story',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_ai(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    result=await analyze_story(row['text']);
    from database import update_ai_result
    update_ai_result(sid,result); log_admin_action(uid,'miniapp_ai_retry',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid))})

async def story_quality_ai(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    from ai import check_story_quality
    result=await check_story_quality(row['text'],row['post_text'] or '')
    from database import set_setting
    # сохраняем результат в версии/аудите, не меняя схему stories
    log_admin_action(uid,'miniapp_ai_quality',story_id=sid,user_id=row['user_id'],details=result)
    return web.json_response({'quality':result,'story':_json(row)})

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
    safety = get_latest_safety_decision(sid)
    if safety and safety.get('recommendation') != 'publish' and get_admin_role(uid) != 'owner':
        raise web.HTTPConflict(text='История требует ручной safety-проверки. Только владелец может сделать override.')
    text=(row['post_text'] or '').strip()
    if not text: raise web.HTTPBadRequest(text='Post is empty')
    bot=request.app['bot']
    sent=await bot.send_message(CHANNEL_ID,text,reply_markup=channel_story_keyboard(sid,None))
    publish_story(sid,sent.message_id); record_kpi_event(uid,'publish'); log_admin_action(uid,'miniapp_publish',story_id=sid,user_id=row['user_id'])
    return web.json_response({'story':_json(get_story(sid)),'message_id':sent.message_id})

async def story_reject(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); row=get_story(sid)
    if not row: raise web.HTTPNotFound()
    payload=await request.json(); reason=str(payload.get('reason',''))[:1000]
    reject_story(sid,reason); record_kpi_event(uid,'reject'); log_admin_action(uid,'miniapp_reject',story_id=sid,user_id=row['user_id'])
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
    add_support_message(did,uid,'admin',text[:4000]); record_kpi_event(uid,'support_response')
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
    uid=auth(request, {'owner','moderator','editor'}); p=await request.json()
    ids=[int(x) for x in p.get('ids',[])][:100]
    start=datetime.now(TZ)+timedelta(minutes=5); interval=max(5,int(p.get('interval_minutes',30)))
    from database import auto_plan_stories
    rows=auto_plan_stories(ids,start.astimezone(ZoneInfo('UTC')).isoformat(),interval,uid)
    log_admin_action(uid,'miniapp_auto_plan',details=json.dumps(rows,ensure_ascii=False))
    return web.json_response({'items':rows})


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

async def settings_api(request):
    uid=auth(request, {'owner'})
    return web.json_response({'settings': _rows(get_all_settings()), 'ai_checks': _rows(get_ai_checks())})

async def settings_update(request):
    uid=auth(request, {'owner'})
    payload=await request.json()
    for key,value in (payload.get('settings') or {}).items():
        set_setting(key,value,uid)
    for key,value in (payload.get('ai_checks') or {}).items():
        set_ai_check(key,bool(value),uid)
    log_admin_action(uid,'settings_update',details=json.dumps(payload,ensure_ascii=False))
    return web.json_response({'ok':True})

async def story_lock_api(request):
    uid=auth(request, {'owner','moderator','editor'})
    sid=int(request.match_info['id']); lock=get_story_lock(sid)
    if lock and int(lock['admin_id']) != uid:
        return web.json_response({'ok':False,'locked':True,'admin_id':lock['admin_id'],'locked_at':lock['locked_at'],'expires_at':lock['expires_at']})
    minutes=int(get_setting('story_lock_minutes','20') or 20)
    row=lock_story(sid,uid,minutes)
    return web.json_response({'ok':True,'lock':_json(row)})

async def story_unlock_api(request):
    uid=auth(request, {'owner','moderator','editor'}); sid=int(request.match_info['id']); unlock_story(sid,uid); return web.json_response({'ok':True})

async def monitoring(request):
    auth(request, {'owner','analyst'})
    return web.json_response({'health':_rows(get_system_health()),'errors':_rows(get_system_errors(200)),'integrity':integrity_check(),'performance':_rows(get_moderator_performance(30))})

async def training(request):
    auth(request, {'owner','moderator'})
    return web.json_response({'items':_rows(get_training())})

async def training_assign_api(request):
    uid=auth(request, {'owner'}); p=await request.json(); assign_training(int(p['admin_id']),str(p['course']),str(p['lesson']),p.get('due_at')); log_admin_action(uid,'training_assign',user_id=int(p['admin_id'])); return web.json_response({'ok':True})

async def training_update_api(request):
    uid=auth(request, {'owner','moderator'}); tid=int(request.match_info['id']); p=await request.json(); set_training_status(tid,p.get('status','completed'),p.get('score')); log_admin_action(uid,'training_update',details=str(tid)); return web.json_response({'ok':True})

async def goals_api(request):
    auth(request, {'owner','moderator','analyst'}); return web.json_response({'goals':_rows(get_moderator_goals()),'performance':_rows(get_moderator_performance(30))})

async def goal_update_api(request):
    uid=auth(request, {'owner'}); p=await request.json(); set_moderator_goal(int(p['admin_id']),str(p['period']),int(p.get('publish',0)),int(p.get('moderate',0)),int(p.get('response',0))); log_admin_action(uid,'goal_update',user_id=int(p['admin_id'])); return web.json_response({'ok':True})

async def priority_queue_api(request):
    auth(request, {'owner','moderator','editor','analyst'}); return web.json_response({'items':_rows(get_ai_priority_queue())})

async def priority_create_api(request):
    uid=auth(request, {'owner','moderator','editor'}); p=await request.json(); create_ai_priority(int(p['story_id']),p.get('priority','high'),p.get('reason','')); log_admin_action(uid,'ai_priority_create',story_id=int(p['story_id'])); return web.json_response({'ok':True})


async def employees_api(request):
 auth(request, {'owner','analyst'}); return web.json_response({'items':_rows(employees())})
async def employee_api(request):
 auth(request, {'owner','analyst'}); uid=int(request.match_info['id']); return web.json_response({'employee':_json(employee(uid)),'permissions':_rows(permissions(uid)),'role_history':_rows(role_history(uid)),'promotion_history':_rows(promotion_history(uid)),'violations':_rows(violations(uid)),'assignments':_rows(assignments(uid))})
async def employee_role_api(request):
 uid=auth(request, {'owner'}); p=await request.json(); change_role(int(request.match_info['id']),str(p['role']),uid,str(p.get('reason',''))); return web.json_response({'ok':True})
async def employee_status_api(request):
 uid=auth(request, {'owner'}); p=await request.json(); set_status(int(request.match_info['id']),str(p['status']),uid,str(p.get('reason',''))); return web.json_response({'ok':True})
async def employee_permission_api(request):
 uid=auth(request, {'owner'})
 p=await request.json()
 try:
  set_permission(int(request.match_info['id']),str(p['permission']),bool(p.get('enabled')),uid)
 except PermissionError as exc:
  raise web.HTTPConflict(text=str(exc))
 return web.json_response({'ok':True})
async def lms_api(request):
 auth(request, {'owner','moderator','analyst'}); return web.json_response({'courses':_rows(courses()),'assignments':_rows(assignments())})
async def lms_assign_api(request):
 auth(request, {'owner','moderator'}); p=await request.json(); assign_course(int(p['admin_id']),int(p['course_id']),p.get('due_at')); return web.json_response({'ok':True})
async def lms_update_api(request):
 auth(request, {'owner','moderator'}); p=await request.json(); update_assignment(int(request.match_info['id']),str(p.get('status','completed')),int(p.get('progress',100)),p.get('score')); return web.json_response({'ok':True})
async def leaderboard_api(request):
 auth(request, {'owner','analyst','moderator'}); return web.json_response({'items':leaderboard(int(request.query.get('days','30')))})


async def founder_page(request):
    auth(request, {'owner'})
    return web.FileResponse(WEB_DIR / 'founder.html')


async def founder_api(request):
    uid = auth(request, {'owner'})
    redis_status = {"status": "offline"}
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            from redis.asyncio import Redis
            r = Redis.from_url(redis_url, decode_responses=True)
            await r.ping()
            queue = os.getenv("AI_QUEUE_NAME", "problem-net:ai")
            redis_status = {
                "status": "online",
                "queue_length": await r.xlen(queue),
                "worker_heartbeats": len(await r.keys(f"{queue}:worker:*:heartbeat")),
            }
            await r.aclose()
        except Exception as exc:
            redis_status = {"status": "error", "details": str(exc)}
    return web.json_response({
        "ok": True,
        "founder_id": uid,
        "dashboard": founder_dashboard(),
        "ai_models": _rows(get_ai_model_configs()),
        "ai_health": _rows(get_ai_model_health()),
        "deployments": _rows(get_deployment_events(50)),
        "safety": _rows(get_ai_safety_events(limit=50)),
        "settings": _rows(get_all_settings()),
        "ai_checks": _rows(get_ai_checks()),
        "redis": redis_status,
        "ops": {
            "workload": _rows(workload()),
            "sla": sla_dashboard(),
            "prompts": _rows(prompts()),
            "policies": _rows(policies()),
            "incidents": _rows(incidents(100)),
            "shadow": _rows(shadow_runs(100)),
        },
    })


async def ai_control_api(request):
    uid = auth(request, {'owner'})
    if request.method == "GET":
        return web.json_response({
            "models": _rows(get_ai_model_configs()),
            "health": _rows(get_ai_model_health()),
            "checks": _rows(get_ai_checks()),
            "queue": _rows(get_ai_priority_queue(100)),
        })
    payload = await request.json()
    model = str(payload.get("model", "")).strip()
    if not model:
        raise web.HTTPBadRequest(text="model required")
    set_ai_model_config(
        model=model,
        enabled=bool(payload.get("enabled", True)),
        priority=int(payload.get("priority", 100)),
        max_tokens=int(payload.get("max_tokens", 1800)),
        temperature=float(payload.get("temperature", 0.2)),
        admin_id=uid,
    )
    log_admin_action(uid, "ai_model_config_update", details=json.dumps(payload, ensure_ascii=False))
    return web.json_response({"ok": True, "models": _rows(get_ai_model_configs())})


async def ai_safety_api(request):
    uid = auth(request, {'owner', 'moderator', 'editor'})
    sid = int(request.match_info["id"])
    row = get_story(sid)
    if not row:
        raise web.HTTPNotFound()
    from ai import run_safety_pipeline
    result = await run_safety_pipeline(row["text"], row["post_text"] or "", sid)
    log_admin_action(uid, "ai_safety_pipeline", story_id=sid, user_id=row["user_id"],
                     details=json.dumps(result, ensure_ascii=False))
    return web.json_response({"result": result, "events": _rows(get_ai_safety_events(sid))})


async def lms_full_api(request):
    auth(request, {'owner', 'moderator', 'analyst'})
    return web.json_response(get_lms_full())


async def lms_manage_api(request):
    uid = auth(request, {'owner'})
    p = await request.json()
    action = str(p.get("action", "")).strip()
    con = get_connection()
    try:
        if action == "create_course":
            cur = con.execute(
                """
                INSERT INTO lms_courses(title,position,required,required_for_permission,deadline_days,active)
                VALUES(?,?,?,?,?,true) RETURNING id
                """,
                (str(p["title"]), p.get("position"), bool(p.get("required")), p.get("required_for_permission"), int(p.get("deadline_days", 7))),
            )
            new_id = cur.fetchone()[0]
        elif action == "create_lesson":
            cur = con.execute(
                "INSERT INTO lms_lessons(course_id,title,content,position) VALUES(?,?,?,?) RETURNING id",
                (int(p["course_id"]), str(p["title"]), p.get("content", ""), int(p.get("position", 0))),
            )
            new_id = cur.fetchone()[0]
        elif action == "create_test":
            cur = con.execute(
                "INSERT INTO lms_tests(lesson_id,question,options,correct_answer,points) VALUES(?,?,?,?,?) RETURNING id",
                (int(p["lesson_id"]), str(p["question"]), json.dumps(p.get("options", []), ensure_ascii=False), str(p["correct_answer"]), int(p.get("points", 1))),
            )
            new_id = cur.fetchone()[0]
        elif action == "create_practical":
            cur = con.execute(
                "INSERT INTO lms_practical_tasks(course_id,title,instructions,max_score,required) VALUES(?,?,?,?,?) RETURNING id",
                (int(p["course_id"]), str(p["title"]), str(p.get("instructions", "")), int(p.get("max_score", 100)), bool(p.get("required"))),
            )
            new_id = cur.fetchone()[0]
        elif action == "create_exam":
            cur = con.execute(
                "INSERT INTO lms_exams(course_id,title,pass_score,attempt_limit,required) VALUES(?,?,?,?,?) RETURNING id",
                (int(p["course_id"]), str(p["title"]), int(p.get("pass_score", 70)), int(p.get("attempt_limit", 3)), bool(p.get("required"))),
            )
            new_id = cur.fetchone()[0]
        else:
            raise web.HTTPBadRequest(text="Unknown LMS action")
        con.commit()
    finally:
        con.close()
    log_admin_action(uid, "lms_manage", details=json.dumps(p, ensure_ascii=False))
    return web.json_response({"ok": True, "id": new_id})


async def lms_test_submit_api(request):
    uid = auth(request, {'owner', 'moderator', 'editor'})
    payload = await request.json()
    result = submit_lms_test(int(payload["assignment_id"]), payload.get("answers", {}), uid)
    log_admin_action(uid, "lms_test_attempt", details=json.dumps(result, ensure_ascii=False))
    return web.json_response({"ok": True, **result})


async def deployment_api(request):
    auth(request, {'owner', 'analyst'})
    return web.json_response({"items": _rows(get_deployment_events(100))})



async def workload_api(request):
    auth(request, {'owner','moderator','analyst'})
    return web.json_response({'items': _rows(workload())})


async def sla_dashboard_api(request):
    auth(request, {'owner','moderator','analyst'})
    return web.json_response(sla_dashboard())


async def kpi_dashboard_api(request):
    """Return the real moderator KPI dashboard data used by the Mini App."""
    auth(request, {'owner', 'moderator', 'analyst'})
    try:
        days = int(request.query.get('days', '30'))
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text='days must be an integer')
    days = max(1, min(days, 365))
    return web.json_response(get_kpi_dashboard(days))


async def prompts_api(request):
    uid = auth(request, {'owner'})
    if request.method == 'GET':
        return web.json_response({'items': _rows(prompts(request.query.get('name')) )})
    payload = await request.json()
    row = save_prompt(str(payload['name']).strip(), str(payload['prompt_text']), uid, bool(payload.get('activate', True)))
    log_admin_action(uid, 'prompt_version_create', details=json.dumps(payload, ensure_ascii=False))
    return web.json_response({'ok': True, 'prompt': _json(row)})


async def prompt_activate_api(request):
    uid = auth(request, {'owner'})
    activate_prompt(int(request.match_info['id']), uid)
    log_admin_action(uid, 'prompt_version_activate', details=str(request.match_info['id']))
    return web.json_response({'ok': True})


async def policies_api(request):
    uid = auth(request, {'owner'})
    if request.method == 'GET':
        return web.json_response({'items': _rows(policies())})
    payload = await request.json()
    set_policy(str(payload['key']), str(payload.get('title', payload['key'])), payload.get('config', {}), bool(payload.get('enabled', True)), uid)
    log_admin_action(uid, 'policy_update', details=json.dumps(payload, ensure_ascii=False))
    return web.json_response({'ok': True})


async def incidents_api(request):
    uid = auth(request, {'owner','moderator','analyst'})
    return web.json_response({'items': _rows(incidents(200, request.query.get('status')))})


async def incident_create_api(request):
    uid = auth(request, {'owner','moderator'})
    payload = await request.json()
    severity = str(payload.get('severity','medium')).lower()
    iid = create_incident(str(payload.get('service','unknown')), severity, str(payload['title']), str(payload.get('details','')), payload.get('deployment_id'))
    rollback_result = None
    if severity == 'critical' and os.getenv('AUTO_ROLLBACK_ENABLED','0').strip() == '1' and payload.get('rollback_deployment_id'):
        target = str(payload['rollback_deployment_id']).strip()
        rollback_result = await railway_rollback(target)
        record_rollback(iid, str(payload.get('service','unknown')), target, 'success' if rollback_result.get('ok') else 'failed', json.dumps(rollback_result, ensure_ascii=False))
    log_admin_action(uid, 'incident_create', details=json.dumps({**payload, 'rollback': rollback_result}, ensure_ascii=False))
    return web.json_response({'ok': True, 'incident_id': iid, 'rollback': rollback_result})


async def incident_resolve_api(request):
    uid = auth(request, {'owner','moderator'})
    payload = await request.json()
    resolve_incident(int(request.match_info['id']), uid, str(payload.get('note','')))
    log_admin_action(uid, 'incident_resolve', details=str(request.match_info['id']))
    return web.json_response({'ok': True})


async def rollback_api(request):
    uid = auth(request, {'owner'})
    payload = await request.json()
    target = str(payload.get('target_deployment_id','')).strip()
    if not target:
        raise web.HTTPBadRequest(text='target_deployment_id required')
    result = await railway_rollback(target)
    incident_id = payload.get('incident_id')
    if incident_id:
        record_rollback(int(incident_id), str(payload.get('service','unknown')), target, 'success' if result.get('ok') else 'failed', json.dumps(result, ensure_ascii=False))
    log_admin_action(uid, 'railway_rollback', details=json.dumps({'target':target,'result':result}, ensure_ascii=False))
    return web.json_response(result)


async def shadow_api(request):
    auth(request, {'owner','analyst'})
    return web.json_response({'items': _rows(shadow_runs(200))})

def create_app(bot):
    app=web.Application(middlewares=[rate_limit_middleware, error_middleware])
    app['bot']=bot
    # Serve the Mini App at both the root and /admin.
    app.router.add_get('/', index)
    app.router.add_get('/health', health)
    app.router.add_get('/admin', index)
    app.router.add_get('/admin/', index)
    app.router.add_get('/founder', founder_page)
    app.router.add_get('/founder/', founder_page)
    app.router.add_get('/founder/api', founder_api)
    app.router.add_get('/admin/{name}', static_file)
    app.router.add_get('/assets/{name}', static_file)
    app.router.add_get('/admin/api/ping', api_health)
    app.router.add_get('/admin/api/dashboard', dashboard)
    app.router.add_get('/admin/api/stories', stories)
    app.router.add_get('/admin/api/story/{id}', story)
    app.router.add_put('/admin/api/story/{id}', story_edit)
    app.router.add_post('/admin/api/story/{id}/ai', story_ai)
    app.router.add_post('/admin/api/story/{id}/ai-moderate', story_moderate_ai)
    app.router.add_post('/admin/api/story/{id}/ai-quality', story_quality_ai)
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
    app.router.add_get('/admin/api/settings', settings_api)
    app.router.add_put('/admin/api/settings', settings_update)
    app.router.add_post('/admin/api/story/{id}/lock', story_lock_api)
    app.router.add_delete('/admin/api/story/{id}/lock', story_unlock_api)
    app.router.add_get('/admin/api/monitoring', monitoring)
    app.router.add_get('/admin/api/employees', employees_api)
    app.router.add_get('/admin/api/employee/{id}', employee_api)
    app.router.add_put('/admin/api/employee/{id}/role', employee_role_api)
    app.router.add_put('/admin/api/employee/{id}/status', employee_status_api)
    app.router.add_put('/admin/api/employee/{id}/permission', employee_permission_api)
    app.router.add_get('/admin/api/lms', lms_api)
    app.router.add_post('/admin/api/lms/assign', lms_assign_api)
    app.router.add_post('/admin/api/lms/manage', lms_manage_api)
    app.router.add_put('/admin/api/lms/assignment/{id}', lms_update_api)
    app.router.add_get('/admin/api/leaderboard', leaderboard_api)
    app.router.add_get('/admin/api/kpi/dashboard', kpi_dashboard_api)
    app.router.add_get('/admin/api/training', training)
    app.router.add_post('/admin/api/training', training_assign_api)
    app.router.add_put('/admin/api/training/{id}', training_update_api)
    app.router.add_get('/admin/api/goals', goals_api)
    app.router.add_post('/admin/api/goals', goal_update_api)
    app.router.add_get('/admin/api/ai-priority', priority_queue_api)
    app.router.add_post('/admin/api/ai-priority', priority_create_api)
    app.router.add_route('*', '/admin/api/ai-control', ai_control_api)
    app.router.add_post('/admin/api/story/{id}/ai-safety', ai_safety_api)
    app.router.add_get('/admin/api/lms/full', lms_full_api)
    app.router.add_post('/admin/api/lms/test/submit', lms_test_submit_api)
    app.router.add_get('/admin/api/deployments', deployment_api)
    app.router.add_get('/admin/api/ops/workload', workload_api)
    app.router.add_get('/admin/api/ops/sla', sla_dashboard_api)
    app.router.add_route('*', '/admin/api/ops/prompts', prompts_api)
    app.router.add_post('/admin/api/ops/prompts/{id}/activate', prompt_activate_api)
    app.router.add_route('*', '/admin/api/ops/policies', policies_api)
    app.router.add_get('/admin/api/ops/incidents', incidents_api)
    app.router.add_post('/admin/api/ops/incidents', incident_create_api)
    app.router.add_post('/admin/api/ops/incidents/{id}/resolve', incident_resolve_api)
    app.router.add_post('/admin/api/ops/rollback', rollback_api)
    app.router.add_get('/admin/api/ops/shadow', shadow_api)
    return app


async def start_admin_web(bot):
    app=create_app(bot)
    runner=web.AppRunner(app); await runner.setup()
    port=int(os.getenv('PORT','8080'))
    site=web.TCPSite(runner,'0.0.0.0',port); await site.start()
    print(f'🖥 Admin Mini App server listening on :{port}')
    return runner
