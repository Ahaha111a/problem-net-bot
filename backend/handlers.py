from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import CHANNEL_ID, CHANNEL_USERNAME, CHANNEL_FIRST_MESSAGE_ID
from database import create_story,update_ai_result,update_post,register_user,create_support_dialog,get_open_dialog_by_user,add_support_message,get_story,create_ai_priority
from ai import analyze_story,run_safety_pipeline
from post_generator import create_post
from keyboards import main_keyboard,channel_first_keyboard

router=Router()
class StoryState(StatesGroup):
    waiting_for_story=State(); support_waiting=State()

@router.message(F.text == '/start')
async def start_handler(message:Message,state:FSMContext):
    await state.clear(); register_user(message.from_user.id)
    await message.answer('💙 <b>Расскажите свою историю.</b>\n\nМожно написать всё, что вас беспокоит.',reply_markup=main_keyboard())

@router.message(F.text == '/help')
async def help_handler(message:Message,state:FSMContext):
    await state.clear(); await message.answer('ℹ️ Помощь\n\n📝 Поделиться историей — отправить историю анонимно.\n📖 Смотреть истории — открыть канал.\n🆘 Экстренная поддержка — связаться с сотрудником.',reply_markup=main_keyboard())

@router.message(F.text == '📝 Поделиться историей')
async def share_story(message:Message,state:FSMContext):
    await state.clear(); register_user(message.from_user.id); await state.set_state(StoryState.waiting_for_story)
    await message.answer('💙 <b>Расскажите свою историю.</b>\n\nМожно написать всё, что вас беспокоит.\n\nОтправьте текст следующим сообщением.')

@router.message(F.text == '📖 Смотреть истории')
async def stories_link(message:Message,state:FSMContext):
    await state.clear(); await message.answer('📖 <b>Истории</b>\n\nОткрывайте первое сообщение канала — дальше можно листать публикации.',reply_markup=channel_first_keyboard())

@router.message(F.text == '💡 Совет дня')
async def tip(message:Message,state:FSMContext):
    await state.clear(); await message.answer('💡 Не пытайтесь решить всё сразу. Выберите один небольшой шаг, который можно сделать сегодня.',reply_markup=main_keyboard())

@router.message(F.text == '📚 Полезные материалы')
async def materials(message:Message,state:FSMContext):
    await state.clear(); await message.answer('📚 Здесь будут материалы о тревоге, стрессе, самооценке, отношениях и эмоциональном состоянии.',reply_markup=main_keyboard())

@router.message(F.text == '❤️ Поддержка')
async def support(message:Message,state:FSMContext):
    await state.clear(); await message.answer('❤️ Ты не обязан справляться со всем один. Если хочется поговорить — воспользуйся экстренной поддержкой.',reply_markup=main_keyboard())

@router.message(F.text == '🆘 Экстренная поддержка')
async def emergency_support(message:Message,state:FSMContext):
    await state.clear(); await state.set_state(StoryState.support_waiting); await message.answer('🆘 <b>Опишите, что происходит.</b>\n\nСообщение увидит сотрудник поддержки. Отправьте его следующим сообщением.')

@router.message(StoryState.waiting_for_story)
async def receive_story(message:Message,state:FSMContext):
    text=(message.text or '').strip()
    if not text: await message.answer('❗ Отправьте историю текстом.'); return
    if len(text)<10: await message.answer('✏️ История слишком короткая. Напишите немного подробнее.'); return
    story_id=create_story(message.from_user.id,text); await message.answer('⏳ Спасибо! История сохранена и отправлена на обработку.',reply_markup=main_keyboard())
    try: update_ai_result(story_id,await analyze_story(text))
    except Exception: update_ai_result(story_id,'⚠️ Автоматический анализ временно недоступен. История сохранена.')
    try: update_post(story_id,await create_post(text))
    except Exception: update_post(story_id,text)
    try:
        current=get_story(story_id); safety=await run_safety_pipeline(text,current['post_text'] if current else '',story_id)
        if safety.get('recommendation') in {'manual_review','reject'}:
            create_ai_priority(story_id,'critical' if float(safety.get('risk_score',0))>=.9 else 'high',str(safety.get('primary',{}).get('reason','AI safety review')))
    except Exception as exc: create_ai_priority(story_id,'high',f'Safety pipeline unavailable: {exc}')
    await state.clear()

@router.message(StoryState.support_waiting)
async def support_message(message:Message,state:FSMContext):
    text=(message.text or '').strip()
    if not text: await message.answer('❗ Отправьте сообщение текстом.'); return
    dialog=get_open_dialog_by_user(message.from_user.id)
    if dialog: add_support_message(dialog['id'],message.from_user.id,'user',text)
    else: create_support_dialog(message.from_user.id,text)
    await state.clear(); await message.answer('💙 Сообщение передано сотруднику. Мы постараемся ответить как можно быстрее.',reply_markup=main_keyboard())
