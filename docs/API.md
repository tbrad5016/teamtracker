# TeamTracker.gg backend API

The front end (plain HTML, CSS and jQuery) talks to the backend with JSON over `/api/...`.
The backend also serves the front-end files themselves, so everything runs from one address:
http://127.0.0.1:5001

Sophia's profile format is in `docs/profile-data-format.md`. `/api/profile` follows it exactly.

## How the files are served

| Folder | Served at | Example |
|---|---|---|
| `frontend/templates/*.html` | `/<name>.html` (and `/` is `home.html`) | `/results.html?search=LunarRaven%237777` |
| `frontend/static/*` | the site root | `/styles.css`, `/script.js`, `/auth.js`, `/img/profilePicImg.PNG` |

So pages link files the normal way: `<link href="styles.css">`, `<script src="script.js">`, `img/x.png`. No Python or template syntax goes in the front-end files. Edit a file, refresh the browser, done.

## Login, the CSRF token, and `auth.js`

* `GET /api/session` tells the page whether somebody is logged in and hands out a CSRF token.
* Every POST, PUT and DELETE must send that token in an `X-CSRF-Token` header. Without it the server answers 400.
* `static/auth.js` does all of this for the pages. Every page includes it after `script.js`:
  `<script src="auth.js"></script>`. It also turns `#login-box` into the logged-in `#account-box`, and wires Log Out.
* Cookies: the login cookie is HttpOnly and SameSite=Lax.

## Endpoints

Errors always look like `{"error": "message"}` with a matching HTTP status. Profile "not found" is `404` with `{"found": false, ...}`.

### Public

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /api/session` | who is logged in + CSRF token | `{loggedIn, username, role, csrfToken}` |
| `GET /api/profile?riotId=Name%23Tag&queue=any&period=6` | player profile | see below |
| `GET /api/search?q=rav` | autocomplete | `{results: ["LunarRaven#7777", ...]}` (max 10) |
| `GET /api/reports/most-followed` | report: most-followed players | `{players: [{riotId, followers}]}` |
| `POST /api/register` | create an account (role `user`) | `{username, email, password, confirmPassword?}` -> 201, 400 (invalid), 409 (taken) |
| `POST /api/login` | log in | `{username, password}` -> 200, 401 |
| `POST /api/logout` | log out | |

`/api/profile` parameters:
* `riotId`: `Name#Tag`, any capitals. Without `#Tag`, a keyword that matches exactly one player also works.
* `queue`: `any`, `solo` (Ranked Solo/Duo), `flex` (Ranked Flex). `ranked` and `casual` also work.
* `period`: months, `1`, `3`, `6` or `12`.

### Logged-in user (401 if not logged in)

| Method and path | Purpose |
|---|---|
| `GET /api/me/searches` | READ my saved searches: `{searches: [{id, riotId, queue, period, savedOn}]}` |
| `POST /api/me/searches` | CREATE: `{riotId, queue, period}` |
| `PUT /api/me/searches/<id>` | UPDATE: `{queue, period}` |
| `DELETE /api/me/searches/<id>` | DELETE |
| `POST /api/me/password` | `{currentPassword, newPassword, confirmPassword?}` |
| `GET /api/me/profile` | My Profile page (see "Open decision") |

A user can only see and change their own saved searches (other people's ids answer 404).
Saved searches store `queue` as `any`, `ranked` or `casual`, and `period` as 1 to 6, because that is what the `Saved_Searches` table allows.

### Admin only (403 for normal users)

| Method and path | Purpose |
|---|---|
| `GET /api/admin/users` | all users with their saved-search counts |
| `POST /api/admin/users` | create a user: `{username, email, password, role}` (`user` or `admin`) |
| `DELETE /api/admin/users/<id>` | delete a user and their saved searches (not yourself) |

The first admin is created from a terminal: `python backend/create_admin.py --username NAME --email EMAIL`.

## Pages built on top of this API (backend side)

| Page | File | What it does |
|---|---|---|
| Register | `register.html` | creates an account, logs the new user in, goes to Account |
| Account | `account.html` | saved searches: list, add, edit, delete; change password |
| Admin | `admin.html` | admins only: list users, create users, delete users |
| "Follow this player" button | added to `results.html` by `auth.js` | saves the current profile as a saved search |

They use Sophia's `styles.css` and `profileCSS.css` plus one extra stylesheet, `forms.css`, and the logic is in `account.js`. She can restyle them freely; keep the ids and `data-page` attribute.
Search suggestions now come from `GET /api/search`, so no player names are hard-coded in the front end.

## Open decisions for the team

1. **My Profile (`list.html`) has no data yet.** A registered account is not linked to a Riot ID anywhere in the schema, so `/api/me/profile` answers 404 and the page shows "couldn't find that profile". To fix it, add one nullable column to `Registered_Users` that points to `Players(puuid)`, plus an endpoint to set it. That is a schema change, so Albert should decide (the ER diagram changes too).
2. **Queue vocabulary.** The profile page filters by Solo/Duo and Flex. Saved searches only store Ranked, Casual or any, so "Follow this player" saves Solo and Flex as Ranked. Decide before the final.
