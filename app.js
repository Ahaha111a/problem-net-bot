const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData || '';
const api = async (path, options = {}) => {
  const response = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
      ...(options.headers || {})
    }
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
};

if (tg.colorScheme === 'dark') document.body.classList.add('dark');

let state = { tab: 'dashboard', selected: new Set(), dashboard: null };
const tabs = [
  ['dashboard','🏠 Dashboard'],
  ['kanban','🛡 Модерация'],
  ['calendar','📅 Календарь'],
  ['queue','📋 Очередь'],
  ['support','💬 Поддержка'],
  ['complaints','⚠️ Жалобы'],
  ['analytics','📈 Аналитика'],
  ['roles','👥 Роли'],
  ['audit','📜 Аудит'],
  ['security','🔐 Безопасность'],
  ['notifications','🔔 Уведомления']
];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
}
function btn(text, fn, cls='btn') { return `<button class="${cls}" onclick="${fn}">${text}</button>`; }
function moscow(value) {
  if (!value) return '—';
  try { return new Date(value).toLocaleString('ru-RU', {timeZone:'Europe/Moscow'}); }
  catch { return String(value); }
}
function nav() {
  document.querySelector('#tabs').innerHTML = tabs.map(([id,label]) =>
    `<button onclick="setTab('${id}')">${label}</button>`
  ).join('');
}
async function setTab(tab) { state.tab = tab; await render(); }
async function load() {
  state.dashboard = await api('/admin/api/dashboard');
  document.querySelector('#role').textContent = state.dashboard.me.role;
  nav();
  await render();
}
async function render() {
  const c = document.querySelector('#content');
  try {
    if (state.tab === 'dashboard') return dashboard(c);
    if (state.tab === 'kanban') return kanban(c);
    if (state.tab === 'calendar') return calendar(c);
    if (state.tab === 'queue') return queue(c);
    if (state.tab === 'support') return support(c);
    if (state.tab === 'complaints') return complaints(c);
    if (state.tab === 'analytics') return analytics(c);
    if (state.tab === 'roles') return roles(c);
    if (state.tab === 'audit') return audit(c);
    if (state.tab === 'security') return security(c);
    if (state.tab === 'notifications') return notifications(c);
  } catch (e) {
    c.innerHTML = `<div class="card">❌ ${esc(e.message)}</div>`;
  }
}

function dashboard(c) {
  const s = state.dashboard.stats;
  c.innerHTML = `<div class="grid">${[
    ['👥',s.users],['📚',s.total],['⏳',s.waiting],['🗓',s.scheduled],
    ['🚀',s.publishing],['✅',s.published],['❌',s.rejected],['💬',s.support.open]
  ].map(x=>`<div class="card"><div>${x[0]}</div><div class="stat">${x[1]}</div></div>`).join('')}</div>
  <div class="card"><h3>🕐 Все времена — Europe/Moscow</h3><p>Планирование и отображение расписания работают по московскому времени.</p></div>
  <div class="card"><h3>🔴 SLA</h3>${state.dashboard.sla_breaches.length ? state.dashboard.sla_breaches.map(x=>`<div>#${x.id} · ${esc(x.priority)}</div>`).join('') : 'Нет просроченных обращений'}</div>`;
}

