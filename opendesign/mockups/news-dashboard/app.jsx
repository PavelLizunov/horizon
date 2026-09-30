const {useState, useEffect, useRef, useMemo} = React;
const KEY = 'horizon-dashboard-prototype-v1';
const TODAY = new Date('2026-09-30T12:00:00Z');
const TOPICS = ['Все темы', 'Локальные модели', 'Агенты', 'Инфраструктура', 'Сети', 'Исследования'];
const STORIES = [
  {id:'local-context', topic:'Локальные модели', title:'Больше контекста. Меньше видеопамяти.', deck:'Что меняется, когда длинный контекст становится доступен на домашнем GPU — и где остаются ограничения.', date:'2026-09-30', score:9.4, minutes:8, source:'Технический разбор', art:'chip', audio:true},
  {id:'agent-handoff', topic:'Агенты', title:'Агенту нужна память, а не ещё один промпт', deck:'Передача задач, журнал решений и контекст, который переживает новую сессию.', date:'2026-09-30', score:9.1, minutes:6, source:'Практика разработки', art:'orbit', audio:true},
  {id:'home-server', topic:'Инфраструктура', title:'Домашний сервер без лишнего шума', deck:'Как собрать сервисы так, чтобы они не требовали ежедневного внимания.', date:'2026-09-29', score:8.8, minutes:5, source:'Опыт эксплуатации', art:'server', audio:false},
  {id:'network-routing', topic:'Сети', title:'Маршрут важнее протокола', deck:'Почему устойчивость соединения начинается с диагностики сети.', date:'2026-09-29', score:8.6, minutes:7, source:'Полевые заметки', art:'network', audio:true},
  {id:'reasoning-tradeoff', topic:'Исследования', title:'Когда длинное рассуждение не помогает', deck:'Где дополнительное время на ответ перестаёт давать точность.', date:'2026-09-28', score:8.9, minutes:9, source:'Исследовательский обзор', art:'wave', audio:false},
  {id:'agent-tests', topic:'Агенты', title:'Как проверить код, написанный агентом', deck:'Тесты, воспроизводимые изменения и граница между «собралось» и «работает».', date:'2026-09-27', score:8.7, minutes:6, source:'Практика разработки', art:'orbit', audio:true},
  {id:'backup-first', topic:'Инфраструктура', title:'Бэкап, который действительно восстанавливается', deck:'Проверка восстановления важнее зелёного статуса задания.', date:'2026-09-25', score:9.0, minutes:5, source:'Опыт эксплуатации', art:'server', audio:true},
  {id:'local-voice', topic:'Локальные модели', title:'Локальная озвучка: качество между фрагментами', deck:'Независимая проверка звука и публикация, которая не ждёт весь выпуск.', date:'2026-09-23', score:8.3, minutes:7, source:'Технический разбор', art:'wave', audio:false},
  {id:'dns-notes', topic:'Сети', title:'DNS — маленькая настройка с большим влиянием', deck:'Что проверять, когда один сервис доступен, а соседний — нет.', date:'2026-09-19', score:8.1, minutes:4, source:'Полевые заметки', art:'network', audio:true},
  {id:'quant-guide', topic:'Локальные модели', title:'Квантизация без магических обещаний', deck:'Как выбрать компромисс по памяти и проверить его на собственных задачах.', date:'2026-09-15', score:9.2, minutes:10, source:'Технический разбор', art:'chip', audio:true},
  {id:'research-evidence', topic:'Исследования', title:'От красивого графика к воспроизводимому результату', deck:'На какие детали смотреть, когда очередной бенчмарк обещает прорыв.', date:'2026-09-10', score:8.5, minutes:8, source:'Исследовательский обзор', art:'wave', audio:false},
  {id:'agent-checkpoints', topic:'Агенты', title:'Чекпоинты для длинных задач', deck:'Небольшие законченные шаги вместо одной сессии на всю ночь.', date:'2026-09-03', score:8.4, minutes:5, source:'Практика разработки', art:'orbit', audio:true},
  {id:'network-old', topic:'Сети', title:'Свой туннель: что стоит записать до первого сбоя', deck:'Схема маршрутов, зависимости и короткий план восстановления.', date:'2026-08-21', score:9.3, minutes:7, source:'Полевые заметки', art:'network', audio:false},
  {id:'server-old', topic:'Инфраструктура', title:'Маленький сервер, большие ожидания', deck:'Ресурсы, лимиты и простой способ не переоценить своё железо.', date:'2026-07-12', score:8.2, minutes:6, source:'Опыт эксплуатации', art:'server', audio:true},
];
const HERO_IDS = STORIES.slice(0,5).map(s => s.id);
function readPrefs() {
  try { const x = JSON.parse(localStorage.getItem(KEY) || '{}'); return x && typeof x === 'object' ? x : {}; }
  catch { return {}; }
}
function validIds(x) { return Array.isArray(x) ? x.filter(id => STORIES.some(s => s.id === id)).slice(0,30) : []; }
function prettyDate(s) { return new Date(s+'T12:00:00Z').toLocaleDateString('ru-RU',{day:'numeric', month:'short'}).replace('.', ''); }
function coverName(kind) { return {chip:'Архитектура вычислений',orbit:'Орбиты задач',server:'Серверная архитектура',network:'Маршруты соединений',wave:'Волны рассуждений'}[kind]; }
function Cover({kind, className=''}) {
  const palette = {chip:['#152830','#55bcae','#cfeaa7'], orbit:['#263770','#a8b7f4','#f4b8a6'], server:['#573b2f','#dfa27b','#f6dcb4'], network:['#243c34','#a6c795','#d5e6ad'], wave:['#323046','#b5a8d1','#eed4b7']}[kind];
  const [bg,a,b] = palette;
  return <div className={'cover '+className} role="img" aria-label={coverName(kind)+' — демонстрационная иллюстрация'}>
    <svg viewBox="0 0 640 420" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <rect width="640" height="420" fill={bg}/>
      <g stroke={a} strokeWidth="1" opacity=".14">{Array.from({length:17},(_,i)=><path key={i} d={`M${i*40} 0V420 M0 ${i*30}H640`}/>)}</g>
      {kind==='chip' && <g>
        <g stroke={a} fill="none" strokeWidth="2" opacity=".7">{Array.from({length:9},(_,i)=><path key={i} d={`M${126+i*34} 0V${58+i%3*12}L${260+i*8} ${122+i%3*8} M${155+i*39} 420V${365-i%3*10}L${240+i*17} 289`}/>)}</g>
        <path d="M173 192 320 105 470 192 320 280Z" fill="#385652" stroke={a} strokeWidth="2"/>
        <path d="M173 192V225L320 313 470 225V192L320 280Z" fill="#162d2c" stroke={a} strokeWidth="2"/>
        <path d="M205 187 320 121 435 187 320 253Z" fill="#1d3c36" stroke={b} strokeWidth="2"/>
        <path d="M263 187 320 154 379 187 320 221Z" fill={b}/>
        <g stroke={b} opacity=".8" strokeWidth="3">{Array.from({length:9},(_,i)=><path key={i} d={`M${189+i*13} ${218+i*7.6}v16 M${456-i*13} ${218+i*7.6}v16`}/>)}</g>
        <circle cx="128" cy="311" r="5" fill={b}/><circle cx="504" cy="112" r="5" fill={a}/>
      </g>}
      {kind==='orbit' && <g transform="translate(320 210)">
        {[0,60,120].map(v=><ellipse key={v} rx="168" ry="66" transform={`rotate(${v})`} fill="none" stroke={a} strokeWidth="2"/>)}
        <circle r="30" fill={b}/><circle cx="-160" cy="-19" r="15" fill={a}/><circle cx="108" cy="-115" r="12" fill={b}/><circle cx="68" cy="147" r="17" fill={a}/>
        <path d="M-230 0H-192 M192 0H230 M0-190V-170 M0 170V190" stroke={a} strokeWidth="2"/>
        <circle r="199" fill="none" stroke={a} opacity=".2" strokeDasharray="4 8"/>
      </g>}
      {kind==='server' && <g transform="translate(0 15)">
        {[0,1,2,3].map(i=><g key={i} transform={`translate(0 ${i*53})`}>
          <path d="M200 130 328 60 455 130 328 202Z" fill="#86604b" stroke={b} strokeWidth="1.5"/>
          <path d="M200 130v34l128 72v-34Z" fill="#453329" stroke={a} strokeWidth="1.5"/>
          <path d="M455 130v34l-127 72v-34Z" fill="#63402e" stroke={a} strokeWidth="1.5"/>
          <g stroke={b} opacity=".7">{[0,1,2,3,4].map(j=><path key={j} d={`M${223+j*16} ${145+j*9}v13`}/>)}</g><circle cx="416" cy="166" r="3" fill="#e8bd71"/>
        </g>)}
      </g>}
      {kind==='network' && <g stroke={a} strokeWidth="2" fill="none">
        <path d="M85 325 215 195 340 268 488 97 M82 96 215 195 314 85 488 97 554 283 340 268 412 368"/>
        <path d="M85 325 340 268 314 85 M215 195 554 283" strokeDasharray="5 6" opacity=".4"/>
        {[[85,325],[215,195],[340,268],[488,97],[82,96],[314,85],[554,283],[412,368]].map(([x,y],i)=><g key={i}><circle cx={x} cy={y} r={i===1?34:15} fill={bg}/><circle cx={x} cy={y} r={i===1?22:6} fill={i===1?b:a} stroke="none"/></g>)}
        <circle cx="215" cy="195" r="63" opacity=".25"/><circle cx="340" cy="268" r="40" opacity=".25"/>
      </g>}
      {kind==='wave' && <g fill="none" strokeWidth="2">
        {Array.from({length:16},(_,i)=><path key={i} d={`M-30 ${85+i*17} C110 ${220+i*11},155 ${-120+i*30},315 ${100+i*12} S485 ${460-i*12},675 ${125+i*17}`} stroke={i%4===0?b:a} opacity={.45+i*.03}/>)}
        <circle cx="324" cy="210" r="62" stroke={b} opacity=".3"/>
      </g>}
      <g fill={b} opacity=".5"><circle cx="36" cy="36" r="2"/><circle cx="604" cy="384" r="2"/></g>
    </svg>
    <span className="cover-caption">ИЛЛЮСТРАЦИЯ</span>
  </div>;
}
function Bookmark({saved, onClick, title, small=false}) {
  return <button type="button" className={'bookmark '+(saved?'is-saved ':'')+(small?'small':'')} aria-label={(saved?'Убрать из отложенного: ':'Отложить: ')+title} aria-pressed={saved} onClick={onClick}><span aria-hidden="true">{saved?'✓':'+'}</span></button>;
}
function ArticleDialog({story, saved, onSave, onClose}) {
  const dialog = useRef(null);
  useEffect(()=>{
    const previous = document.activeElement;
    dialog.current.showModal();
    return ()=>{ if(dialog.current?.open) dialog.current.close(); previous?.focus(); };
  },[]);
  return <dialog ref={dialog} className="article-dialog" onCancel={onClose} onClick={e=>{if(e.target===e.currentTarget) onClose();}} aria-labelledby="article-title">
    <button className="dialog-close" aria-label="Закрыть статью" onClick={onClose}>×</button>
    <Cover kind={story.art}/>
    <div className="article-body">
      <div className="article-meta"><span>{story.topic}</span><span>{prettyDate(story.date)} · {story.minutes} мин</span></div>
      <h1 id="article-title">{story.title}</h1><p className="article-deck">{story.deck}</p>
      <div className="article-actions"><button className={'button '+(saved?'button-saved':'')} onClick={onSave}>{saved?'✓ В отложенном':'+ Отложить на потом'}</button><span className="score">{story.score.toFixed(1)}<span> / 10</span></span></div>
      <p className="demo-note">Демонстрационный материал. Заголовок, рейтинг и текст приведены для проверки интерфейса, а не как опубликованная новость.</p>
      <h2>Что здесь важно</h2>
      <p>При возвращении к материалу важнее помнить его тему, чем день публикации. Эта карточка показывает, как будет выглядеть чтение из общей ленты: краткий контекст, заметная тема и возможность сохранить статью.</p>
      <p>{story.deck} В рабочем варианте здесь будет настоящий разбор из архива с исходными ссылками и доступной проверкой утверждений.</p>
      <blockquote>Хорошая главная помогает выбрать, что читать. История и отложенное помогают к этому вернуться.</blockquote>
      <h2>Озвучка</h2><p>{story.audio?'В демонстрационных данных у этой статьи отмечена озвучка. Аудиофайл в макет не включён — кнопки с ложным воспроизведением здесь нет.':'У этой демонстрационной статьи озвучка пока не готова. Текст остаётся доступен.'}</p>
      <button className="text-button" onClick={onClose}>← Вернуться к подборке</button>
    </div>
  </dialog>;
}
function App() {
  const [initial] = useState(readPrefs);
  const [theme,setTheme] = useState(initial.theme==='dark'?'dark':'light');
  const [saved,setSaved] = useState(validIds(initial.saved));
  const [recent,setRecent] = useState(validIds(initial.recent));
  const [view,setView] = useState(['news','saved','recent'].includes(initial.view)?initial.view:'news');
  const [topic,setTopic] = useState(TOPICS.includes(initial.topic)?initial.topic:'Все темы');
  const [period,setPeriod] = useState(['all','7','30'].includes(initial.period)?initial.period:'all');
  const [sort,setSort] = useState(initial.sort==='score'?'score':'newest');
  const [query,setQuery] = useState('');
  const [selected,setSelected] = useState(null);
  const [status,setStatus] = useState('loading');
  const [toast,setToast] = useState('');
  const timer = useRef(null);
  useEffect(()=>{const t=setTimeout(()=>setStatus('ready'),450);return()=>clearTimeout(t);},[]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem(KEY,JSON.stringify({theme,saved,recent,view,topic,period,sort}));}catch{}},[theme,saved,recent,view,topic,period,sort]);
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  function notify(message){setToast(message);clearTimeout(timer.current);timer.current=setTimeout(()=>setToast(''),2500);}
  function toggleSaved(s){const exists=saved.includes(s.id);setSaved(x=>exists?x.filter(id=>id!==s.id):[s.id,...x]);notify(exists?'Убрано из отложенного':'Сохранено на потом');}
  function openStory(s){setSelected(s);setRecent(x=>[s.id,...x.filter(id=>id!==s.id)].slice(0,30));}
  function switchView(v){setView(v);setQuery('');setTopic('Все темы');setPeriod('all');setStatus('ready');}
  function reset(){setQuery('');setTopic('Все темы');setPeriod('all');setSort('newest');setStatus('ready');}
  const filtered = useMemo(()=>{
    let result=STORIES.filter(s=>view==='news'||(view==='saved'?saved:recent).includes(s.id));
    const q=query.trim().toLocaleLowerCase('ru-RU');
    result=result.filter(s=>(topic==='Все темы'||s.topic===topic)&&(!q||[s.title,s.deck,s.topic,s.source].join(' ').toLocaleLowerCase('ru-RU').includes(q))&&(period==='all'||(TODAY-new Date(s.date+'T12:00:00Z'))/86400000<Number(period)));
    return result.sort((a,b)=>view==='recent'?recent.indexOf(a.id)-recent.indexOf(b.id):sort==='score'?b.score-a.score:b.date.localeCompare(a.date)||b.score-a.score);
  },[view,saved,recent,topic,period,query,sort]);
  const showHero = view==='news' && !query.trim() && topic==='Все темы' && period==='all' && sort==='newest' && status==='ready';
  const feed=showHero?filtered.filter(s=>!HERO_IDS.includes(s.id)):filtered;
  const title=view==='saved'?'Отложенное':view==='recent'?'Недавно открывали':'Ваш новостной горизонт';
  const deck=view==='saved'?'То, к чему хочется вернуться. Сохранено в этом браузере.':view==='recent'?'Ваш путь по материалам — без необходимости вспоминать дату.':'Важное из ваших источников. И всё, что стоит перечитать.';
  function renderCard(s, lead=false){return <article key={s.id} className={'story '+(lead?'lead':'')} data-story-id={s.id} data-score={s.score}>
    <Cover kind={s.art}/><div className="story-body"><div className="story-topline"><span>{s.topic}</span><span className="story-score">{s.score.toFixed(1)}<small> / 10</small></span></div>
      <h3><button className="story-open" onClick={()=>openStory(s)}>{s.title}</button></h3><p>{s.deck}</p>
      <div className="story-bottom"><span>{prettyDate(s.date)}<span className="dot">·</span>{s.minutes} мин{s.audio&&<span className="audio-label" title="Озвучка отмечена в демоданных"> · Аудио</span>}</span><Bookmark saved={saved.includes(s.id)} onClick={()=>toggleSaved(s)} title={s.title}/></div>
    </div></article>;}
  return <>
    <div className="demo-ribbon"><span>ПРОТОТИП</span> Демонстрационные статьи и обложки · рабочий сайт не изменён</div>
    <header className="site-header"><div className="header-inner"><a className="brand" href="./" onClick={e=>{e.preventDefault();switchView('news');}}><img src="penguin.png" width="39" height="39" alt=""/><span>Digest <strong>Ninitux</strong></span></a>
      <nav aria-label="Разделы"><button className={view==='news'?'active':''} onClick={()=>switchView('news')}>Главная</button><button className={view==='saved'?'active':''} onClick={()=>switchView('saved')}>Отложенное <span className="nav-count">{saved.length}</span></button><button className={view==='recent'?'active':''} onClick={()=>switchView('recent')}>История</button></nav>
      <button className="theme-toggle" onClick={()=>setTheme(t=>t==='light'?'dark':'light')} aria-label={theme==='light'?'Включить тёмную тему':'Включить светлую тему'}><span aria-hidden="true">{theme==='light'?'◐':'◑'}</span></button>
    </div></header>
    <main>
      <div className="intro"><div><p className="eyebrow">ЛИЧНАЯ ЛЕНТА / ДЕМО 30 СЕНТЯБРЯ</p><h1>{title}</h1><p className="intro-deck">{deck}</p></div><div className="edition"><span>ОТБОР ПО ИНТЕРЕСАМ</span><b>Свежие материалы.<br/>Архив без календаря.</b></div></div>
      <section className="controls" aria-label="Настройки ленты"><div className="search-wrap"><span aria-hidden="true">⌕</span><input aria-label="Найти материал" type="search" placeholder="Найти статью, тему или источник" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button className="clear-search" aria-label="Очистить поиск" onClick={()=>setQuery('')}>×</button>}</div>
        <label className="period">Период<select aria-label="Период публикации" value={period} onChange={e=>setPeriod(e.target.value)}><option value="all">Всё время</option><option value="7">Последние 7 дней</option><option value="30">Последние 30 дней</option></select></label>
        <div className="sort-toggle" role="group" aria-label="Порядок материалов"><button aria-pressed={sort==='newest'} onClick={()=>setSort('newest')}>Свежие</button><button aria-pressed={sort==='score'} onClick={()=>setSort('score')}>По рейтингу</button></div>
      </section>
      <div className="topics" role="group" aria-label="Темы">{TOPICS.map(t=><button key={t} aria-pressed={topic===t} onClick={()=>setTopic(t)}>{t}</button>)}</div>
      {status==='loading'?<section className="loading-panel" role="status"><span className="loading-dot"/>Собираем демонстрационную ленту…<div className="skeleton-grid">{[1,2,3].map(i=><div key={i}/>)}</div></section>:status==='error'?<section className="empty-panel" role="alert"><span className="empty-symbol">!</span><h2>Лента временно недоступна</h2><p>Это демонстрация ошибки загрузки. Статьи и ваши закладки не потеряны.</p><button className="button" onClick={()=>{setStatus('loading');setTimeout(()=>setStatus('ready'),450);}}>Попробовать снова</button></section>:<>
        {showHero&&<section className="hero-section" aria-labelledby="hero-title"><div className="section-heading"><h2 id="hero-title">В фокусе</h2><span>5 материалов · разные темы</span></div><div className="hero-grid">{STORIES.slice(0,5).map((s,i)=>renderCard(s,i===0))}</div></section>}
        <section className="archive-section" aria-labelledby="feed-title"><div className="section-heading"><h2 id="feed-title">{view==='news'?(showHero?'Ещё в ленте':'Материалы архива'):title}</h2><span>{feed.length} {feed.length===1?'материал':feed.length>1&&feed.length<5?'материала':'материалов'}</span></div>
          {feed.length===0?<div className="empty-panel"><span className="empty-symbol">↗</span><h2>{view==='saved'&&saved.length===0?'Здесь будут ваши находки':view==='recent'&&recent.length===0?'Ваша история начинается с первой статьи':'Ничего не нашлось'}</h2><p>{view==='saved'&&saved.length===0?'Нажмите «+» на карточке — и материал останется под рукой.':view==='recent'&&recent.length===0?'Откройте любой материал на главной. Мы запомним его в этом браузере.':'Попробуйте другую тему или снимите ограничения периода.'}</p><button className="button" onClick={()=>{if(view!=='news'&&(view==='saved'?saved:recent).length===0)switchView('news');else reset();}}>{view!=='news'&&(view==='saved'?saved:recent).length===0?'К подборке':'Сбросить фильтры'}</button></div>:<div className="feed-layout"><div className="feed-grid">{feed.map(s=>renderCard(s))}</div><aside className="reading-sidebar"><div className="side-label">ПОД РУКОЙ</div><h2>Вернуться<br/>к прочитанному</h2>{recent.length>0?<ul>{recent.slice(0,3).map(id=>{const s=STORIES.find(x=>x.id===id);return <li key={id}><span>{s.topic}</span><button onClick={()=>openStory(s)}>{s.title}<span aria-hidden="true"> ↗</span></button></li>;})}</ul>:<p>Открытые материалы появятся здесь. Не нужно запоминать выпуск или дату.</p>}<button className="text-button" onClick={()=>switchView(recent.length?'recent':'saved')}>{recent.length?'Вся история →':'Открыть отложенное →'}</button><div className="side-divider"/><span className="side-label">О РЕЙТИНГЕ</span><p>Оценка интереса — не проверка истинности. В этом макете все оценки демонстрационные.</p></aside></div>}
        </section>
      </>}
      <footer className="footer"><div><b>Digest Ninitux</b><p>Сохранённое и история остаются в этом браузере.</p></div><details className="demo-controls"><summary>Проверить состояния макета</summary><div><button onClick={()=>setStatus('loading')}>Загрузка</button><button onClick={()=>setStatus('error')}>Ошибка</button><button onClick={()=>{setQuery('нет-совпадений-000');setStatus('ready');}}>Пустая выдача</button><button onClick={reset}>Вернуть ленту</button></div></details></footer>
    </main>
    <div className={'toast '+(toast?'visible':'')} role="status" aria-live="polite">{toast}</div>
    {selected&&<ArticleDialog story={selected} saved={saved.includes(selected.id)} onSave={()=>toggleSaved(selected)} onClose={()=>setSelected(null)}/>}
  </>;
}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
