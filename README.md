# Koboki

Koboki is a music-focused social network built with Django templates and PostgreSQL. Users can publish posts with music links, discover and review music, build playlists, follow profiles, comment on posts, and exchange private messages with attachments.

Django applications live in `apps/`; shared project validators live in `apps/core/` and `core/` (the chat app uses the latter). The active Django project configuration is `config.settings`.

## Quick start

Use Python 3.11+ and PostgreSQL 14+. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set a private `SECRET_KEY` and the PostgreSQL connection values in `.env`. Create the database if needed:

```bash
createdb koboki
```

Apply migrations and start the development server:

```bash
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Uploaded images, audio and message attachments are stored under `media/` and are excluded from Git.

## Checks

```bash
python manage.py check
python manage.py test
```

## Git and pull requests

Use branches such as `feature/<task>` and submit changes through a pull request. Include migrations and relevant tests with application changes.

## Access from other devices

For a temporary local network demo, add the computer's LAN hostname or IP to `ALLOWED_HOSTS`, start Django with `python manage.py runserver 0.0.0.0:8000`, and allow port 8000 through the computer's firewall. Other devices open `http://<server-lan-ip>:8000/`. `DB_HOST` can stay `localhost` when PostgreSQL runs on that same computer. If PostgreSQL runs on another machine, set `DB_HOST` to that database server's hostname/IP and configure PostgreSQL and its firewall to accept the app server.

`ALLOWED_HOSTS=*` accepts every Host header and does not make the server reachable by itself. Keep `DEBUG=True` for local development only; use `DEBUG=False`, a real secret key, explicit trusted hosts, and a production server/reverse proxy for a public deployment.