async function kanban(c) {
  const d = await api('/admin/api/stories');
  const groups = {waiting:[], publishing:[], scheduled:[], published:[], rejected:[]};
  d.items.forEach(x => {
    let k = x.status;
    if (k === 'waiting' && x.scheduled_at) k='scheduled';
    if (groups[k]) groups[k].push(x);
  });
  c.innerHTML = `<div class="row">${btn('☑️ Выбрать всё','selectAll()')} ${btn('❌ Массово отклонить','bulkReject()','btn danger')} ${btn('🗓 Снять расписание','bulkUnschedule()')} ${btn('⚡ Автопланирование','autoPlanSelected()','btn primary')}</div>
  <div class="kanban">${[['waiting','⏳ Новые'],['publishing','🚀 Публикация'],['scheduled','🗓 Запланированы'],['published','✅ Опубликованы'],['rejected','❌ Отклонены']].map(([k,t])=>`<section class="column" ondragover="event.preventDefault()" ondrop="dropStory(event,'${k}')"><h3>${t}</h3>${groups[k].map(storyCard).join('')}</section>`).join('')}</div>`;
}
function storyCard(x) {
  return `<article class="story" draggable="true" ondragstart="event.dataTransfer.setData('id','${x.id}')" onclick="openStory(${x.id})"><label onclick="event.stopPropagation()"><input type="checkbox" onchange="toggleSelect(${x.id},this.checked)"></label> <b>#${x.id}</b> <span class="badge">${esc(x.category||'без темы')}</span><p>${esc((x.text||'').slice(0,180))}</p>${x.scheduled_at?`<small>🗓 ${esc(moscow(x.scheduled_at))} МСК</small>`:''}</article>`;
}
async function openStory(id) {
  const d = await api('/admin/api/story/'+id); const s=d.story;
  document.body.insertAdjacentHTML('beforeend', `<div class="modal" id="modal"><div class="sheet"><h2>История #${s.id}</h2><p>User: ${s.user_id}</p>
  <textarea id="storyText">${esc(s.text)}</textarea><textarea id="postText">${esc(s.post_text||'')}</textarea>
  <div class="actions">${btn('💾 Сохранить','saveStory('+id+')','btn primary')}${btn('🤖 ИИ','retryAI('+id+')')}${btn('🛡 Проверка ИИ','moderateAI('+id+')')}${btn('👀 Предпросмотр','previewStory('+id+')')}${btn('🚀 Опубликовать','publishStory('+id+')','btn ok')}${btn('❌ Отклонить','rejectStory('+id+')','btn danger')}${btn('🗓 Запланировать','scheduleStory('+id+')')}${btn('👤 Написать пользователю','contactUser('+id+')')}${btn('🔁 Повторно опубликовать','repostStory('+id+')')}</div>
  <h3>BC — Версии</h3>${d.versions.map(v=>`<div class="card">v${v.version_no} · ${esc(v.change_type)} · ${esc(v.created_at)}<br>${btn('↩️ Восстановить','restoreVersion('+v.id+')')}</div>`).join('')}${btn('Закрыть',"document.getElementById('modal').remove()")}</div></div>`);
}
async function saveStory(id){await api('/admin/api/story/'+id,{method:'PUT',body:JSON.stringify({text:document.getElementById('storyText').value,post_text:document.getElementById('postText').value})});alert('Сохранено');}
async function retryAI(id){await api('/admin/api/story/'+id+'/ai',{method:'POST'});alert('ИИ обновлён');}
async function moderateAI(id){await api('/admin/api/story/'+id+'/ai-moderate',{method:'POST'});alert('Проверка ИИ завершена');}
async function publishStory(id){if(!confirm('Первое подтверждение: опубликовать?'))return;if(!confirm('Второе подтверждение: публикация необратима. Продолжить?'))return;await api('/admin/api/story/'+id+'/publish',{method:'POST'});document.getElementById('modal')?.remove();await render();}
async function rejectStory(id){if(!confirm('Отклонить историю?'))return;const reason=prompt('Причина');if(reason===null)return;await api('/admin/api/story/'+id+'/reject',{method:'POST',body:JSON.stringify({reason})});document.getElementById('modal')?.remove();await render();}
async function previewStory(id){const d=await api('/admin/api/story/'+id);alert((d.story.post_text||d.story.text||'').slice(0,4000));}
async function contactUser(id){await api('/admin/api/story/'+id+'/contact',{method:'POST'});alert('Пользователю отправлено уведомление');}
async function scheduleStory(id){const raw=prompt('Дата и время по Москве: 2026-08-20 18:30');if(!raw)return;const normalized=raw.includes('T')?raw.replace(' ','T'):raw.replace(' ','T');await api('/admin/api/story/'+id+'/schedule',{method:'POST',body:JSON.stringify({scheduled_at:normalized})});alert('Запланировано по МСК');await render();}
async function repostStory(id){const raw=prompt('Дата и время повторной публикации по Москве: 2026-08-25 18:30');if(!raw)return;await api('/admin/api/story/'+id+'/repost',{method:'POST',body:JSON.stringify({scheduled_at:raw.replace(' ','T')})});alert('Повторная публикация запланирована');}
async function restoreVersion(id){await api('/admin/api/version/'+id+'/restore',{method:'POST'});alert('Версия восстановлена');document.getElementById('modal')?.remove();await render();}
function toggleSelect(id,on){on?state.selected.add(Number(id)):state.selected.delete(Number(id));}
async function dropStory(event,status){const id=event.dataTransfer.getData('id');if(status==='rejected')await api('/admin/api/story/'+id+'/reject',{method:'POST',body:JSON.stringify({reason:'Перемещено в отклонённые через Mini App'})});else if(status==='scheduled')await scheduleStory(id);else if(status==='published')await publishStory(id);await render();}
function selectAll(){document.querySelectorAll('.story input').forEach(x=>{x.checked=true;toggleSelect(x.closest('.story').querySelector('b').textContent.slice(1),true);});}
async function bulkReject(){await api('/admin/api/bulk',{method:'POST',body:JSON.stringify({ids:[...state.selected],action:'reject'})});state.selected.clear();await render();}
async function bulkUnschedule(){await api('/admin/api/bulk',{method:'POST',body:JSON.stringify({ids:[...state.selected],action:'unschedule'})});state.selected.clear();await render();}
async function autoPlanSelected(){if(!state.selected.size)return alert('Сначала выберите истории');const start=prompt('Старт по МСК: 2026-08-20 18:00');if(!start)return;const interval=prompt('Интервал между публикациями в минутах','60');await api('/admin/api/content/auto-plan',{method:'POST',body:JSON.stringify({ids:[...state.selected],start_at:start.replace(' ','T'),interval_minutes:Number(interval||60)})});state.selected.clear();alert('Автопланирование выполнено');await render();}

