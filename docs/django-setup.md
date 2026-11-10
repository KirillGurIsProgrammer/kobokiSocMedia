# Django setup: accounts (weeks 1-2)

## Environment

Copy `.env.example` to `.env` and set a unique `SECRET_KEY` and the credentials
for your local PostgreSQL database. The example uses `socnet_local`; change
`DB_NAME` to a personal database name if needed.

Install the project dependencies with `uv sync` or
`pip install -r requirements.txt`. PostgreSQL must be running and the
configured database must already exist.

## Custom user model

`AUTH_USER_MODEL` is set to `accounts.User`. This model must be present in the
first migration; do not migrate the built-in user model first. Create and apply
the initial migrations with:

```sh
python manage.py makemigrations accounts
python manage.py migrate
```

## Account routes

- `/accounts/register/` creates an account and signs the user in.
- `/accounts/login/` and `/accounts/logout/` provide Django session
  authentication; logout is submitted as a CSRF-protected POST.
- `/u/<username>/` displays a profile.
- `/u/<username>/edit/` lets only that user update their bio and avatar.

Avatars accept JPG, PNG, or WebP images up to 5 MB and are stored under
`MEDIA_ROOT` (the local `media/` directory).