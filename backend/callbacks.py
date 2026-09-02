from aiogram import Router,F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from config import ADMIN_IDS,CHANNEL_ID,CHANNEL_USERNAME
from database import get_story,get_latest_safety_decision,publish_story,reject_story,get_story_reaction_counts,set_story_reaction,get_user_story_reaction,lock_story,is_admin_active,unlock_story,update_story_content,log_admin_action,get_admin_role,record_kpi_event,update_ai_result
from keyboards import channel_story_keyboard,published_story_keyboard
from notifications import notify_user
from ai import analyze_story
router=Router()
callback_router=router

def get_channel_message_link(bot,message_id):
    if CHANNEL_USERNAME: return f'https://t.me/{CHANNEL_USERNAME}/{message_id}'
    raw=str(CHANNEL_ID)
    return f'https://t.me/c/{raw[4:]}/{message_id}' if raw.startswith('-100') else None

def allowed(uid): return int(uid) in {int(x) for x in ADMIN_IDS} and is_admin_active(uid)

@router.callback_query(F.data.startswith('story:publish:'))
async def publish_callback(q:CallbackQuery):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); story=get_story(sid)
    if not story: await q.answer('История не найдена',show_alert=True); return
    try:
        safety=get_latest_safety_decision(sid); role=get_admin_role(q.from_user.id)
        if safety and safety.get('recommendation')!='publish' and role!='owner': await q.answer('Нужна ручная safety-проверка. Владелец может сделать override.',show_alert=True); return
        sent=await q.bot.send_message(CHANNEL_ID,story['post_text'] or story['text'])
        publish_story(sid,sent.message_id); link=get_channel_message_link(q.bot,sent.message_id); counts=get_story_reaction_counts(sid)
        if link: await sent.edit_reply_markup(reply_markup=channel_story_keyboard(sid,link,counts))
        record_kpi_event(q.from_user.id,'publish'); await q.answer('Опубликовано')
        await q.message.edit_text((q.message.text or '')+'\n\n✅ <b>ОПУБЛИКОВАНО</b>',reply_markup=None)
        try:
            text='🎉 <b>Ваша история была опубликована!</b>\n\nСпасибо, что поделились ей с нами 💙'
            await notify_user(story['user_id'],text,reply_markup=published_story_keyboard(link,sid))
        except Exception as exc: log_admin_action(q.from_user.id,'publish_user_notify_error',story_id=sid,user_id=story['user_id'],details=str(exc))
        log_admin_action(q.from_user.id,'publish',story_id=sid,user_id=story['user_id'])
    except Exception as exc: await q.answer(f'Ошибка: {exc}',show_alert=True)

@router.callback_query(F.data.startswith('story:reject:'))
async def reject_callback(q:CallbackQuery):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); story=get_story(sid)
    if not story: await q.answer('История не найдена',show_alert=True); return
    reject_story(sid,'Отклонено модератором'); record_kpi_event(q.from_user.id,'reject'); await q.answer('История отклонена'); await q.message.edit_text((q.message.text or '')+'\n\n❌ <b>ОТКЛОНЕНО</b>',reply_markup=None); log_admin_action(q.from_user.id,'reject',story_id=sid,user_id=story['user_id'])

@router.callback_query(F.data.startswith('story:lock:'))
async def lock_callback(q:CallbackQuery):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); row=lock_story(sid,q.from_user.id)
    if row and int(row['admin_id'])!=int(q.from_user.id): await q.answer(f"Историю уже редактирует {row['admin_id']}",show_alert=True); return
    await q.answer('История заблокирована за вами')

@router.callback_query(F.data.startswith('story:unlock:'))
async def unlock_callback(q:CallbackQuery):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); unlock_story(sid,q.from_user.id); await q.answer('Разблокировано')

class ModeratorEditState(StatesGroup): waiting_for_post=State()

@router.callback_query(F.data.startswith('story:edit:'))
async def edit_callback(q:CallbackQuery,state:FSMContext):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); row=lock_story(sid,q.from_user.id)
    if row and int(row['admin_id'])!=int(q.from_user.id): await q.answer(f"Историю уже редактирует {row['admin_id']}",show_alert=True); return
    await state.update_data(edit_story_id=sid); await state.set_state(ModeratorEditState.waiting_for_post); await q.answer(); await q.message.answer(f'✏️ История #{sid}. Отправьте новый готовый текст поста.')

@router.message(ModeratorEditState.waiting_for_post)
async def receive_edit(message,state):
    if not allowed(message.from_user.id): await state.clear(); return
    data=await state.get_data(); sid=int(data['edit_story_id']); row=get_story(sid); text=(message.text or '').strip()
    if not row or len(text)<10: await message.answer('❗ Текст слишком короткий.'); return
    update_story_content(sid,row['text'],text,message.from_user.id); unlock_story(sid,message.from_user.id); await state.clear(); await message.answer(f'✅ Готовый пост истории #{sid} обновлён.')

@router.callback_query(F.data.startswith('story:ai:'))
async def ai_callback(q:CallbackQuery):
    if not allowed(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    sid=int(q.data.rsplit(':',1)[1]); row=get_story(sid)
    if not row: await q.answer('История не найдена',show_alert=True); return
    await q.answer('ИИ анализирует…')
    try:
        result=await analyze_story(row['text']); update_ai_result(sid,result); await q.message.answer(f'🤖 <b>ИИ-анализ истории #{sid}</b>\n\n{result}')
    except Exception as exc: await q.message.answer(f'❌ ИИ-анализ не выполнен: {exc}')

@router.callback_query(F.data.startswith('react:'))
async def reaction_callback(q:CallbackQuery):
    parts=q.data.split(':'); sid=int(parts[1]); reaction=parts[2]; current=get_user_story_reaction(sid,q.from_user.id); set_story_reaction(sid,q.from_user.id,None if current==reaction else reaction); await q.message.edit_reply_markup(reply_markup=channel_story_keyboard(sid,None,get_story_reaction_counts(sid))); await q.answer('Готово')
