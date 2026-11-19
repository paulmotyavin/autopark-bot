# autopark-bot

Telegram-бот для управления автопарком (MVP): владелец/администратор/водитель,
аренда, платежи, пробег, ТО, документы. Этот каркас содержит инфраструктуру:
конфиг, БД и миграции, роли и приглашения, S3, прокси, планировщик, деплой.
Доменные таблицы и сценарии добавляются поверх.

## Стек

aiogram 3 · PostgreSQL (SQLAlchemy 2 async + asyncpg + Alembic) · Redis (FSM) ·
S3 (aioboto3) · APScheduler · structlog · uv · Docker Compose · GitHub Actions.

## Локальный запуск

```bash
cp .env.example .env     # BOT_TOKEN, OWNER_TG_ID, S3_*; для локальной БД: DB_HOST=localhost,
                         # DB_SSL_MODE пустой, REDIS_URL=redis://localhost:6379/0
docker compose -f docker-compose.dev.yml up -d    # Postgres и Redis ТОЛЬКО для разработки
uv sync
uv run alembic upgrade head
uv run autopark-bot
```

Проверка перед пушем (то же запускает CI): `uv run ruff check --fix . && uv run pyright`
(`--fix` сам расставит импорты в нужном порядке).

## Как устроен доступ

- Свободной регистрации нет. Первый владелец создаётся из `OWNER_TG_ID` при каждом старте
  (переменная окружения — корень доверия: роль и активность восстанавливаются принудительно).
- Остальных приглашает владелец: `/invite driver` или `/invite admin` → одноразовая ссылка
  `t.me/<bot>?start=<token>` с TTL (`INVITE_TTL_HOURS`). В БД хранится только sha256 токена,
  использование атомарно (`UPDATE ... WHERE used_at IS NULL AND expires_at > now()`).
- Middleware: `Throttling → DbSession → Auth`. Auth читает роль из БД на каждый апдейт
  (без кеша — отзыв доступа мгновенный) и игнорирует всё, кроме личных чатов.
- Роутеры защищены `RoleFilter` на уровне всего роутера роли.
- Правило для всех будущих хендлеров: принадлежность данных проверяется в SQL
  (`WHERE rental.driver_id = :user_id`), а не по значениям из `callback_data`.
- Транзакция одна на апдейт (`DbSessionMiddleware`): не делайте долгих внешних вызовов
  (загрузка в S3 и т.п.) внутри открытой транзакции дольше, чем нужно.

## Прокси и сеть

`TELEGRAM_PROXY` (socks5/http) применяется только к запросам бота к Telegram.
БД, Redis и S3 ходят напрямую. Бот работает через long polling, входящих портов нет.
Прокси держите свой, с авторизацией или allowlist по IP.

## Деплой

GitHub Actions (`.github/workflows/deploy.yml`) на push в `main`:
ruff + pyright → git reset на сервере → `docker compose build` → `alembic upgrade head` →
`docker compose up -d` → проверка, что контейнер жив.

Секреты репозитория: `SERVER_HOST`, `SERVER_USER`, `SERVER_PORT` (по умолчанию 22),
`SERVER_SSH_KEY`, `SERVER_KNOWN_HOSTS` (обязателен), `DEPLOY_PATH`.
На сервере в `DEPLOY_PATH` должен лежать `.env` (в образ он не попадает).

В проде БД облачная: в `.env` указывается её хост и `DB_SSL_MODE=require`. Перед миграцией,
меняющей схему, делайте снапшот БД в консоли провайдера.

Первый деплой вручную:

```bash
docker compose build
docker compose run --rm bot alembic upgrade head
docker compose up -d
```

## Что ещё нужно до боевого запуска

- Бэкапы: включить автоматические бэкапы облачной БД с восстановлением на момент времени
  и один раз проверить восстановление. Для файлов в S3 включить versioning.
- Внешний мониторинг: `HEALTHCHECK_URL` (healthchecks.io или аналог) с алертом на почту.
- Готово: роли и приглашения, машины, водители, аренда (старт и завершение).
  Дальше: начисления и платежи, пробег и ТО, поломки, документы, джобы планировщика.
