from aiogram import Router,F
from aiogram.types import Message,ReplyKeyboardRemove,CallbackQuery,InlineKeyboardMarkup,InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from config import ADMIN_IDS
from database import is_admin_active,get_admin_role,get_stats,get_all_stories,get_waiting_stories,get_story,get_open_dialogs,get_dialog,get_moderator_performance,get_system_health,get_system_errors,get_ai_model_configs,get_ai_model_health,get_ai_priority_queue,get_lms_full,get_extended_stats,get_kpi_dashboard,get_all_settings,get_ai_checks
from keyboards import admin_keyboard,moderation_keyboard
from staff_ops import employees, employee, permissions, role_history, promotion_history, violations, courses, assignments, change_role, set_status, set_permission
from notifications import notify_user
router=Router()

def is_admin(uid): return int(uid) in {int(x) for x in ADMIN_IDS} and is_admin_active(uid)

def story_text(s):
    return (f"📥 <b>История #{s['id']}</b>\n<b>Статус:</b> {s['status']}\n<b>Пользователь:</b> {s['user_id']}\n\n💭 <b>Текст:</b>\n{s['text']}\n\n🧠 <b>Анализ ИИ:</b>\n{s.get('ai_result') or '—'}\n\n🛡 <b>ИИ-модерация:</b>\n{s.get('ai_moderation_result') or '—'}\n\n📌 <b>Готовый пост:</b>\n{s.get('post_text') or '—'}")

@router.message(F.text=='/start')
async def start(message:Message,state:FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id): await message.answer('Этот бот предназначен только для сотрудников проекта.'); return
    await message.answer('🧹',reply_markup=ReplyKeyboardRemove()); await message.answer('🛡 <b>Панель сотрудников ProblemNet</b>\n\nВсе основные операции доступны здесь, даже если Mini App временно недоступен.',reply_markup=admin_keyboard())

@router.message(F.text=='🖥 Админ-панель')
async def admin_app(message:Message):
    if is_admin(message.from_user.id): await message.answer('🖥 Mini App доступен кнопкой выше. При сбое используйте разделы этой панели.')

@router.message(F.text.in_({'👑 Кабинет основателя','👑 Founder Center'}))
async def founder_center(message:Message):
    if not is_admin(message.from_user.id): return
    if get_admin_role(message.from_user.id)!='owner': await message.answer('🔒 Раздел доступен только владельцу.'); return
    s=get_extended_stats(); k=get_kpi_dashboard(30); models=get_ai_model_configs(); health=get_ai_model_health(20); queue=get_ai_priority_queue(20); settings=get_all_settings(); checks=get_ai_checks()
    lines=[f"👑 <b>Founder Control Center</b>",f"👥 Пользователи: {s['users']}",f"📚 Истории: {s['total']}",f"⏳ Модерация: {s['waiting']}",f"✅ Опубликовано: {s['published']}",f"❌ Отклонено: {s['rejected']}",f"💬 Поддержка: {s['support']['open']}",f"🤖 AI queue: {len(queue)}",f"⚙️ Settings: {len(settings)}",f"🧪 AI checks: {len(checks)}",'','🤖 <b>AI models</b>']
    lines += [f"• {m['model']} — {'🟢' if m['enabled'] else '⚪'} priority={m['priority']}" for m in models[:10]]
    lines += ['','📈 <b>KPI</b>']+[f"• {r['admin_id']}: score {r['score']} | publish {r['published']} | moderate {r['moderated']} | errors {r['errors']}" for r in k.get('ranking',[])[:10]]
    await message.answer('\n'.join(lines))

@router.message(F.text=='⏳ Модерация')
async def moderation(message:Message):
    if not is_admin(message.from_user.id): return
    rows=get_waiting_stories()
    if not rows: await message.answer('🟢 Историй на модерации нет.'); return
    await message.answer(f'⏳ <b>Историй на модерации: {len(rows)}</b>')
    for s in rows[:30]: await message.answer(story_text(s),reply_markup=moderation_keyboard(s['id']))

@router.message(F.text=='📊 Статистика')
async def stats(message:Message):
    if not is_admin(message.from_user.id): return
    s=get_extended_stats(); await message.answer(f"📊 <b>Статистика</b>\n\n👥 Пользователи: {s['users']}\n📚 Историй: {s['total']}\n⏳ На модерации: {s['waiting']}\n✅ Опубликовано: {s['published']}\n❌ Отклонено: {s['rejected']}\n📅 Сегодня опубликовано: {s['published_today']}\n💬 Открытых диалогов: {s['support']['open']}")

