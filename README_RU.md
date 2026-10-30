# 🚀 Cloudflare Turnstile & IUAM Automation API

Локальный REST API для автоматизированного прохождения страниц-вызовов Cloudflare Turnstile и IUAM (Under Attack Mode) в реальном браузере — возвращает токены и `cf_clearance`-сессии.

[![Version](https://img.shields.io/badge/version-2.1.0-blue)](https://github.com/D3-vin/Turnstile-Solver-NEW/releases)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Educational%20Use-green)](LICENSE)

[![Telegram Channel](https://img.shields.io/badge/Telegram-Канал-blue?logo=telegram)](https://t.me/D3_vin)
[![Telegram Chat](https://img.shields.io/badge/Telegram-Чат-blue?logo=telegram)](https://t.me/D3vin_chat)
[![GitHub](https://img.shields.io/badge/GitHub-Репозиторий-black?logo=github)](https://github.com/D3-vin/Turnstile-Solver-NEW)

[Возможности](#возможности) • [Как это работает](#как-это-работает) • [Быстрый старт](#быстрый-старт) • [Использование](#использование) • [API](#api-документация) • [Проблемы](#решение-проблем) • [Changelog](CHANGELOG.md) • [Контакты](#контакты)

[English](README.md) | [Русский](#)

---

> **Новое в 2.1:** headed Chrome по умолчанию, правила stealth проверены на реальном Cloudflare challenge, `proxy` на запрос для `/turnstile`, надёжная обработка виджета в Next.js/SPA, человекоподобный клик, ограниченные дедлайны решения и рабочий `test_solve.py`. Проверено на iHerb (`checkout9.iherb.com`, sitekey `0x4AAAAAADmKZAkmJVxUyvHF`, action `account_check`) — токен из 752 символов.

## Возможности

- 🎯 **Автоматизация Turnstile** — route-intercept заглушка с fallback на реальную страницу; обычно 4–20 секунд решения без учёта очереди и запуска браузера
- 🛡️ **Прохождение IUAM / Challenge** — Managed Challenge + JS Challenge interstitial, получение `cf_clearance` с полным набором для replay (cookies, User-Agent, заголовки)
- 🥷 **Stealth-first** — Patchright + реальный **headed** Chrome. Без подмены User-Agent/locale/отпечатка (init-скрипты сами по себе детектируются Turnstile)
- 🚀 **Многопоточность** — несколько задач одновременно с лимитом конкуренции
- 🌐 **Несколько браузеров** — Chrome, Edge, Chromium, Camoufox
- 🔌 **Поддержка прокси** — все распространённые форматы из `proxies.txt` плюс `proxy` на запрос для обоих эндпоинтов
- 📊 **REST API** — асинхронная модель задач (создать задачу → опросить результат), легко интегрировать
- 📦 **Без базы данных** — задачи живут в памяти, обслуживание не нужно

---

## Как это работает

### Turnstile (`/turnstile`)

1. Создаётся контекст браузера, при необходимости с прокси на запрос.
2. Solver регистрирует route для целевого URL и отдаёт минимальную страницу с Turnstile-виджетом (`sitekey`, `action`, `cdata`).
3. Виджет рендерится на **целевом origin** (например `checkout9.iherb.com`), поэтому sitekey, привязанный к домену, продолжает работать, а реальная страница и её WAF не загружаются.
4. Solver ждёт iframe Turnstile и читает токен из `input[name=cf-turnstile-response]` или callback виджета.
5. Если Turnstile требует взаимодействия, выполняется человекоподобное движение мыши по кривой Безье и клик по чекбоксу.
6. Если route-подход не сработал, solver снимает route, загружает реальную страницу, ждёт прохождения interstitial Cloudflare, гидратации SPA/виджета, при необходимости внедряет виджет и повторяет попытку в пределах оставшегося дедлайна.

### IUAM / `cf_clearance` (`/cf_clearance`)

1. Реальный защищённый URL загружается в headed-браузере.
2. Если присутствует interstitial Cloudflare, выполняется человекоподобный клик по чекбоксу.
3. Контекст опрашивается, пока не появится cookie `cf_clearance` **и** interstitial не исчезнет.
4. API возвращает cookie, все cookies контекста, User-Agent, `Accept-Language` и предупреждение о replay.

### Правила stealth (важно)

Проверено на реальном Turnstile iHerb:

- **Headed Chrome обязателен** для реальных challenge. `--headless=new` детектируется даже с persistent-профилем и подменой UA.
- **Не задавайте User-Agent.** UA Chrome 150 при установленном Chrome 156 делает `navigator.userAgentData` несогласованным, и challenge не проходит.
- **Не переопределяйте locale/timezone.** Одного `locale="en-US"` достаточно, чтобы токен никогда не пришёл.
- **Не внедряйте JS-отпечатки.** Любой `context.add_init_script()`, даже пустая строка, детектируется Turnstile. Patchright уже скрывает `navigator.webdriver`; headed Chrome сам по себе имеет настоящие `window.chrome`, plugins, languages, WebGL и audio.
- `--debug` печатает отчёт об отпечатке (`webdriver`, `chrome`, plugins, languages, WebGL, screen, timezone), чтобы регрессии были видны.

### Жизненный цикл задач

- Задачи хранятся в RAM. Перезапуск сервера их теряет.
- Задачи старше **3600 с** удаляются каждые **600 с**.
- `--thread` (по умолчанию **4**) ограничивает число одновременных браузерных задач; остальные ждут со статусом `processing`.
- Нет эндпоинта отмены и ключа идемпотентности. Каждый вызов создаёт новую задачу.
- Время в очереди и запуск браузера **не входят** в `timeout` solver'а; клиентский дедлайн нужен отдельно.

---

## Быстрый старт

### 1. Установка

```bash
git clone https://github.com/D3-vin/Turnstile-Solver-NEW.git
cd Turnstile-Solver-NEW
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Установка браузера

```bash
python -m patchright install chromium   # или: install msedge / системный Chrome
python -m camoufox fetch                # опционально, только для --browser_type camoufox
```

Рекомендуется системный Chrome через `channel="chrome"`. Если Chrome уже установлен, дополнительное скачивание не нужно.

### 3. Запуск

```bash
python api.py
```

Сервер стартует на `http://0.0.0.0:5072`. Браузер по умолчанию работает **headed** — реальные Turnstile/WAF challenge отвергают headless Chrome даже со stealth-патчами. `--headless` используйте только для тестовых ключей Turnstile.

На Windows можно запустить `start_solver.bat` (bind `127.0.0.1:5072`).

> На Linux без рабочего стола запускайте Chrome под Xvfb (`xvfb-run -a python api.py`). Если `DISPLAY`/`WAYLAND_DISPLAY` не найдены, сервер перейдёт в headless, и реальные challenge работать не будут.

---

## Использование

```bash
python api.py [опции]

Опции:
  --headless              Без окна (только тестовые ключи; реальному Cloudflare нужен дисплей)
  --no-headless           Показывать окно браузера (по умолчанию)
  --browser_type string   chromium | chrome | msedge | camoufox (по умолчанию "chrome")
  --thread int            Максимум параллельных задач (по умолчанию 4)
  --proxy                 Использовать случайный прокси из proxies.txt
  --useragent string      Свой User-Agent (лучше не задавать для реальных challenge)
  --debug                 Подробные логи + отпечаток браузера + HTTP access-логи
  --host string           Адрес (по умолчанию "0.0.0.0")
  --port string           Порт (по умолчанию "5072")
```

### Тестовый клиент

`test_solve.py` по умолчанию использует публичный Turnstile demo. Поддерживает оба типа задач, прокси на запрос и клиентский дедлайн.

```bash
# Turnstile demo (dummy token)
python test_solve.py

# IUAM / cf_clearance (по умолчанию ivasms.com)
python test_solve.py --type cf_clearance
python test_solve.py --type cf_clearance --proxy http://user:pass@ip:port

# Реальный Turnstile, привязанный к домену (iHerb)
python test_solve.py --type turnstile --url https://checkout9.iherb.com/auth/ui/account/login --sitekey 0x4AAAAAADmKZAkmJVxUyvHF --action account_check
```

| Опция клиента | По умолчанию | Описание |
|---|---|---|
| `--type` | `turnstile` | `turnstile` или `cf_clearance` |
| `--base` | `http://127.0.0.1:5072` | Базовый URL solver'а |
| `--url` | demo / ivasms | URL целевой страницы |
| `--sitekey` | demo key | Ключ сайта Turnstile |
| `--action` | — | `data-action` виджета |
| `--cdata` | — | `data-cdata` виджета |
| `--proxy` | — | Прокси на запрос |
| `--solve-timeout` | `60` | Ожидание cookie `cf_clearance` на сервере |
| `--deadline` | `180` | Общий клиентский дедлайн (секунды) |

---

## API-документация

Все эндпоинты — **HTTP GET** и возвращают JSON. API-ключа нет. Бизнес-ошибки также используют HTTP 200; проверяйте поле `errorId`.

`GET /` возвращает HTML-страницу с инструкцией, а не JSON health check.

### Turnstile

```
GET /turnstile?url=https://example.com&sitekey=0x4AAAAAAA
```

| Параметр | Тип | Описание | Обязателен |
|----------|-----|----------|------------|
| `url` | string | Страница, на которой валидируется Turnstile | Да |
| `sitekey` | string | Ключ сайта Turnstile | Да |
| `action` | string | Привязка виджета `data-action` | Нет |
| `cdata` | string | Привязка виджета `data-cdata` | Нет |
| `proxy` | string | Прокси на запрос (`http://user:pass@host:port`) | Нет |
| `timeout` | int | Бюджет решения в секундах после запуска браузера (по умолчанию 90, минимум 10) | Нет |

> `proxy` применяется к контексту браузера **до** навигации, поэтому Turnstile видит выходной IP прокси, а не IP сервера. Если параметр не задан, а сервер запущен с `--proxy`, берётся случайный прокси из `proxies.txt`.

### IUAM (`cf_clearance`)

```
GET /cf_clearance?url=https://protected.com&proxy=http://user:pass@ip:port
```

| Параметр | Тип | Описание | Обязателен |
|----------|-----|----------|------------|
| `url` | string | URL страницы под защитой Cloudflare | Да |
| `proxy` | string | Прокси на запрос (`cf_clearance` привязан к выходному IP) | Нет |
| `timeout` | int | Ожидание cookie в секундах (по умолчанию 60, минимум 10) | Нет |

### Создание задачи

Оба эндпоинта возвращают:

```json
{ "errorId": 0, "taskId": "d2bcb257-9c37-4f9c-9bc7-1eaee72d96a8" }
```

Это подтверждает только создание задачи, а не успешное решение.

### Получение результата

```
GET /result?id=d2bcb257-9c37-4f9c-9bc7-1eaee72d96a8
```

В обработке (или ожидание свободного слота):

```json
{ "status": "processing" }
```

Turnstile готов:

```json
{ "errorId": 0, "status": "ready", "solution": { "token": "1.xxxxx..." } }
```

`/result` намеренно **не** отдаёт внутренний `method` (`route` / `real-page`) и тайминги solver'а для Turnstile.

`cf_clearance` готов:

```json
{
  "errorId": 0,
  "status": "ready",
  "solution": {
    "cf_clearance": {
      "name": "cf_clearance",
      "value": "...",
      "domain": ".example.com",
      "path": "/",
      "httpOnly": true,
      "secure": true
    },
    "cookies": [ "..." ],
    "user_agent": "Mozilla/5.0 ...",
    "headers": { "User-Agent": "Mozilla/5.0 ...", "Accept-Language": "en-US" },
    "elapsed": 12.3,
    "elapsed_time": 14.567,
    "proxy": "http://...",
    "warning": "cf_clearance привязан к IP + JA3/TLS + User-Agent..."
  }
}
```

> ⚠️ Использовать `cf_clearance` повторно можно только с того же IP, с возвращённым `user_agent` и клиентом с совпадающим TLS-отпечатком (curl-impersonate или реальный браузер).

### Коды ошибок

Бизнес-ошибки используют HTTP 200 и `errorId: 1`:

```json
{
  "errorId": 1,
  "errorCode": "ERROR_CAPTCHA_UNSOLVABLE",
  "errorDescription": "Workers could not solve the Captcha"
}
```

| `errorCode` | Значение | Действие клиента |
|---|---|---|
| `ERROR_WRONG_PAGEURL` | Нет `url` или нет `sitekey` для Turnstile | Исправить запрос |
| `ERROR_WRONG_PROXY` | `proxy` не удалось разобрать | Исправить формат прокси |
| `ERROR_WRONG_CAPTCHA_ID` | Неизвестный, истёкший или удалённый task ID | Прекратить polling |
| `ERROR_CAPTCHA_UNSOLVABLE` | Нет токена/cookie, ошибка браузера или исключение | Прекратить polling; смотреть логи сервера |

Ответы `processing` не содержат `errorId`; это не ошибка. Подробные исключения клиенту не возвращаются.

---

## Форматы прокси

`proxies.txt` принимает один прокси на строку. Пустые строки и строки, начинающиеся с `#`, игнорируются.

```text
# host:port
1.2.3.4:8080

# host:port:user:pass
1.2.3.4:8080:user:pass

# user:pass@host:port
user:pass@1.2.3.4:8080

# scheme://host:port
socks5://1.2.3.4:1080

# scheme://user:pass@host:port
http://user:pass@1.2.3.4:8080
```

Те же форматы принимает query-параметр `proxy`. Учётные данные прокси маскируются в debug-логах.

---

## Структура проекта

```
Turnstile-Solver-NEW/
├── api.py               # Quart-приложение: маршруты, задачи в памяти, CLI
├── test_solve.py        # Тестовый клиент (turnstile / cf_clearance)
├── requirements.txt
├── API_INTEGRATION.md   # Подробное руководство по интеграции
├── CHANGELOG.md         # История изменений
├── core/
│   ├── browser.py       # Конфигурация браузера, запуск, контекст, прокси
│   ├── logger.py        # Цветной логгер
│   ├── stealth.py       # UA/Client-Hints + проверка отпечатка
│   └── templates.py     # HTML-шаблон Turnstile, JS-сниппеты, route glob
├── turnstile/
│   └── solve.py         # Route-intercept + автоматизация Turnstile на реальной странице
└── cf_clearance/
    └── solve.py         # Прохождение IUAM interstitial + cf_clearance-сессия
```

---

## Решение проблем

### "Browser not found"

Установите браузер: `python -m patchright install chromium` (или `--browser_type chrome` с системным Chrome).

### "Port already in use"

Смените порт: `python api.py --port 5080`.

### `ERROR_CAPTCHA_UNSOLVABLE` на реальном сайте

1. Убедитесь, что браузер **headed** (по умолчанию). `--headless` отвергается реальными Cloudflare challenge.
2. **Не задавайте `--useragent`**: принудительный UA, отличающийся от реальной версии Chrome, делает `navigator.userAgentData` несогласованным.
3. Смотрите `--debug`:
   - `Route-intercept ...` и затем `Turnstile solved via route` — виджет работает.
   - `Real-page returned HTTP 403 (Cloudflare WAF?)` — целевая страница за WAF; route-intercept специально её обходит.
   - `Turnstile widget error: ...` — неверный sitekey/домен/action, stealth не поможет.
4. Датацентровские IP оцениваются строго — передавайте `proxy=` на запрос или используйте резидентский прокси.
5. Нужен реальный дисплей/окно. На Windows — интерактивная сессия, на Linux — Xvfb.

### `cf_clearance` не установлен

- Убедитесь, что браузер headed.
- Проверьте, что выходной IP прокси не заблокирован.
- Некоторым сайтам нужен конкретный регион или резидентский IP.
- `timeout` покрывает только ожидание cookie, а не очередь и запуск браузера. Увеличьте его и/или клиентский дедлайн.

### Остаются окна Chrome

Каждая задача закрывает свой browser и context. При Ctrl+C сервер убивает дочерние процессы через `psutil`. Если после жёсткого завершения остались orphan-процессы, завершите `chrome.exe` вручную.

---

## Замечания по развёртыванию

- **Windows:** запускайте API в интерактивной сессии рабочего стола. Служба в session 0 не имеет реального дисплея и может вести себя как headless.
- **Linux:** используйте `xvfb-run -a python api.py` или реальный X11/Wayland.
- **Docker:** добавьте Chrome/Chromium и Xvfb в entrypoint; headless не подходит для реальных challenge.
- **Конкурентность:** каждая задача запускает полноценный браузер. Уменьшайте `--thread` на слабых машинах.
- **Безопасность:** у API нет аутентификации. Слушайте только `127.0.0.1` или доверенную сеть.

---

## Контакты

- **GitHub**: https://github.com/D3-vin/Turnstile-Solver-NEW
- **Telegram Канал**: [@D3_vin](https://t.me/D3_vin)
- **Telegram Чат**: [@D3vin_chat](https://t.me/D3vin_chat)

---

## Лицензия

Только для образовательных целей — см. файл [LICENSE](LICENSE).

## ⚠️ Отказ от ответственности

ПО предоставляется **исключительно в образовательных и ознакомительных целях**, «как есть» (AS IS), без каких-либо гарантий. Автор не несёт ответственности за любое использование, блокировки API, баны IP и иные последствия — вся ответственность лежит на конечном пользователе. Не аффилировано с Cloudflare, Inc.

> This software is provided for educational and research purposes only, "AS IS". The author is not responsible for any misuse.
