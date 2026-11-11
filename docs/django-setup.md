# Django setup: accounts and feed (weeks 1-8)

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

## Follows and feed

The accounts app provides `Follow` relationships with unique follower/target
pairs and a database constraint against following yourself. Follow and unfollow
actions are POST-only.

The feed app provides posts with text up to 2,000 characters and optional JPG,
PNG, or WebP images up to 5 MB. A post may also include a track title, artist,
and link to an external music service. The authenticated home page (`/`) shows
posts from all users, with 10 posts per page. Posts can be created at
`/post/new/`, viewed at `/post/<id>/`, and edited or deleted only by their
author.

After updating the code, apply schema changes with:

```sh
python manage.py migrate
```

## Team integration points

- The profile links to `/chat/with/<username>/`. The `chat` app must provide
  that route; it is owned by the chat participant and is not implemented here.
- The post detail template exposes a `comments` block with a placeholder.
  The comments participant can replace it with the comments UI.

## Verification

Run the app checks and account/feed tests with:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run accounts feed
python manage.py test apps.accounts.tests apps.feed.tests
```