@router.message(F.text=='📁 Все истории')
async def all_stories(message:Message):
    if not is_admin(message.from_user.id): return
    rows=get_all_stories()[:20]
    if not rows: await message.answer('📁 Историй пока нет.'); return
    for s in rows: await message.answer(story_text(s),reply_markup=moderation_keyboard(s['id']) if s['status']=='waiting' else None)

@router.message(F.text=='💬 Поддержка')
async def support(message:Message):
    if not is_admin(message.from_user.id): return
    rows=get_open_dialogs()[:20]
    if not rows: await message.answer('💬 Открытых диалогов нет.'); return
    for d in rows:
        await message.answer(f"💬 <b>Диалог #{d['id']}</b>\nПользователь: {d['user_id']}\nСтатус: {d['support_status']}\n\n{d.get('last_message') or d.get('first_message') or '—'}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💬 Ответить',callback_data=f'support:reply:{d["id"]}'),InlineKeyboardButton(text='✅ Закрыть',callback_data=f'support:close:{d["id"]}')]]))

class SupportState(StatesGroup): waiting=State()

@router.callback_query(F.data.startswith('support:reply:'))
async def support_reply(q:CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    did=int(q.data.rsplit(':',1)[1]); await state.update_data(dialog_id=did); await state.set_state(SupportState.waiting); await q.answer(); await q.message.answer(f'💬 Диалог #{did}: отправьте текст ответа.')

@router.message(SupportState.waiting)
async def support_send(message:Message,state:FSMContext):
    if not is_admin(message.from_user.id): await state.clear(); return
    from database import add_support_message,record_kpi_event
    data=await state.get_data(); did=int(data['dialog_id']); d=get_dialog(did); text=(message.text or '').strip()
    if not d or not text: await message.answer('❗ Диалог не найден.'); await state.clear(); return
    add_support_message(did,message.from_user.id,'admin',text[:4000]); record_kpi_event(message.from_user.id,'support_response')
    try: await notify_user(d['user_id'],f'💬 <b>Сообщение поддержки:</b>\n\n{text[:4000]}')
    except Exception as exc: await message.answer(f'⚠️ Ответ сохранён, но Telegram не принял сообщение: {exc}')
    await state.clear(); await message.answer('✅ Ответ отправлен.')

@router.callback_query(F.data.startswith('support:close:'))
async def support_close(q:CallbackQuery):
    if not is_admin(q.from_user.id): await q.answer('Нет доступа',show_alert=True); return
    from database import close_dialog
    close_dialog(int(q.data.rsplit(':',1)[1])); await q.answer('Диалог закрыт'); await q.message.edit_reply_markup(reply_markup=None)

@router.message(F.text=='📈 KPI')
async def kpi(message:Message):
    if not is_admin(message.from_user.id): return
    d=get_kpi_dashboard(30); rows=d.get('ranking',[]); await message.answer('🏆 <b>KPI за 30 дней</b>\n\n'+('\n'.join(f"• {r['admin_id']}: score {r['score']} | publish {r['published']} | moderate {r['moderated']} | errors {r['errors']}" for r in rows) if rows else 'Данных пока нет.'))

@router.message(F.text=='🖥 Мониторинг')
async def monitoring(message:Message):
    if not is_admin(message.from_user.id): return
    h=get_system_health(); e=get_system_errors(10); await message.answer('🖥 <b>Мониторинг</b>\n\n'+('\n'.join(f"• {x['service']}: {x['status']} — {x['details']}" for x in h[:20]) or '🟢 Системное состояние не сообщило проблем.')+'\n\n❗ Ошибки:\n'+('\n'.join(f"• {x['service']}: {x['message']}" for x in e) or 'нет'))

@router.message(F.text=='🤖 AI Control')
async def ai_control(message:Message):
    if not is_admin(message.from_user.id): return
    models=get_ai_model_configs(); health=get_ai_model_health(30); q=get_ai_priority_queue(20); await message.answer('🤖 <b>AI Control Center</b>\n\n'+('\n'.join(f"• {m['model']} — {'🟢' if m['enabled'] else '⚪'} priority={m['priority']}" for m in models[:15]) or 'Модели не настроены.')+f'\n\nОчередь: {len(q)}\nHealth: {len(health)}')

@router.message(F.text=='👥 Сотрудники')
async def staff(message:Message):
    if not is_admin(message.from_user.id): return
    rows=employees()
    if not rows:
        await message.answer('👥 Сотрудников нет.'); return
    await message.answer('👥 <b>Сотрудники</b>\n\nНажмите на сотрудника для профиля и управления ролью/статусом.')
    for r in rows[:50]:
        target=int(r['admin_id'])
        await message.answer(f"👤 <b>{r.get('full_name') or 'Без имени'}</b>\nID: {target}\nСтатус: {r.get('status')}\nРоль: {r.get('role') or 'moderator'}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Открыть профиль',callback_data=f'staff:view:{target}')]]))

@router.message(F.text=='🎓 Обучение')
async def training(message:Message):
    if not is_admin(message.from_user.id): return
    d=get_lms_full(); await message.answer(f"🎓 <b>LMS</b>\n\nКурсов: {len(d['courses'])}\nУроков: {len(d['lessons'])}\nТестов: {len(d['tests'])}\nПрактика: {len(d['practical_tasks'])}\nЭкзамены: {len(d['exams'])}\nНазначения: {len(d['assignments'])}\n\nСертификатов нет — они удалены из концепции.")

# =========================================================
# EMPLOYEE ACTIONS (bot fallback for Mini App)
# =========================================================

@router.callback_query(F.data.startswith('staff:role:'))
async def staff_role_callback(q: CallbackQuery):
    if not is_admin(q.from_user.id) or get_admin_role(q.from_user.id) != 'owner':
        await q.answer('Только владелец', show_alert=True); return
    _, _, target, role = q.data.split(':', 3)
    if role not in {'owner','moderator','support','analyst','editor'}:
        await q.answer('Недопустимая роль', show_alert=True); return
    change_role(int(target), role, q.from_user.id, 'Из панели Moderator Bot')
    await q.answer(f'Роль: {role}')
    await q.message.answer(f'✅ Сотруднику {target} назначена роль <b>{role}</b>.')


@router.callback_query(F.data.startswith('staff:status:'))
async def staff_status_callback(q: CallbackQuery):
    if not is_admin(q.from_user.id) or get_admin_role(q.from_user.id) != 'owner':
        await q.answer('Только владелец', show_alert=True); return
    _, _, target, status = q.data.split(':', 3)
    if status not in {'trainee','employee','senior','leader','fired'}:
        await q.answer('Недопустимый статус', show_alert=True); return
    set_status(int(target), status, q.from_user.id, 'Из панели Moderator Bot')
    await q.answer(f'Статус: {status}')
    await q.message.answer(f'✅ Сотруднику {target} установлен статус <b>{status}</b>.')


@router.callback_query(F.data.startswith('staff:view:'))
async def staff_view_callback(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        await q.answer('Нет доступа', show_alert=True); return
    target=int(q.data.rsplit(':',1)[1]); e=employee(target)
    if not e:
        await q.answer('Сотрудник не найден', show_alert=True); return
    lines=[f'👤 <b>{e.get("full_name") or "Сотрудник"}</b>',f'ID: {target}',f'Статус: {e.get("status")}',f'Роль: {e.get("role") or "moderator"}',f'Должность: {e.get("position") or "—"}','','🔐 <b>Разрешения</b>']
    perms=permissions(target); lines += [f'• {p["permission"]}: {"✅" if p["enabled"] else "❌"}' for p in perms] or ['• нет']
    kb=[]
    if get_admin_role(q.from_user.id)=='owner':
        kb += [[InlineKeyboardButton(text='👤 Moderator',callback_data=f'staff:role:{target}:moderator'),InlineKeyboardButton(text='💬 Support',callback_data=f'staff:role:{target}:support')],
               [InlineKeyboardButton(text='📊 Analyst',callback_data=f'staff:role:{target}:analyst'),InlineKeyboardButton(text='✏️ Editor',callback_data=f'staff:role:{target}:editor')],
               [InlineKeyboardButton(text='🟢 Employee',callback_data=f'staff:status:{target}:employee'),InlineKeyboardButton(text='⭐ Senior',callback_data=f'staff:status:{target}:senior')],
               [InlineKeyboardButton(text='🚫 Уволить',callback_data=f'staff:status:{target}:fired')]]
    await q.message.answer('\n'.join(lines),reply_markup=InlineKeyboardMarkup(inline_keyboard=kb) if kb else None)
    await q.answer()
