# Koboki Social Media

Учебный проект социальной сети на Django с PostgreSQL, серверными шаблонами и приложениями `accounts`, `feed`, `music`, `chat` и `comments`.

## Быстрый запуск

Нужны Python 3.11+ и PostgreSQL 14+. Команды ниже выполняются из корня репозитория.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Создайте базу и пользователя PostgreSQL (или используйте существующие значения в `.env`):

```bash
createdb socnet
```

Затем примените миграции и запустите сервер:

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Демо-пользователи: `demo_alice`, `demo_bob`, `demo_carol`; пароль у всех `demo-password`.

Для локального запуска без PostgreSQL установите `DJANGO_USE_SQLITE=1` в `.env`, затем выполните те же команды. Это предназначено для разработки и тестов; командная база проекта — PostgreSQL.

## Проверки

```bash
python manage.py test
python manage.py check
```

Файлы загруженных вложений сохраняются в `media/` и не должны коммититься. Секреты и параметры подключения хранятся в `.env`; в репозитории находится только `.env.example`.

## Git и pull request

Рабочие ветки имеют формат `feature/<задача>`, `main` защищена, изменения вливаются через pull request и ревью. Перед отправкой проверьте, что бизнес-логика находится в `services.py`/валидаторах, тесты добавлены, а миграции закоммичены.