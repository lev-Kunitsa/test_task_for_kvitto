# Kvitto Payments API

Сервис приёма оплаты курса: тарифы, создание платежа (с промокодом и рассрочкой),
идемпотентность через `Idempotency-Key` и вебхук банка о смене статуса.

Стек: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, pytest + httpx, ruff.

**Содержание**

1. [Запуск через Docker](#1-запуск-через-docker)
2. [Тесты через Docker](#2-тесты-через-docker)
3. [Локальный запуск без Docker](#3-локальный-запуск-без-docker)
4. [Локальные тесты и линтер](#4-локальные-тесты-и-линтер)
5. [Ручная проверка API](#5-ручная-проверка-api)
6. [Эндпоинты](#6-эндпоинты)
7. [Бизнес-правила и принятые решения](#7-бизнес-правила-и-принятые-решения)
8. [Структура проекта](#8-структура-проекта)

---

## 1. Запуск через Docker

**Нужно:** Docker с Compose v2 (Docker Desktop на Windows/macOS) и свободный порт 8000.
Python и прочие зависимости на машине не нужны — всё ставится внутри образа.

Из корня репозитория:

```bash
docker compose up --build
```

Что происходит:

1. Собирается образ на `python:3.13-slim`, внутри ставятся зависимости из `requirements.txt`
   (версии закреплены).
2. Создаётся volume `data` — в нём хранится файл базы SQLite `/data/kvitto.db`.
3. При старте приложение создаёт таблицы и тарифы `basic`, `standard`, `premium`.
4. В логах появится `Uvicorn running on http://0.0.0.0:8000` — сервис готов.

Проверка, что всё поднялось:

- http://127.0.0.1:8000/tariffs — список из трёх тарифов;
- http://127.0.0.1:8000/docs — Swagger UI, через него можно вызвать любой эндпоинт из браузера.

Управление:

| Действие | Команда |
|---|---|
| Запустить в фоне | `docker compose up --build -d` |
| Посмотреть логи | `docker compose logs -f app` |
| Остановить (данные сохраняются) | `docker compose down` или `Ctrl+C`, если запущено не в фоне |
| Остановить и удалить базу | `docker compose down -v` |
| Пересобрать после изменения кода | `docker compose up --build` |

Если порт 8000 занят, в `docker-compose.yml` поменяйте `"8000:8000"` на, например,
`"8080:8000"` и обращайтесь к http://127.0.0.1:8080.

## 2. Тесты через Docker

Автотесты (pytest) и линтер (ruff) запускаются одной командой — без локального Python:

```bash
docker compose run --rm --build tests
```

Ожидаемый результат — `74 passed`, `All checks passed!`, `18 files already formatted`;
код выхода 0 при успехе и не 0, если что-то упало. `--build` пересобирает тестовый образ из
текущего кода, `--rm` удаляет контейнер после прогона.

Как это устроено:

- В `Dockerfile` две стадии поверх общей основы: `app` — только приложение, `tests` — плюс
  `requirements-dev.txt` (pytest, httpx, ruff) и папка `tests/`. Образ приложения остаётся
  без тестов и dev-зависимостей.
- В `docker-compose.yml` сервис `tests` вынесен в профиль `tests`, поэтому обычный
  `docker compose up` его не запускает — поднимается только приложение.
- Зависимости ставятся один раз при сборке и кэшируются; повторный прогон занимает секунды.
- Поднимать приложение для тестов не нужно: у них своя in-memory база, данные в volume `data`
  они не трогают.

Запустить только часть тестов — передать свою команду вместо стандартной:

```bash
docker compose run --rm --build tests pytest tests/test_webhooks.py -v
```

Удалить всё, что создал проект в Docker, включая тестовый образ:

```bash
docker compose --profile tests down -v --rmi local
```

Ручные запросы к поднятому сервису — в [разделе 5](#5-ручная-проверка-api).

## 3. Локальный запуск без Docker

**Нужно:** Python 3.11 или новее.

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

> Если PowerShell запрещает запуск `Activate.ps1`, разрешите скрипты для текущего окна:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

Сервис поднимется на http://127.0.0.1:8000 (Swagger — http://127.0.0.1:8000/docs),
`--reload` перезапускает его при изменении кода.

База — файл `kvitto.db` в корне проекта, создаётся при первом запуске. Чтобы начать с чистой
базы, остановите сервис и удалите этот файл. Другой путь к базе задаётся переменной
`DATABASE_URL`, например `sqlite:///./other.db`.

Миграций нет: таблицы создаются при старте через `create_all`.

## 4. Локальные тесты и линтер

В активированном виртуальном окружении (см. [раздел 3](#3-локальный-запуск-без-docker)):

```bash
pytest
```

```bash
ruff check . && ruff format --check .
```

Тесты используют in-memory SQLite и не трогают `kvitto.db`. Отдельный файл можно запустить
так: `pytest tests/test_webhooks.py -v`. У каждого теста есть docstring на русском, по нему
удобно искать: `grep -rn "Idempotency-Key" tests/`.

CI (`.github/workflows/ci.yml`) на каждый push запускает ruff и pytest на Python 3.11 и 3.13.

## 5. Ручная проверка API

Сценарий работает одинаково для Docker (`docker compose up --build`, см. [раздел 1](#1-запуск-через-docker))
и локального запуска — сервис должен быть доступен на http://127.0.0.1:8000.
Запросы отправляются с вашей машины, заходить в контейнер не нужно. Самый простой способ — Swagger UI на `/docs`. Ниже то же самое из консоли.

### bash (Linux / macOS / WSL)

```bash
BASE=http://127.0.0.1:8000

# 1. Тарифы
curl -s $BASE/tariffs; echo

# 2. Платёж: standard в рассрочку на 3 месяца с промокодом; запоминаем id
PAYMENT_ID=$(curl -s -X POST $BASE/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "installment", "installment_months": 3, "promo_code": "kvitto10"}' \
  | sed -E 's/.*"id":"([^"]+)".*/\1/')
echo $PAYMENT_ID

# 3. Повтор с тем же Idempotency-Key — код 200 и тот же платёж, дубль не создаётся
curl -s -w "\n%{http_code}\n" -X POST $BASE/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-1" \
  -d '{"tariff_id": 2, "email": "student@example.com", "method": "installment", "installment_months": 3, "promo_code": "kvitto10"}'

# 4. Получить платёж
curl -s $BASE/payments/$PAYMENT_ID; echo

# 5. Банк сообщает об успешной оплате — {"result":"ok"}
curl -s -X POST $BASE/webhooks/bank \
  -H "Content-Type: application/json" \
  -d "{\"payment_id\": \"$PAYMENT_ID\", \"status\": \"succeeded\"}"; echo

# 6. Запрещённый переход succeeded -> failed — 409, статус не меняется
curl -s -w "\n%{http_code}\n" -X POST $BASE/webhooks/bank \
  -H "Content-Type: application/json" \
  -d "{\"payment_id\": \"$PAYMENT_ID\", \"status\": \"failed\"}"

# 7. Список платежей с фильтрами
curl -s "$BASE/payments?email=student@example.com&status=succeeded"; echo

# 8. Несуществующий платёж — 404
curl -s -w "\n%{http_code}\n" $BASE/payments/00000000-0000-0000-0000-000000000000

# 9. Неизвестный промокод — 422
curl -s -w "\n%{http_code}\n" -X POST $BASE/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id": 1, "email": "student@example.com", "method": "card", "promo_code": "WRONG"}'
```

Ответ на шаге 2–4:

```json
{
  "id": "0230f744-76fb-4929-9d1d-4ec39e9b37ca",
  "status": "pending",
  "tariff_id": 2,
  "amount": 1791000,
  "discount": 199000,
  "method": "installment",
  "installment_months": 3,
  "schedule": [597000, 597000, 597000],
  "email": "student@example.com",
  "created_at": "2026-10-07T02:03:49.184477Z"
}
```

### PowerShell (Windows)

В PowerShell `curl.exe` плохо переносит JSON в кавычках, поэтому удобнее `Invoke-RestMethod`:

```powershell
$base = "http://127.0.0.1:8000"

# 1. Тарифы
Invoke-RestMethod "$base/tariffs"

# 2. Платёж в рассрочку с промокодом
$body = @{ tariff_id = 2; email = "student@example.com"; method = "installment"; installment_months = 3; promo_code = "kvitto10" } | ConvertTo-Json
$payment = Invoke-RestMethod "$base/payments" -Method Post -ContentType "application/json" -Headers @{ "Idempotency-Key" = "demo-1" } -Body $body
$payment

# 3. Повтор с тем же ключом — тот же id
(Invoke-RestMethod "$base/payments" -Method Post -ContentType "application/json" -Headers @{ "Idempotency-Key" = "demo-1" } -Body $body).id -eq $payment.id

# 4. Вебхук банка: успешная оплата
$hook = @{ payment_id = $payment.id; status = "succeeded" } | ConvertTo-Json
Invoke-RestMethod "$base/webhooks/bank" -Method Post -ContentType "application/json" -Body $hook

# 5. Список платежей с фильтрами
Invoke-RestMethod "$base/payments?email=student@example.com&status=succeeded"
```

Ошибочные ответы (404, 409, 422) `Invoke-RestMethod` выбрасывает как исключение — их удобнее
смотреть в Swagger UI или через bash-сценарий выше.

## 6. Эндпоинты

| Запрос | Что делает | Коды ответа |
|---|---|---|
| `GET /tariffs` | Список тарифов `[{id, title, price}]` | 200 |
| `POST /payments` | Создать платёж. Тело: `tariff_id`, `email`, `method`, `installment_months` (для рассрочки), `promo_code` (необязательно). Заголовок `Idempotency-Key` необязателен | 201 — создан, 200 — уже есть платёж с этим ключом, 422 — ошибка в теле |
| `GET /payments/{id}` | Получить платёж; `id` — UUID | 200, 404 — платежа с таким UUID нет, 422 — `id` не UUID (например, `/payments/1`) |
| `GET /payments?email=&status=` | Список платежей; оба фильтра необязательны, email без учёта регистра, новые сначала, возвращаются все подходящие (пагинации нет) | 200, 422 — неизвестный статус |
| `POST /webhooks/bank` | Смена статуса от банка. Тело: `payment_id`, `status` | 200 `{"result": "ok"}`, 404, 409 `{"error": "invalid_transition"}`, 422 |

Платёж в ответах: `id` (UUID), `status`, `tariff_id`, `amount`, `discount`, `method`,
`installment_months`, `schedule` (список сумм в копейках или `null`), `email`, `created_at` (UTC).

## 7. Бизнес-правила и принятые решения

- **Деньги** — везде целые копейки (`int`), float не используется.
- **`amount`** — итоговая сумма к оплате, **`discount`** — размер скидки в копейках.
- **Промокод** `KVITTO10` — −10% от цены тарифа, регистр и пробелы по краям не важны.
  Пустая или состоящая из пробелов строка = промокода нет. Неизвестный код — 422.
  Если 10% не делится нацело, скидка округляется вверх (в пользу клиента).
- **Рассрочка**: `installment_months` обязателен для `installment` и допустим только 3, 6 или 12;
  для `card`/`sbp` передавать его нельзя — 422.
- **График** делится в копейках, остаток раздаётся по копейке первым платежам;
  сумма графика всегда ровно равна `amount`.
- **Несуществующий `tariff_id`** — 422 в стандартном формате ошибок FastAPI.
- **id платежа — UUID**, чтобы платежи нельзя было перебрать по порядку. Поэтому
  `GET /payments/1` или `/payments/abc` вернёт **422**, а не 404: FastAPI валидирует тип
  параметра пути, и по заданию ошибки валидации — стандартный 422. 404 возвращается, когда
  `id` — корректный UUID, но такого платежа нет (`/payments/00000000-0000-0000-0000-000000000000`).
  То же для вебхука: `payment_id` не UUID — 422, корректный UUID без платежа — 404.
- **Idempotency-Key**: если платёж с ключом уже есть — возвращается он (200), даже если тело
  запроса отличается. На ключе стоит unique-ограничение, поэтому два параллельных запроса
  тоже не создадут дубль. Пустой или состоящий из пробелов заголовок считается отсутствием
  ключа — иначе все такие запросы схлопнулись бы в один платёж.
- **Статусы**: `pending → succeeded`, `pending → failed`, `succeeded → refunded`.
  Любой другой переход, включая повтор текущего статуса, — 409 `{"error": "invalid_transition"}`.
  Статус меняется условным `UPDATE ... WHERE status = <текущий>`, чтобы параллельные вебхуки
  не обошли проверку.
- **Email** валидируется через Pydantic `EmailStr`; он приводит к нижнему регистру только домен,
  поэтому фильтр по email сравнивает без учёта регистра.

## 8. Структура проекта

```
app/
  main.py            # приложение, создание таблиц и тарифов при старте
  db.py              # движок, сессия, Base
  models.py          # ORM-модели и enum'ы статуса/способа оплаты
  schemas.py         # Pydantic-схемы запросов/ответов и валидация
  services/
    pricing.py       # скидка и график рассрочки (чистые функции)
    payments.py      # создание платежа, идемпотентность, переходы статусов, список
  routers/           # HTTP-слой: tariffs, payments, webhooks
tests/               # pytest: деньги, платежи, список, вебхуки
Dockerfile                 # стадии: base -> tests (тестовый образ) и app (приложение)
docker-compose.yml         # сервис app + сервис tests в профиле tests
requirements.txt           # зависимости приложения (точные версии)
requirements-dev.txt       # + pytest, httpx, ruff
.github/workflows/ci.yml   # ruff + pytest на каждый push
CLAUDE.md                  # правила для ИИ-ассистента
AI_LOG.md                  # как использовался ИИ при разработке
```