async function calendar(c){const d=await api('/admin/api/content/analytics');const items=d.queue;c.innerHTML=`<h2>BV — Календарь публикаций</h2><p>Все даты показываются по Europe/Moscow.</p><div class="calendar">${Array.from({length:31},(_,i)=>{const day=i+1;const rows=items.filter(x=>new Date(x.scheduled_at).toLocaleString('en-US',{timeZone:'Europe/Moscow'}).split('/')[1]==day);return `<div class="day"><b>${day}</b>${rows.map(x=>`<div>#${x.id} ${esc(moscow(x.scheduled_at))}</div>`).join('')}</div>`}).join('')}</div><div class="card"><h3>BW — Автопланирование</h3>${btn('⚡ Автопланировать выбранные','autoPlanSelected()','btn primary')}</div>`;}
async function queue(c){const d=await api('/admin/api/content/analytics');c.innerHTML=`<h2>BX — Очередь публикаций</h2>${d.queue.map(x=>`<div class="card"><b>#${x.id}</b> · ${esc(x.status)}<br>🕐 ${esc(moscow(x.scheduled_at))} МСК</div>`).join('')||'Очередь пуста'}<div class="card"><h3>BY — Повторные публикации</h3>${(await api('/admin/api/reposts')).items.map(x=>`#${x.story_id} · ${esc(moscow(x.scheduled_at))} · ${x.status}`).join('<br>')||'Нет запланированных повторов'}</div>`;}

async function support(c){const d=await api('/admin/api/support/metrics');const m=d.metrics;c.innerHTML=`<h2>BP / BR — Поддержка</h2><div class="grid"><div class="card">Всего: <b>${m.total||0}</b></div><div class="card">Открыто: <b>${m.open_count||0}</b></div><div class="card">BS — средний первый ответ: <b>${fmtSeconds(m.avg_first_response_seconds)}</b></div><div class="card">BT — среднее решение: <b>${fmtSeconds(m.avg_resolution_seconds)}</b></div></div><h3>BU — Нагрузка</h3>${d.queue.map(x=>`<div class="card"><b>#${x.id}</b> · User ${x.user_id} · ${x.assignment_status}<br>Приоритет: ${x.priority}<br>${esc(x.first_message||'')}</div>`).join('')||'Очередь пуста'}`;}
function fmtSeconds(v){if(v==null)return'—';v=Number(v);if(v<60)return Math.round(v)+' сек';if(v<3600)return Math.round(v/60)+' мин';return (v/3600).toFixed(1)+' ч';}
async function complaints(c){const d=await api('/admin/api/complaints');c.innerHTML=`<h2>AB — Жалобы</h2>${d.items.map(x=>`<div class="card"><b>#${x.story_id}</b> ${esc(x.reason)}<br>${x.status} · ${x.priority}${btn('В работу',"complaintUpdate("+x.id+",'in_progress') )}${btn('Закрыть',"complaintUpdate("+x.id+",'closed') )}</div>`).join('')||'Жалоб нет'}`;}
async function complaintUpdate(id,status){await api('/admin/api/complaint/'+id,{method:'PUT',body:JSON.stringify({status})});await render();}
async function analytics(c){const d=await api('/admin/api/content/analytics');const a=await api('/admin/api/analytics');c.innerHTML=`<h2>AS / CF / CH / CI</h2><div class="grid"><div class="card">Пользователи: ${a.analytics.users}</div><div class="card">Истории: ${a.analytics.stories}</div><div class="card">Реакции: ${a.analytics.reactions}</div><div class="card">Диалоги: ${a.analytics.dialogs}</div></div><div class="card"><h3>CF — Воронка</h3>Пользователи: ${d.funnel.users}<br>Создали историю: ${d.funnel.stories}<br>Опубликовано: ${d.funnel.published}<br>Обращались в поддержку: ${d.funnel.support_users}</div><div class="card"><h3>CH — Лучшие категории</h3>${d.categories.map(x=>`${esc(x.category)} — ${x.stories} историй / ${x.published} опубликовано`).join('<br>')}</div><div class="card"><h3>CI — Лучшие часы публикации</h3>${d.hours.map(x=>`${String(x.hour).padStart(2,'0')}:00 МСК — ${x.count}`).join('<br>')}</div><div class="card"><h3>AU / AV / AW</h3>${a.top.map(x=>`#${x.id} — ${x.reactions} реакций`).join('<br>')}<hr>${a.moderators.map(x=>`${x.admin_id}: ${x.action} — ${x.count}`).join('<br>')}</div>`;}
async function dialogs(c){const d=await api('/admin/api/dialogs');c.innerHTML=`<h2>AJ / AK / AL / AN — Поддержка</h2>${d.items.map(x=>`<div class="card"><b>#${x.id}</b> User ${x.user_id}<br>${esc(x.first_message||'')}<div class="actions">${btn('🔴 Critical',"setPriority("+x.id+",'critical')")}${btn('🟠 High',"setPriority("+x.id+",'high')")}${btn('🟡 Normal',"setPriority("+x.id+",'normal')")}${btn('🟢 Low',"setPriority("+x.id+",'low')")}${btn('👤 Назначить себе',"dialogAction("+x.id+",'assign')")}${btn('⏳ Ждём',"dialogAction("+x.id+",'waiting')")}${btn('✅ Решён',"dialogAction("+x.id+",'resolved')")}${btn('🔴 Закрыть',"dialogAction("+x.id+",'close')")}</div><textarea id="msg${x.id}" placeholder="Ответ пользователю"></textarea>${btn('💬 Отправить',"sendDialog("+x.id+")",'btn primary')}</div>`).join('')||'Нет открытых диалогов'}`;}
async function sendDialog(id){const el=document.getElementById('msg'+id);if(!el.value.trim())return;await api('/admin/api/dialog/'+id+'/message',{method:'POST',body:JSON.stringify({text:el.value})});el.value='';await render();}
async function dialogAction(id,a){await api('/admin/api/dialog/'+id+'/'+a,{method:'POST'});await render();}
async function setPriority(id,p){await api('/admin/api/dialog/'+id,{method:'PUT',body:JSON.stringify({priority:p})});await render();}
async function roles(c){const d=await api('/admin/api/roles');c.innerHTML=`<h2>AO — Роли</h2>${d.items.map(x=>`<div class="card"><b>${x.user_id}</b> — ${x.role}<select onchange="setRole(${x.user_id},this.value)"><option value="owner" ${x.role==='owner'?'selected':''}>owner</option><option value="moderator" ${x.role==='moderator'?'selected':''}>moderator</option><option value="support" ${x.role==='support'?'selected':''}>support</option><option value="analyst" ${x.role==='analyst'?'selected':''}>analyst</option><option value="editor" ${x.role==='editor'?'selected':''}>editor</option></select></div>`).join('')}`;}
async function setRole(id,role){await api('/admin/api/role/'+id,{method:'PUT',body:JSON.stringify({role})});}
async function audit(c){const d=await api('/admin/api/audit');c.innerHTML=`<h2>AP — Аудит</h2>${d.items.map(x=>`<div class="card">${esc(x.created_at)} · ${x.admin_id} · ${esc(x.action)}<br>${esc(x.details||'')}</div>`).join('')}`;}
async function security(c){const d=await api('/admin/api/security');c.innerHTML=`<h2>BZ — Журнал безопасности</h2>${d.items.map(x=>`<div class="card">${esc(x.created_at)} · admin ${x.admin_id}<br><b>${esc(x.action)}</b><br>${esc(x.details||'')}</div>`).join('')}`;}
async function notifications(c){const d=await api('/admin/api/notifications');c.innerHTML=`<h2>BF — Уведомления</h2>${d.items.map(x=>`<div class="card"><b>${esc(x.title)}</b><p>${esc(x.body)}</p>${x.read_at?'':'🔵 Непрочитано'}</div>`).join('')||'Нет уведомлений'}`;}

load().catch(e => { document.querySelector('#content').innerHTML = `<div class="card">❌ ${esc(e.message)}<br><br>Если это 404 — проверьте, что ADMIN_MINIAPP_URL указывает на домен Railway, а не на несуществующий /admin путь.</div>`; });
