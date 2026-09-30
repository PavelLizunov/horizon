const {
  useState,
  useEffect,
  useRef,
  useMemo
} = React;
const KEY = 'horizon-dashboard-prototype-v1';
const TODAY = new Date('2026-09-30T12:00:00Z');
const TOPICS = ['Все темы', 'Локальные модели', 'Агенты', 'Инфраструктура', 'Сети', 'Исследования'];
const STORIES = [{
  id: 'local-context',
  topic: 'Локальные модели',
  title: 'Больше контекста. Меньше видеопамяти.',
  deck: 'Что меняется, когда длинный контекст становится доступен на домашнем GPU — и где остаются ограничения.',
  date: '2026-09-30',
  score: 9.4,
  minutes: 8,
  source: 'Технический разбор',
  art: 'chip',
  audio: true
}, {
  id: 'agent-handoff',
  topic: 'Агенты',
  title: 'Агенту нужна память, а не ещё один промпт',
  deck: 'Передача задач, журнал решений и контекст, который переживает новую сессию.',
  date: '2026-09-30',
  score: 9.1,
  minutes: 6,
  source: 'Практика разработки',
  art: 'orbit',
  audio: true
}, {
  id: 'home-server',
  topic: 'Инфраструктура',
  title: 'Домашний сервер без лишнего шума',
  deck: 'Как собрать сервисы так, чтобы они не требовали ежедневного внимания.',
  date: '2026-09-29',
  score: 8.8,
  minutes: 5,
  source: 'Опыт эксплуатации',
  art: 'server',
  audio: false
}, {
  id: 'network-routing',
  topic: 'Сети',
  title: 'Маршрут важнее протокола',
  deck: 'Почему устойчивость соединения начинается с диагностики сети.',
  date: '2026-09-29',
  score: 8.6,
  minutes: 7,
  source: 'Полевые заметки',
  art: 'network',
  audio: true
}, {
  id: 'reasoning-tradeoff',
  topic: 'Исследования',
  title: 'Когда длинное рассуждение не помогает',
  deck: 'Где дополнительное время на ответ перестаёт давать точность.',
  date: '2026-09-28',
  score: 8.9,
  minutes: 9,
  source: 'Исследовательский обзор',
  art: 'wave',
  audio: false
}, {
  id: 'agent-tests',
  topic: 'Агенты',
  title: 'Как проверить код, написанный агентом',
  deck: 'Тесты, воспроизводимые изменения и граница между «собралось» и «работает».',
  date: '2026-09-27',
  score: 8.7,
  minutes: 6,
  source: 'Практика разработки',
  art: 'orbit',
  audio: true
}, {
  id: 'backup-first',
  topic: 'Инфраструктура',
  title: 'Бэкап, который действительно восстанавливается',
  deck: 'Проверка восстановления важнее зелёного статуса задания.',
  date: '2026-09-25',
  score: 9.0,
  minutes: 5,
  source: 'Опыт эксплуатации',
  art: 'server',
  audio: true
}, {
  id: 'local-voice',
  topic: 'Локальные модели',
  title: 'Локальная озвучка: качество между фрагментами',
  deck: 'Независимая проверка звука и публикация, которая не ждёт весь выпуск.',
  date: '2026-09-23',
  score: 8.3,
  minutes: 7,
  source: 'Технический разбор',
  art: 'wave',
  audio: false
}, {
  id: 'dns-notes',
  topic: 'Сети',
  title: 'DNS — маленькая настройка с большим влиянием',
  deck: 'Что проверять, когда один сервис доступен, а соседний — нет.',
  date: '2026-09-19',
  score: 8.1,
  minutes: 4,
  source: 'Полевые заметки',
  art: 'network',
  audio: true
}, {
  id: 'quant-guide',
  topic: 'Локальные модели',
  title: 'Квантизация без магических обещаний',
  deck: 'Как выбрать компромисс по памяти и проверить его на собственных задачах.',
  date: '2026-09-15',
  score: 9.2,
  minutes: 10,
  source: 'Технический разбор',
  art: 'chip',
  audio: true
}, {
  id: 'research-evidence',
  topic: 'Исследования',
  title: 'От красивого графика к воспроизводимому результату',
  deck: 'На какие детали смотреть, когда очередной бенчмарк обещает прорыв.',
  date: '2026-09-10',
  score: 8.5,
  minutes: 8,
  source: 'Исследовательский обзор',
  art: 'wave',
  audio: false
}, {
  id: 'agent-checkpoints',
  topic: 'Агенты',
  title: 'Чекпоинты для длинных задач',
  deck: 'Небольшие законченные шаги вместо одной сессии на всю ночь.',
  date: '2026-09-03',
  score: 8.4,
  minutes: 5,
  source: 'Практика разработки',
  art: 'orbit',
  audio: true
}, {
  id: 'network-old',
  topic: 'Сети',
  title: 'Свой туннель: что стоит записать до первого сбоя',
  deck: 'Схема маршрутов, зависимости и короткий план восстановления.',
  date: '2026-08-21',
  score: 9.3,
  minutes: 7,
  source: 'Полевые заметки',
  art: 'network',
  audio: false
}, {
  id: 'server-old',
  topic: 'Инфраструктура',
  title: 'Маленький сервер, большие ожидания',
  deck: 'Ресурсы, лимиты и простой способ не переоценить своё железо.',
  date: '2026-07-12',
  score: 8.2,
  minutes: 6,
  source: 'Опыт эксплуатации',
  art: 'server',
  audio: true
}];
const HERO_IDS = STORIES.slice(0, 5).map(s => s.id);
function readPrefs() {
  try {
    const x = JSON.parse(localStorage.getItem(KEY) || '{}');
    return x && typeof x === 'object' ? x : {};
  } catch {
    return {};
  }
}
function validIds(x) {
  return Array.isArray(x) ? x.filter(id => STORIES.some(s => s.id === id)).slice(0, 30) : [];
}
function prettyDate(s) {
  return new Date(s + 'T12:00:00Z').toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short'
  }).replace('.', '');
}
function coverName(kind) {
  return {
    chip: 'Архитектура вычислений',
    orbit: 'Орбиты задач',
    server: 'Серверная архитектура',
    network: 'Маршруты соединений',
    wave: 'Волны рассуждений'
  }[kind];
}
function Cover({
  kind,
  className = ''
}) {
  const palette = {
    chip: ['#152830', '#55bcae', '#cfeaa7'],
    orbit: ['#263770', '#a8b7f4', '#f4b8a6'],
    server: ['#573b2f', '#dfa27b', '#f6dcb4'],
    network: ['#243c34', '#a6c795', '#d5e6ad'],
    wave: ['#323046', '#b5a8d1', '#eed4b7']
  }[kind];
  const [bg, a, b] = palette;
  return React.createElement("div", {
    className: 'cover ' + className,
    role: "img",
    "aria-label": coverName(kind) + ' — демонстрационная иллюстрация'
  }, React.createElement("svg", {
    viewBox: "0 0 640 420",
    "aria-hidden": "true",
    preserveAspectRatio: "xMidYMid slice"
  }, React.createElement("rect", {
    width: "640",
    height: "420",
    fill: bg
  }), React.createElement("g", {
    stroke: a,
    strokeWidth: "1",
    opacity: ".14"
  }, Array.from({
    length: 17
  }, (_, i) => React.createElement("path", {
    key: i,
    d: `M${i * 40} 0V420 M0 ${i * 30}H640`
  }))), kind === 'chip' && React.createElement("g", null, React.createElement("g", {
    stroke: a,
    fill: "none",
    strokeWidth: "2",
    opacity: ".7"
  }, Array.from({
    length: 9
  }, (_, i) => React.createElement("path", {
    key: i,
    d: `M${126 + i * 34} 0V${58 + i % 3 * 12}L${260 + i * 8} ${122 + i % 3 * 8} M${155 + i * 39} 420V${365 - i % 3 * 10}L${240 + i * 17} 289`
  }))), React.createElement("path", {
    d: "M173 192 320 105 470 192 320 280Z",
    fill: "#385652",
    stroke: a,
    strokeWidth: "2"
  }), React.createElement("path", {
    d: "M173 192V225L320 313 470 225V192L320 280Z",
    fill: "#162d2c",
    stroke: a,
    strokeWidth: "2"
  }), React.createElement("path", {
    d: "M205 187 320 121 435 187 320 253Z",
    fill: "#1d3c36",
    stroke: b,
    strokeWidth: "2"
  }), React.createElement("path", {
    d: "M263 187 320 154 379 187 320 221Z",
    fill: b
  }), React.createElement("g", {
    stroke: b,
    opacity: ".8",
    strokeWidth: "3"
  }, Array.from({
    length: 9
  }, (_, i) => React.createElement("path", {
    key: i,
    d: `M${189 + i * 13} ${218 + i * 7.6}v16 M${456 - i * 13} ${218 + i * 7.6}v16`
  }))), React.createElement("circle", {
    cx: "128",
    cy: "311",
    r: "5",
    fill: b
  }), React.createElement("circle", {
    cx: "504",
    cy: "112",
    r: "5",
    fill: a
  })), kind === 'orbit' && React.createElement("g", {
    transform: "translate(320 210)"
  }, [0, 60, 120].map(v => React.createElement("ellipse", {
    key: v,
    rx: "168",
    ry: "66",
    transform: `rotate(${v})`,
    fill: "none",
    stroke: a,
    strokeWidth: "2"
  })), React.createElement("circle", {
    r: "30",
    fill: b
  }), React.createElement("circle", {
    cx: "-160",
    cy: "-19",
    r: "15",
    fill: a
  }), React.createElement("circle", {
    cx: "108",
    cy: "-115",
    r: "12",
    fill: b
  }), React.createElement("circle", {
    cx: "68",
    cy: "147",
    r: "17",
    fill: a
  }), React.createElement("path", {
    d: "M-230 0H-192 M192 0H230 M0-190V-170 M0 170V190",
    stroke: a,
    strokeWidth: "2"
  }), React.createElement("circle", {
    r: "199",
    fill: "none",
    stroke: a,
    opacity: ".2",
    strokeDasharray: "4 8"
  })), kind === 'server' && React.createElement("g", {
    transform: "translate(0 15)"
  }, [0, 1, 2, 3].map(i => React.createElement("g", {
    key: i,
    transform: `translate(0 ${i * 53})`
  }, React.createElement("path", {
    d: "M200 130 328 60 455 130 328 202Z",
    fill: "#86604b",
    stroke: b,
    strokeWidth: "1.5"
  }), React.createElement("path", {
    d: "M200 130v34l128 72v-34Z",
    fill: "#453329",
    stroke: a,
    strokeWidth: "1.5"
  }), React.createElement("path", {
    d: "M455 130v34l-127 72v-34Z",
    fill: "#63402e",
    stroke: a,
    strokeWidth: "1.5"
  }), React.createElement("g", {
    stroke: b,
    opacity: ".7"
  }, [0, 1, 2, 3, 4].map(j => React.createElement("path", {
    key: j,
    d: `M${223 + j * 16} ${145 + j * 9}v13`
  }))), React.createElement("circle", {
    cx: "416",
    cy: "166",
    r: "3",
    fill: "#e8bd71"
  })))), kind === 'network' && React.createElement("g", {
    stroke: a,
    strokeWidth: "2",
    fill: "none"
  }, React.createElement("path", {
    d: "M85 325 215 195 340 268 488 97 M82 96 215 195 314 85 488 97 554 283 340 268 412 368"
  }), React.createElement("path", {
    d: "M85 325 340 268 314 85 M215 195 554 283",
    strokeDasharray: "5 6",
    opacity: ".4"
  }), [[85, 325], [215, 195], [340, 268], [488, 97], [82, 96], [314, 85], [554, 283], [412, 368]].map(([x, y], i) => React.createElement("g", {
    key: i
  }, React.createElement("circle", {
    cx: x,
    cy: y,
    r: i === 1 ? 34 : 15,
    fill: bg
  }), React.createElement("circle", {
    cx: x,
    cy: y,
    r: i === 1 ? 22 : 6,
    fill: i === 1 ? b : a,
    stroke: "none"
  }))), React.createElement("circle", {
    cx: "215",
    cy: "195",
    r: "63",
    opacity: ".25"
  }), React.createElement("circle", {
    cx: "340",
    cy: "268",
    r: "40",
    opacity: ".25"
  })), kind === 'wave' && React.createElement("g", {
    fill: "none",
    strokeWidth: "2"
  }, Array.from({
    length: 16
  }, (_, i) => React.createElement("path", {
    key: i,
    d: `M-30 ${85 + i * 17} C110 ${220 + i * 11},155 ${-120 + i * 30},315 ${100 + i * 12} S485 ${460 - i * 12},675 ${125 + i * 17}`,
    stroke: i % 4 === 0 ? b : a,
    opacity: .45 + i * .03
  })), React.createElement("circle", {
    cx: "324",
    cy: "210",
    r: "62",
    stroke: b,
    opacity: ".3"
  })), React.createElement("g", {
    fill: b,
    opacity: ".5"
  }, React.createElement("circle", {
    cx: "36",
    cy: "36",
    r: "2"
  }), React.createElement("circle", {
    cx: "604",
    cy: "384",
    r: "2"
  }))), React.createElement("span", {
    className: "cover-caption"
  }, "\u0418\u041B\u041B\u042E\u0421\u0422\u0420\u0410\u0426\u0418\u042F"));
}
function Bookmark({
  saved,
  onClick,
  title,
  small = false
}) {
  return React.createElement("button", {
    type: "button",
    className: 'bookmark ' + (saved ? 'is-saved ' : '') + (small ? 'small' : ''),
    "aria-label": (saved ? 'Убрать из отложенного: ' : 'Отложить: ') + title,
    "aria-pressed": saved,
    onClick: onClick
  }, React.createElement("span", {
    "aria-hidden": "true"
  }, saved ? '✓' : '+'));
}
function ArticleDialog({
  story,
  saved,
  onSave,
  onClose
}) {
  const dialog = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current.showModal();
    return () => {
      if (dialog.current?.open) dialog.current.close();
      previous?.focus();
    };
  }, []);
  return React.createElement("dialog", {
    ref: dialog,
    className: "article-dialog",
    onCancel: onClose,
    onClick: e => {
      if (e.target === e.currentTarget) onClose();
    },
    "aria-labelledby": "article-title"
  }, React.createElement("button", {
    className: "dialog-close",
    "aria-label": "\u0417\u0430\u043A\u0440\u044B\u0442\u044C \u0441\u0442\u0430\u0442\u044C\u044E",
    onClick: onClose
  }, "\xD7"), React.createElement(Cover, {
    kind: story.art
  }), React.createElement("div", {
    className: "article-body"
  }, React.createElement("div", {
    className: "article-meta"
  }, React.createElement("span", null, story.topic), React.createElement("span", null, prettyDate(story.date), " \xB7 ", story.minutes, " \u043C\u0438\u043D")), React.createElement("h1", {
    id: "article-title"
  }, story.title), React.createElement("p", {
    className: "article-deck"
  }, story.deck), React.createElement("div", {
    className: "article-actions"
  }, React.createElement("button", {
    className: 'button ' + (saved ? 'button-saved' : ''),
    onClick: onSave
  }, saved ? '✓ В отложенном' : '+ Отложить на потом'), React.createElement("span", {
    className: "score"
  }, story.score.toFixed(1), React.createElement("span", null, " / 10"))), React.createElement("p", {
    className: "demo-note"
  }, "\u0414\u0435\u043C\u043E\u043D\u0441\u0442\u0440\u0430\u0446\u0438\u043E\u043D\u043D\u044B\u0439 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B. \u0417\u0430\u0433\u043E\u043B\u043E\u0432\u043E\u043A, \u0440\u0435\u0439\u0442\u0438\u043D\u0433 \u0438 \u0442\u0435\u043A\u0441\u0442 \u043F\u0440\u0438\u0432\u0435\u0434\u0435\u043D\u044B \u0434\u043B\u044F \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0438 \u0438\u043D\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0430, \u0430 \u043D\u0435 \u043A\u0430\u043A \u043E\u043F\u0443\u0431\u043B\u0438\u043A\u043E\u0432\u0430\u043D\u043D\u0430\u044F \u043D\u043E\u0432\u043E\u0441\u0442\u044C."), React.createElement("h2", null, "\u0427\u0442\u043E \u0437\u0434\u0435\u0441\u044C \u0432\u0430\u0436\u043D\u043E"), React.createElement("p", null, "\u041F\u0440\u0438 \u0432\u043E\u0437\u0432\u0440\u0430\u0449\u0435\u043D\u0438\u0438 \u043A \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u0443 \u0432\u0430\u0436\u043D\u0435\u0435 \u043F\u043E\u043C\u043D\u0438\u0442\u044C \u0435\u0433\u043E \u0442\u0435\u043C\u0443, \u0447\u0435\u043C \u0434\u0435\u043D\u044C \u043F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u0438. \u042D\u0442\u0430 \u043A\u0430\u0440\u0442\u043E\u0447\u043A\u0430 \u043F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0435\u0442, \u043A\u0430\u043A \u0431\u0443\u0434\u0435\u0442 \u0432\u044B\u0433\u043B\u044F\u0434\u0435\u0442\u044C \u0447\u0442\u0435\u043D\u0438\u0435 \u0438\u0437 \u043E\u0431\u0449\u0435\u0439 \u043B\u0435\u043D\u0442\u044B: \u043A\u0440\u0430\u0442\u043A\u0438\u0439 \u043A\u043E\u043D\u0442\u0435\u043A\u0441\u0442, \u0437\u0430\u043C\u0435\u0442\u043D\u0430\u044F \u0442\u0435\u043C\u0430 \u0438 \u0432\u043E\u0437\u043C\u043E\u0436\u043D\u043E\u0441\u0442\u044C \u0441\u043E\u0445\u0440\u0430\u043D\u0438\u0442\u044C \u0441\u0442\u0430\u0442\u044C\u044E."), React.createElement("p", null, story.deck, " \u0412 \u0440\u0430\u0431\u043E\u0447\u0435\u043C \u0432\u0430\u0440\u0438\u0430\u043D\u0442\u0435 \u0437\u0434\u0435\u0441\u044C \u0431\u0443\u0434\u0435\u0442 \u043D\u0430\u0441\u0442\u043E\u044F\u0449\u0438\u0439 \u0440\u0430\u0437\u0431\u043E\u0440 \u0438\u0437 \u0430\u0440\u0445\u0438\u0432\u0430 \u0441 \u0438\u0441\u0445\u043E\u0434\u043D\u044B\u043C\u0438 \u0441\u0441\u044B\u043B\u043A\u0430\u043C\u0438 \u0438 \u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E\u0439 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u043E\u0439 \u0443\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043D\u0438\u0439."), React.createElement("blockquote", null, "\u0425\u043E\u0440\u043E\u0448\u0430\u044F \u0433\u043B\u0430\u0432\u043D\u0430\u044F \u043F\u043E\u043C\u043E\u0433\u0430\u0435\u0442 \u0432\u044B\u0431\u0440\u0430\u0442\u044C, \u0447\u0442\u043E \u0447\u0438\u0442\u0430\u0442\u044C. \u0418\u0441\u0442\u043E\u0440\u0438\u044F \u0438 \u043E\u0442\u043B\u043E\u0436\u0435\u043D\u043D\u043E\u0435 \u043F\u043E\u043C\u043E\u0433\u0430\u044E\u0442 \u043A \u044D\u0442\u043E\u043C\u0443 \u0432\u0435\u0440\u043D\u0443\u0442\u044C\u0441\u044F."), React.createElement("h2", null, "\u041E\u0437\u0432\u0443\u0447\u043A\u0430"), React.createElement("p", null, story.audio ? 'В демонстрационных данных у этой статьи отмечена озвучка. Аудиофайл в макет не включён — кнопки с ложным воспроизведением здесь нет.' : 'У этой демонстрационной статьи озвучка пока не готова. Текст остаётся доступен.'), React.createElement("button", {
    className: "text-button",
    onClick: onClose
  }, "\u2190 \u0412\u0435\u0440\u043D\u0443\u0442\u044C\u0441\u044F \u043A \u043F\u043E\u0434\u0431\u043E\u0440\u043A\u0435")));
}
function App() {
  const [initial] = useState(readPrefs);
  const [theme, setTheme] = useState(initial.theme === 'dark' ? 'dark' : 'light');
  const [saved, setSaved] = useState(validIds(initial.saved));
  const [recent, setRecent] = useState(validIds(initial.recent));
  const [view, setView] = useState(['news', 'saved', 'recent'].includes(initial.view) ? initial.view : 'news');
  const [topic, setTopic] = useState(TOPICS.includes(initial.topic) ? initial.topic : 'Все темы');
  const [period, setPeriod] = useState(['all', '7', '30'].includes(initial.period) ? initial.period : 'all');
  const [sort, setSort] = useState(initial.sort === 'score' ? 'score' : 'newest');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState('loading');
  const [toast, setToast] = useState('');
  const timer = useRef(null);
  useEffect(() => {
    const t = setTimeout(() => setStatus('ready'), 450);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(KEY, JSON.stringify({
        theme,
        saved,
        recent,
        view,
        topic,
        period,
        sort
      }));
    } catch {}
  }, [theme, saved, recent, view, topic, period, sort]);
  useEffect(() => () => clearTimeout(timer.current), []);
  function notify(message) {
    setToast(message);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(''), 2500);
  }
  function toggleSaved(s) {
    const exists = saved.includes(s.id);
    setSaved(x => exists ? x.filter(id => id !== s.id) : [s.id, ...x]);
    notify(exists ? 'Убрано из отложенного' : 'Сохранено на потом');
  }
  function openStory(s) {
    setSelected(s);
    setRecent(x => [s.id, ...x.filter(id => id !== s.id)].slice(0, 30));
  }
  function switchView(v) {
    setView(v);
    setQuery('');
    setTopic('Все темы');
    setPeriod('all');
    setStatus('ready');
  }
  function reset() {
    setQuery('');
    setTopic('Все темы');
    setPeriod('all');
    setSort('newest');
    setStatus('ready');
  }
  const filtered = useMemo(() => {
    let result = STORIES.filter(s => view === 'news' || (view === 'saved' ? saved : recent).includes(s.id));
    const q = query.trim().toLocaleLowerCase('ru-RU');
    result = result.filter(s => (topic === 'Все темы' || s.topic === topic) && (!q || [s.title, s.deck, s.topic, s.source].join(' ').toLocaleLowerCase('ru-RU').includes(q)) && (period === 'all' || (TODAY - new Date(s.date + 'T12:00:00Z')) / 86400000 < Number(period)));
    return result.sort((a, b) => view === 'recent' ? recent.indexOf(a.id) - recent.indexOf(b.id) : sort === 'score' ? b.score - a.score : b.date.localeCompare(a.date) || b.score - a.score);
  }, [view, saved, recent, topic, period, query, sort]);
  const showHero = view === 'news' && !query.trim() && topic === 'Все темы' && period === 'all' && sort === 'newest' && status === 'ready';
  const feed = showHero ? filtered.filter(s => !HERO_IDS.includes(s.id)) : filtered;
  const title = view === 'saved' ? 'Отложенное' : view === 'recent' ? 'Недавно открывали' : 'Ваш новостной горизонт';
  const deck = view === 'saved' ? 'То, к чему хочется вернуться. Сохранено в этом браузере.' : view === 'recent' ? 'Ваш путь по материалам — без необходимости вспоминать дату.' : 'Важное из ваших источников. И всё, что стоит перечитать.';
  function renderCard(s, lead = false) {
    return React.createElement("article", {
      key: s.id,
      className: 'story ' + (lead ? 'lead' : ''),
      "data-story-id": s.id,
      "data-score": s.score
    }, React.createElement(Cover, {
      kind: s.art
    }), React.createElement("div", {
      className: "story-body"
    }, React.createElement("div", {
      className: "story-topline"
    }, React.createElement("span", null, s.topic), React.createElement("span", {
      className: "story-score"
    }, s.score.toFixed(1), React.createElement("small", null, " / 10"))), React.createElement("h3", null, React.createElement("button", {
      className: "story-open",
      onClick: () => openStory(s)
    }, s.title)), React.createElement("p", null, s.deck), React.createElement("div", {
      className: "story-bottom"
    }, React.createElement("span", null, prettyDate(s.date), React.createElement("span", {
      className: "dot"
    }, "\xB7"), s.minutes, " \u043C\u0438\u043D", s.audio && React.createElement("span", {
      className: "audio-label",
      title: "\u041E\u0437\u0432\u0443\u0447\u043A\u0430 \u043E\u0442\u043C\u0435\u0447\u0435\u043D\u0430 \u0432 \u0434\u0435\u043C\u043E\u0434\u0430\u043D\u043D\u044B\u0445"
    }, " \xB7 \u0410\u0443\u0434\u0438\u043E")), React.createElement(Bookmark, {
      saved: saved.includes(s.id),
      onClick: () => toggleSaved(s),
      title: s.title
    }))));
  }
  return React.createElement(React.Fragment, null, React.createElement("div", {
    className: "demo-ribbon"
  }, React.createElement("span", null, "\u041F\u0420\u041E\u0422\u041E\u0422\u0418\u041F"), " \u0414\u0435\u043C\u043E\u043D\u0441\u0442\u0440\u0430\u0446\u0438\u043E\u043D\u043D\u044B\u0435 \u0441\u0442\u0430\u0442\u044C\u0438 \u0438 \u043E\u0431\u043B\u043E\u0436\u043A\u0438 \xB7 \u0440\u0430\u0431\u043E\u0447\u0438\u0439 \u0441\u0430\u0439\u0442 \u043D\u0435 \u0438\u0437\u043C\u0435\u043D\u0451\u043D"), React.createElement("header", {
    className: "site-header"
  }, React.createElement("div", {
    className: "header-inner"
  }, React.createElement("a", {
    className: "brand",
    href: "./",
    onClick: e => {
      e.preventDefault();
      switchView('news');
    }
  }, React.createElement("img", {
    src: "penguin.png",
    width: "39",
    height: "39",
    alt: ""
  }), React.createElement("span", null, "Digest ", React.createElement("strong", null, "Ninitux"))), React.createElement("nav", {
    "aria-label": "\u0420\u0430\u0437\u0434\u0435\u043B\u044B"
  }, React.createElement("button", {
    className: view === 'news' ? 'active' : '',
    onClick: () => switchView('news')
  }, "\u0413\u043B\u0430\u0432\u043D\u0430\u044F"), React.createElement("button", {
    className: view === 'saved' ? 'active' : '',
    onClick: () => switchView('saved')
  }, "\u041E\u0442\u043B\u043E\u0436\u0435\u043D\u043D\u043E\u0435 ", React.createElement("span", {
    className: "nav-count"
  }, saved.length)), React.createElement("button", {
    className: view === 'recent' ? 'active' : '',
    onClick: () => switchView('recent')
  }, "\u0418\u0441\u0442\u043E\u0440\u0438\u044F")), React.createElement("button", {
    className: "theme-toggle",
    onClick: () => setTheme(t => t === 'light' ? 'dark' : 'light'),
    "aria-label": theme === 'light' ? 'Включить тёмную тему' : 'Включить светлую тему'
  }, React.createElement("span", {
    "aria-hidden": "true"
  }, theme === 'light' ? '◐' : '◑')))), React.createElement("main", null, React.createElement("div", {
    className: "intro"
  }, React.createElement("div", null, React.createElement("p", {
    className: "eyebrow"
  }, "\u041B\u0418\u0427\u041D\u0410\u042F \u041B\u0415\u041D\u0422\u0410 / \u0414\u0415\u041C\u041E 30 \u0421\u0415\u041D\u0422\u042F\u0411\u0420\u042F"), React.createElement("h1", null, title), React.createElement("p", {
    className: "intro-deck"
  }, deck)), React.createElement("div", {
    className: "edition"
  }, React.createElement("span", null, "\u041E\u0422\u0411\u041E\u0420 \u041F\u041E \u0418\u041D\u0422\u0415\u0420\u0415\u0421\u0410\u041C"), React.createElement("b", null, "\u0421\u0432\u0435\u0436\u0438\u0435 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u044B.", React.createElement("br", null), "\u0410\u0440\u0445\u0438\u0432 \u0431\u0435\u0437 \u043A\u0430\u043B\u0435\u043D\u0434\u0430\u0440\u044F."))), React.createElement("section", {
    className: "controls",
    "aria-label": "\u041D\u0430\u0441\u0442\u0440\u043E\u0439\u043A\u0438 \u043B\u0435\u043D\u0442\u044B"
  }, React.createElement("div", {
    className: "search-wrap"
  }, React.createElement("span", {
    "aria-hidden": "true"
  }, "\u2315"), React.createElement("input", {
    "aria-label": "\u041D\u0430\u0439\u0442\u0438 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B",
    type: "search",
    placeholder: "\u041D\u0430\u0439\u0442\u0438 \u0441\u0442\u0430\u0442\u044C\u044E, \u0442\u0435\u043C\u0443 \u0438\u043B\u0438 \u0438\u0441\u0442\u043E\u0447\u043D\u0438\u043A",
    value: query,
    onChange: e => setQuery(e.target.value)
  }), query && React.createElement("button", {
    className: "clear-search",
    "aria-label": "\u041E\u0447\u0438\u0441\u0442\u0438\u0442\u044C \u043F\u043E\u0438\u0441\u043A",
    onClick: () => setQuery('')
  }, "\xD7")), React.createElement("label", {
    className: "period"
  }, "\u041F\u0435\u0440\u0438\u043E\u0434", React.createElement("select", {
    "aria-label": "\u041F\u0435\u0440\u0438\u043E\u0434 \u043F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u0438",
    value: period,
    onChange: e => setPeriod(e.target.value)
  }, React.createElement("option", {
    value: "all"
  }, "\u0412\u0441\u0451 \u0432\u0440\u0435\u043C\u044F"), React.createElement("option", {
    value: "7"
  }, "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 7 \u0434\u043D\u0435\u0439"), React.createElement("option", {
    value: "30"
  }, "\u041F\u043E\u0441\u043B\u0435\u0434\u043D\u0438\u0435 30 \u0434\u043D\u0435\u0439"))), React.createElement("div", {
    className: "sort-toggle",
    role: "group",
    "aria-label": "\u041F\u043E\u0440\u044F\u0434\u043E\u043A \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u043E\u0432"
  }, React.createElement("button", {
    "aria-pressed": sort === 'newest',
    onClick: () => setSort('newest')
  }, "\u0421\u0432\u0435\u0436\u0438\u0435"), React.createElement("button", {
    "aria-pressed": sort === 'score',
    onClick: () => setSort('score')
  }, "\u041F\u043E \u0440\u0435\u0439\u0442\u0438\u043D\u0433\u0443"))), React.createElement("div", {
    className: "topics",
    role: "group",
    "aria-label": "\u0422\u0435\u043C\u044B"
  }, TOPICS.map(t => React.createElement("button", {
    key: t,
    "aria-pressed": topic === t,
    onClick: () => setTopic(t)
  }, t))), status === 'loading' ? React.createElement("section", {
    className: "loading-panel",
    role: "status"
  }, React.createElement("span", {
    className: "loading-dot"
  }), "\u0421\u043E\u0431\u0438\u0440\u0430\u0435\u043C \u0434\u0435\u043C\u043E\u043D\u0441\u0442\u0440\u0430\u0446\u0438\u043E\u043D\u043D\u0443\u044E \u043B\u0435\u043D\u0442\u0443\u2026", React.createElement("div", {
    className: "skeleton-grid"
  }, [1, 2, 3].map(i => React.createElement("div", {
    key: i
  })))) : status === 'error' ? React.createElement("section", {
    className: "empty-panel",
    role: "alert"
  }, React.createElement("span", {
    className: "empty-symbol"
  }, "!"), React.createElement("h2", null, "\u041B\u0435\u043D\u0442\u0430 \u0432\u0440\u0435\u043C\u0435\u043D\u043D\u043E \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0430"), React.createElement("p", null, "\u042D\u0442\u043E \u0434\u0435\u043C\u043E\u043D\u0441\u0442\u0440\u0430\u0446\u0438\u044F \u043E\u0448\u0438\u0431\u043A\u0438 \u0437\u0430\u0433\u0440\u0443\u0437\u043A\u0438. \u0421\u0442\u0430\u0442\u044C\u0438 \u0438 \u0432\u0430\u0448\u0438 \u0437\u0430\u043A\u043B\u0430\u0434\u043A\u0438 \u043D\u0435 \u043F\u043E\u0442\u0435\u0440\u044F\u043D\u044B."), React.createElement("button", {
    className: "button",
    onClick: () => {
      setStatus('loading');
      setTimeout(() => setStatus('ready'), 450);
    }
  }, "\u041F\u043E\u043F\u0440\u043E\u0431\u043E\u0432\u0430\u0442\u044C \u0441\u043D\u043E\u0432\u0430")) : React.createElement(React.Fragment, null, showHero && React.createElement("section", {
    className: "hero-section",
    "aria-labelledby": "hero-title"
  }, React.createElement("div", {
    className: "section-heading"
  }, React.createElement("h2", {
    id: "hero-title"
  }, "\u0412 \u0444\u043E\u043A\u0443\u0441\u0435"), React.createElement("span", null, "5 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u043E\u0432 \xB7 \u0440\u0430\u0437\u043D\u044B\u0435 \u0442\u0435\u043C\u044B")), React.createElement("div", {
    className: "hero-grid"
  }, STORIES.slice(0, 5).map((s, i) => renderCard(s, i === 0)))), React.createElement("section", {
    className: "archive-section",
    "aria-labelledby": "feed-title"
  }, React.createElement("div", {
    className: "section-heading"
  }, React.createElement("h2", {
    id: "feed-title"
  }, view === 'news' ? showHero ? 'Ещё в ленте' : 'Материалы архива' : title), React.createElement("span", null, feed.length, " ", feed.length === 1 ? 'материал' : feed.length > 1 && feed.length < 5 ? 'материала' : 'материалов')), feed.length === 0 ? React.createElement("div", {
    className: "empty-panel"
  }, React.createElement("span", {
    className: "empty-symbol"
  }, "\u2197"), React.createElement("h2", null, view === 'saved' && saved.length === 0 ? 'Здесь будут ваши находки' : view === 'recent' && recent.length === 0 ? 'Ваша история начинается с первой статьи' : 'Ничего не нашлось'), React.createElement("p", null, view === 'saved' && saved.length === 0 ? 'Нажмите «+» на карточке — и материал останется под рукой.' : view === 'recent' && recent.length === 0 ? 'Откройте любой материал на главной. Мы запомним его в этом браузере.' : 'Попробуйте другую тему или снимите ограничения периода.'), React.createElement("button", {
    className: "button",
    onClick: () => {
      if (view !== 'news' && (view === 'saved' ? saved : recent).length === 0) switchView('news');else reset();
    }
  }, view !== 'news' && (view === 'saved' ? saved : recent).length === 0 ? 'К подборке' : 'Сбросить фильтры')) : React.createElement("div", {
    className: "feed-layout"
  }, React.createElement("div", {
    className: "feed-grid"
  }, feed.map(s => renderCard(s))), React.createElement("aside", {
    className: "reading-sidebar"
  }, React.createElement("div", {
    className: "side-label"
  }, "\u041F\u041E\u0414 \u0420\u0423\u041A\u041E\u0419"), React.createElement("h2", null, "\u0412\u0435\u0440\u043D\u0443\u0442\u044C\u0441\u044F", React.createElement("br", null), "\u043A \u043F\u0440\u043E\u0447\u0438\u0442\u0430\u043D\u043D\u043E\u043C\u0443"), recent.length > 0 ? React.createElement("ul", null, recent.slice(0, 3).map(id => {
    const s = STORIES.find(x => x.id === id);
    return React.createElement("li", {
      key: id
    }, React.createElement("span", null, s.topic), React.createElement("button", {
      onClick: () => openStory(s)
    }, s.title, React.createElement("span", {
      "aria-hidden": "true"
    }, " \u2197")));
  })) : React.createElement("p", null, "\u041E\u0442\u043A\u0440\u044B\u0442\u044B\u0435 \u043C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u044B \u043F\u043E\u044F\u0432\u044F\u0442\u0441\u044F \u0437\u0434\u0435\u0441\u044C. \u041D\u0435 \u043D\u0443\u0436\u043D\u043E \u0437\u0430\u043F\u043E\u043C\u0438\u043D\u0430\u0442\u044C \u0432\u044B\u043F\u0443\u0441\u043A \u0438\u043B\u0438 \u0434\u0430\u0442\u0443."), React.createElement("button", {
    className: "text-button",
    onClick: () => switchView(recent.length ? 'recent' : 'saved')
  }, recent.length ? 'Вся история →' : 'Открыть отложенное →'), React.createElement("div", {
    className: "side-divider"
  }), React.createElement("span", {
    className: "side-label"
  }, "\u041E \u0420\u0415\u0419\u0422\u0418\u041D\u0413\u0415"), React.createElement("p", null, "\u041E\u0446\u0435\u043D\u043A\u0430 \u0438\u043D\u0442\u0435\u0440\u0435\u0441\u0430 \u2014 \u043D\u0435 \u043F\u0440\u043E\u0432\u0435\u0440\u043A\u0430 \u0438\u0441\u0442\u0438\u043D\u043D\u043E\u0441\u0442\u0438. \u0412 \u044D\u0442\u043E\u043C \u043C\u0430\u043A\u0435\u0442\u0435 \u0432\u0441\u0435 \u043E\u0446\u0435\u043D\u043A\u0438 \u0434\u0435\u043C\u043E\u043D\u0441\u0442\u0440\u0430\u0446\u0438\u043E\u043D\u043D\u044B\u0435."))))), React.createElement("footer", {
    className: "footer"
  }, React.createElement("div", null, React.createElement("b", null, "Digest Ninitux"), React.createElement("p", null, "\u0421\u043E\u0445\u0440\u0430\u043D\u0451\u043D\u043D\u043E\u0435 \u0438 \u0438\u0441\u0442\u043E\u0440\u0438\u044F \u043E\u0441\u0442\u0430\u044E\u0442\u0441\u044F \u0432 \u044D\u0442\u043E\u043C \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435.")), React.createElement("details", {
    className: "demo-controls"
  }, React.createElement("summary", null, "\u041F\u0440\u043E\u0432\u0435\u0440\u0438\u0442\u044C \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u044F \u043C\u0430\u043A\u0435\u0442\u0430"), React.createElement("div", null, React.createElement("button", {
    onClick: () => setStatus('loading')
  }, "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430"), React.createElement("button", {
    onClick: () => setStatus('error')
  }, "\u041E\u0448\u0438\u0431\u043A\u0430"), React.createElement("button", {
    onClick: () => {
      setQuery('нет-совпадений-000');
      setStatus('ready');
    }
  }, "\u041F\u0443\u0441\u0442\u0430\u044F \u0432\u044B\u0434\u0430\u0447\u0430"), React.createElement("button", {
    onClick: reset
  }, "\u0412\u0435\u0440\u043D\u0443\u0442\u044C \u043B\u0435\u043D\u0442\u0443"))))), React.createElement("div", {
    className: 'toast ' + (toast ? 'visible' : ''),
    role: "status",
    "aria-live": "polite"
  }, toast), selected && React.createElement(ArticleDialog, {
    story: selected,
    saved: saved.includes(selected.id),
    onSave: () => toggleSaved(selected),
    onClose: () => setSelected(null)
  }));
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App, null));