(() => {
  'use strict';
  const tg = window.Telegram?.WebApp;
  const $ = (s) => document.querySelector(s);
  const state = { tab:'dashboard', story:null, versions:[], selected:new Set(), dashboard:null, settings:null };

  if (!tg) { document.body.innerHTML='<div class="fatal">❌ Откройте Mini App внутри Telegram.</div>'; return; }
  tg.ready(); tg.expand();
  const initData = tg.initData || '';
  if (!initData) { document.body.innerHTML='<div class="fatal">❌ Telegram не передал данные авторизации. Закройте Mini App и откройте его из второго бота.</div>'; return; }

  const esc = v => String(v ?? '').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const moscow = v => { if(!v) return '—'; try{return new Date(v).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'});}catch{return String(v)} };
  const api = async (path, options={}) => {
    const r = await fetch(path,{...options,headers:{'Content-Type':'application/json','X-Telegram-Init-Data':initData,...(options.headers||{})}});
    const text=await r.text(); let data={}; try{data=text?JSON.parse(text):{}}catch{data={error:text}};
    if(!r.ok) throw new Error(`${r.status}: ${data.error||data.details||text||r.statusText}`);
    return data;
  };
  const post = (p,b={}) => api(p,{method:'POST',body:JSON.stringify(b)});
  const put = (p,b={}) => api(p,{method:'PUT',body:JSON.stringify(b)});
  const del = p => api(p,{method:'DELETE'});

  const tabs=[
    ['dashboard','🏠 Главная'],['kanban','🛡 Модерация'],['calendar','📅 Планировщик'],['queue','⚡ Очередь'],
    ['support','💬 Поддержка'],['complaints','⚠️ Жалобы'],['analytics','📈 Аналитика'],['employees','👥 Сотрудники'],
    ['training','🎓 Обучение'],['goals','🎯 Цели'],['settings','⚙️ Настройки'],['monitoring','🖥 Мониторинг'],['audit','📜 Аудит']
  ];
  window.setTab=async id=>{state.tab=id;await render()};

  function nav(){
    $('#tabs').innerHTML=tabs.map(([id,label])=>`<button class="tab ${state.tab===id?'active':''}" onclick="setTab('${id}')">${label}</button>`).join('');
  }
  async function load(){
    state.dashboard=await api('/admin/api/dashboard');
    $('#role').textContent=state.dashboard.me.role;
    nav(); await render();
  }
  async function render(){
    nav(); const c=$('#content'); c.innerHTML='<div class="loader">⏳ Загрузка…</div>';
    try{
      const map={dashboard:dashboard,kanban:kanban,calendar:calendar,queue:queue,support:support,complaints:complaints,analytics:analytics,employees:employees,training:training,goals:goals,settings:settings,monitoring:monitoring,audit:audit};
      await map[state.tab](c);
    }catch(e){c.innerHTML=`<div class="card error">❌ ${esc(e.message)}</div>`}
  }

  async function dashboard(c){
    const s=state.dashboard.stats;
    c.innerHTML=`<div class="hero"><div><div class="eyebrow">PROBLEM NET</div><h1>Центр управления</h1><p>Все процессы проекта в одном месте.</p></div><div class="hero-badge">🟢 ONLINE</div></div>
      <div class="grid">${[['👥',s.users,'Пользователи'],['📚',s.total,'Истории'],['⏳',s.waiting,'Модерация'],['🗓',s.scheduled,'Запланировано'],['🚀',s.publishing,'Публикация'],['✅',s.published,'Опубликовано'],['❌',s.rejected,'Отклонено'],['💬',s.support.open,'Поддержка']].map(x=>`<div class="stat-card"><div class="icon">${x[0]}</div><div class="stat">${x[1]}</div><div class="muted">${x[2]}</div></div>`).join('')}</div>
      <div class="grid two"><div class="card"><h3>🔴 SLA</h3>${state.dashboard.sla_breaches.length?state.dashboard.sla_breaches.map(x=>`<div class="list-row">Диалог #${x.id}<span class="danger-text">${esc(x.priority)}</span></div>`).join(''):'<div class="muted">Нарушений нет</div>'}</div>
      <div class="card"><h3>📌 Быстрые действия</h3><div class="actions"><button class="btn primary" onclick="setTab('kanban')">🛡 Открыть модерацию</button><button class="btn" onclick="setTab('monitoring')">🖥 Состояние системы</button><button class="btn" onclick="setTab('settings')">⚙️ Настройки</button></div></div></div>`;
  }

  async function kanban(c){
    const d=await api('/admin/api/stories'); const groups={waiting:[],scheduled:[],publishing:[],published:[],rejected:[]};
    d.items.forEach(x=>{let k=x.status;if(k==='waiting'&&x.scheduled_at)k='scheduled';if(groups[k])groups[k].push(x)});
    c.innerHTML=`<div class="toolbar"><button class="btn" onclick="selectAll()">☑️ Выбрать всё</button><button class="btn danger" onclick="bulkReject()">❌ Отклонить выбранные</button><button class="btn" onclick="bulkUnschedule()">🗓 Снять расписание</button><button class="btn primary" onclick="autoPlanSelected()">⚡ Автоплан</button></div><div class="kanban">${[['waiting','⏳ Новые'],['publishing','🚀 Публикация'],['scheduled','🗓 Запланированы'],['published','✅ Опубликованы'],['rejected','❌ Отклонены']].map(([k,t])=>`<section class="column"><h3>${t}<span>${groups[k].length}</span></h3>${groups[k].map(storyCard).join('')||'<div class="empty">Пусто</div>'}</section>`).join('')}</div>`;
  }
  function storyCard(x){return `<article class="story" onclick="openStory(${x.id})"><div class="story-top"><input type="checkbox" onclick="event.stopPropagation()" onchange="toggleSelect(${x.id},this.checked)"><b>#${x.id}</b><span class="badge">${esc(x.category||'Без темы')}</span></div><p>${esc((x.text||'').slice(0,220))}</p>${x.scheduled_at?`<small>🗓 ${esc(moscow(x.scheduled_at))} МСК</small>`:''}</article>`}

  window.openStory=async id=>{
    const lock=await post(`/admin/api/story/${id}/lock`).catch(e=>({ok:false,error:e.message}));
    const d=await api('/admin/api/story/'+id); state.story=d.story; state.versions=d.versions||[];
    const s=state.story;
    const locked=lock.locked;
    document.body.insertAdjacentHTML('beforeend',`<div class="modal" id="modal"><div class="sheet"><div class="sheet-head"><div><div class="eyebrow">ИСТОРИЯ</div><h2>#${s.id}</h2></div><button class="icon-btn" onclick="closeStory()">✕</button></div>${locked?`<div class="lock">🔒 Историю сейчас редактирует сотрудник #${esc(lock.admin_id)} до ${esc(moscow(lock.expires_at))}</div>`:''}<label>Исходная история<textarea id="storyText">${esc(s.text)}</textarea></label><label>Готовый пост<textarea id="postText">${esc(s.post_text||'')}</textarea></label><div class="actions">${!locked?`<button class="btn primary" onclick="saveStory(${id})">💾 Сохранить</button>`:''}<button class="btn" onclick="retryAI(${id})">🤖 Анализ ИИ</button><button class="btn" onclick="moderateAI(${id})">🛡 ИИ-проверка</button><button class="btn" onclick="qualityAI(${id})">🔎 Качество</button><button class="btn ok" onclick="publishStory(${id})">🚀 Опубликовать</button><button class="btn danger" onclick="rejectStory(${id})">❌ Отклонить</button><button class="btn" onclick="scheduleStory(${id})">🗓 Назначить время</button><button class="btn" onclick="contactUser(${id})">👤 Пользователю</button></div><h3>🕘 История изменений</h3><div id="versions">${versionsHtml(state.versions)}</div><div class="actions"><button class="btn" onclick="compareLatest()">🔍 Сравнить версии</button></div></div></div>`);
  };
  function versionsHtml(vs){return vs.length?vs.map(v=>`<div class="version"><b>v${v.version_no}</b> · ${esc(v.change_type)} · ${esc(moscow(v.created_at))}<div class="muted">${esc((v.post_text||'').slice(0,180))}</div><button class="btn small" onclick="restoreVersion(${v.id})">↩️ Вернуть</button></div>`).join(''):'<div class="muted">Изменений пока нет.</div>'}
  window.closeStory=()=>{const m=$('#modal');if(m)m.remove()};
  window.saveStory=async id=>{await put('/admin/api/story/'+id,{text:$('#storyText').value,post_text:$('#postText').value});await del('/admin/api/story/'+id+'/lock');closeStory();await render()};
  window.retryAI=async id=>{await post('/admin/api/story/'+id+'/ai');closeStory();await openStory(id)};
  window.moderateAI=async id=>{await post('/admin/api/story/'+id+'/ai-moderate');closeStory();await openStory(id)};
  window.qualityAI=async id=>{await post('/admin/api/story/'+id+'/ai-quality');closeStory();await openStory(id)};
  window.publishStory=async id=>{if(!confirm('Опубликовать историю?'))return;await post('/admin/api/story/'+id+'/publish');closeStory();await render()};
  window.rejectStory=async id=>{const reason=prompt('Причина отклонения:','Требуется дополнительная проверка');if(reason===null)return;await post('/admin/api/story/'+id+'/reject',{reason});closeStory();await render()};
  window.scheduleStory=async id=>{const raw=prompt('Введите дату и время по Москве в формате YYYY-MM-DD HH:MM');if(!raw)return;const [d,t]=raw.split(' ');if(!d||!t)throw new Error('Неверный формат');await post('/admin/api/story/'+id+'/schedule',{scheduled_at:`${d}T${t}:00`});closeStory();await render()};
  window.contactUser=async id=>{await post('/admin/api/story/'+id+'/contact');alert('Сообщение отправлено пользователю.')};
  window.restoreVersion=async id=>{if(!confirm('Вернуть эту версию?'))return;await post('/admin/api/version/'+id+'/restore');closeStory();await render()};
  window.compareLatest=()=>{if(state.versions.length<2){alert('Нужно минимум две версии.');return}const a=state.versions[state.versions.length-2],b=state.versions[state.versions.length-1];alert(`Сравнение v${a.version_no} → v${b.version_no}\n\nБыло:\n${a.post_text||''}\n\nСтало:\n${b.post_text||''}`)};

  window.toggleSelect=(id,on)=>{on?state.selected.add(id):state.selected.delete(id)};
  window.selectAll=()=>{document.querySelectorAll('.story input[type=checkbox]').forEach(x=>{x.checked=true;const id=Number(x.closest('.story').querySelector('b').textContent.slice(1));state.selected.add(id)})};
  window.bulkReject=async()=>{await post('/admin/api/bulk',{ids:[...state.selected],action:'reject'});state.selected.clear();await render()};
  window.bulkUnschedule=async()=>{await post('/admin/api/bulk',{ids:[...state.selected],action:'unschedule'});state.selected.clear();await render()};
  window.autoPlanSelected=async()=>{if(!state.selected.size)return alert('Выберите истории.');await post('/admin/api/content/auto-plan',{ids:[...state.selected]});state.selected.clear();await render()};

  async function calendar(c){const d=await api('/admin/api/reposts');c.innerHTML=`<div class="card"><h2>📅 Планировщик</h2><p>Все даты отображаются по Europe/Moscow.</p>${d.items.map(x=>`<div class="list-row">#${x.story_id}<span>${esc(moscow(x.scheduled_at))}</span></div>`).join('')||'<div class="empty">Публикаций нет</div>'}</div>`}
  async function queue(c){const d=await api('/admin/api/ai-priority');c.innerHTML=`<div class="card"><h2>⚡ Приоритетная очередь опасных историй</h2>${d.items.map(x=>`<div class="list-row"><b>#${x.story_id}</b><span class="danger-text">${esc(x.priority)}</span><span>${esc(x.reason||'')}</span></div>`).join('')||'<div class="empty">Очередь пуста</div>'}</div>`}
  async function support(c){const d=await api('/admin/api/support/metrics');c.innerHTML=`<div class="grid two"><div class="stat-card"><div class="icon">⏱</div><div class="stat">${Math.round((d.metrics?.avg_first_response_seconds||0)/60)} мин</div><div class="muted">Среднее время ответа</div></div><div class="stat-card"><div class="icon">✅</div><div class="stat">${Math.round((d.metrics?.avg_resolution_seconds||0)/60)} мин</div><div class="muted">Среднее время решения</div></div></div><div class="card"><h2>💬 Очередь поддержки</h2>${d.queue.map(x=>`<div class="list-row"><b>#${x.id}</b><span>${esc(x.priority)}</span><span>${esc(x.assignment_status)}</span></div>`).join('')||'<div class="empty">Диалогов нет</div>'}</div>`}
  async function complaints(c){const d=await api('/admin/api/complaints');c.innerHTML=`<div class="card"><h2>⚠️ Жалобы</h2>${d.items.map(x=>`<div class="list-row"><b>История #${x.story_id}</b><span>${esc(x.reason)}</span><span>${esc(x.priority)}</span></div>`).join('')||'<div class="empty">Новых жалоб нет</div>'}</div>`}
  async function analytics(c){const d=await api('/admin/api/analytics');c.innerHTML=`<div class="card"><h2>📈 Аналитика</h2><pre>${esc(JSON.stringify(d,null,2))}</pre></div>`}
  async function employees(c){const d=await api('/admin/api/roles');c.innerHTML=`<div class="card"><h2>👥 Сотрудники</h2>${d.items.map(x=>`<div class="employee"><b>${x.user_id}</b><select onchange="setRole(${x.user_id},this.value)">${['owner','moderator','editor','support','analyst'].map(r=>`<option ${x.role===r?'selected':''}>${r}</option>`).join('')}</select></div>`).join('')}</div>`}
  window.setRole=async(id,role)=>{await put('/admin/api/role/'+id,{role});await load()};
  async function training(c){const d=await api('/admin/api/training');c.innerHTML=`<div class="card"><h2>🎓 Обучение и стажировка</h2>${d.items.map(x=>`<div class="list-row"><b>${x.admin_id}</b><span>${esc(x.course)} / ${esc(x.lesson)}</span><span>${esc(x.status)} ${x.score??''}</span></div>`).join('')||'<div class="empty">Курсы не назначены</div>'}</div>`}
  async function goals(c){const d=await api('/admin/api/goals');c.innerHTML=`<div class="card"><h2>🎯 Цели и рейтинг</h2>${d.performance.map(x=>`<div class="list-row"><b>${x.admin_id}</b><span>Публикации: ${x.published}</span><span>Модерация: ${x.moderated}</span><span>Действия: ${x.actions}</span></div>`).join('')||'<div class="empty">Данных пока нет</div>'}</div>`}
  async function settings(c){const d=await api('/admin/api/settings');state.settings=d;c.innerHTML=`<div class="card"><h2>⚙️ Единый центр настроек</h2>${d.settings.map(x=>`<label>${esc(x.key)}<input data-setting="${esc(x.key)}" value="${esc(x.value)}"></label>`).join('')}<h3>AI-проверки</h3>${d.ai_checks.map(x=>`<label class="switch"><input type="checkbox" data-ai="${esc(x.key)}" ${x.enabled?'checked':''}> ${esc(x.key)}</label>`).join('')}<button class="btn primary" onclick="saveSettings()">💾 Сохранить</button></div>`}
  window.saveSettings=async()=>{const settings={};document.querySelectorAll('[data-setting]').forEach(x=>settings[x.dataset.setting]=x.value);const ai_checks={};document.querySelectorAll('[data-ai]').forEach(x=>ai_checks[x.dataset.ai]=x.checked);await put('/admin/api/settings',{settings,ai_checks});alert('Настройки сохранены');await render()};
  async function monitoring(c){const d=await api('/admin/api/monitoring');c.innerHTML=`<div class="grid">${d.health.map(x=>`<div class="stat-card"><div class="icon">${x.status==='ok'?'🟢':'🔴'}</div><div class="stat">${esc(x.service)}</div><div class="muted">${esc(x.details||'')}</div></div>`).join('')}</div><div class="card"><h2>🧪 Целостность базы</h2><div class="${d.integrity.ok?'ok-text':'danger-text'}">${d.integrity.ok?'🟢 База в порядке':'🔴 Обнаружены ошибки'}</div><pre>${esc(JSON.stringify(d.integrity,null,2))}</pre></div><div class="card"><h2>🧯 Технические ошибки</h2>${d.errors.map(x=>`<div class="error-row"><b>${esc(x.service)}</b> · ${esc(x.created_at)}<br>${esc(x.message)}</div>`).join('')||'<div class="empty">Ошибок нет</div>'}</div>`}
  async function audit(c){const d=await api('/admin/api/audit');c.innerHTML=`<div class="card"><h2>📜 Аудит</h2>${d.items.map(x=>`<div class="list-row"><span>${esc(x.created_at)}</span><b>${esc(x.admin_id)}</b><span>${esc(x.action)}</span></div>`).join('')}</div>`}

  load().catch(e=>{$('#content').innerHTML=`<div class="fatal">❌ ${esc(e.message)}</div>`});
})();
