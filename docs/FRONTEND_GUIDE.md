# Front-end guide (for Sophia): how your HTML and CSS plug into the backend

You do not need to write any Python. The backend is a Flask app. Flask reads an HTML file from `frontend/templates/`, fills in the data, and sends it to the browser. A template is just normal HTML with a few `{{ ... }}` holes for data.

```
frontend/
  templates/     <- HTML pages (Flask only looks here)
  static/        <- CSS, images, JavaScript, fonts (served at /static/...)
```

The pages in this repo are plain placeholders so the site works today. Replace them with your design.

## How to work

1. Follow `docs/SETUP.md` once, then run `python backend/server.py`.
2. Edit a file in `frontend/templates/` or `frontend/static/`, save, and refresh the browser. HTML and CSS changes show up without restarting.
3. Never hard-code player data into an HTML file. Use the `{{ variable }}` names listed below so the real database data shows up.

## Linking CSS, images and JavaScript

Do not write `href="style.css"`. Use `url_for`, which finds the right path:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
<img src="{{ url_for('static', filename='logo.png') }}" alt="TeamTracker">
<script src="{{ url_for('static', filename='app.js') }}"></script>
```

Put your files in `frontend/static/`. Subfolders are fine (`filename='img/logo.png'`).

## The layout file (`base.html`)

`base.html` holds the header, the navigation, the flash messages and the footer. Every other page starts with `{% extends "base.html" %}` and fills the `content` block:

```html
{% extends "base.html" %}
{% block title %}Page name - TeamTracker.gg{% endblock %}
{% block content %}
  ...your page...
{% endblock %}
```

If your design already has its own full-page HTML, you can ignore `extends` and keep the whole page in one file. In that case copy the three pieces listed under "Must keep" below into your file.

## Must keep (the site breaks without these)

**1. A hidden CSRF field inside every `<form method="post">`.** This blocks forged form submissions. Without it the server answers "400, form has expired".

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

**2. Log out must be a POST form, not a link.**

```html
<form method="post" action="{{ url_for('logout') }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit">Log out</button>
</form>
```
You can style the button to look like a link (see `.linklike` in `style.css`).

**3. Flash messages.** Success and error messages ("Wrong username or password", "Account created") come from the server. Keep this loop somewhere visible:

```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div class="flash flash-{{ category }}">{{ message }}</div>
  {% endfor %}
{% endwith %}
```
`category` is `success`, `error` or `info`.

Also keep every form field's `name="..."` exactly as listed below, because the server reads fields by name. Change the labels, classes, layout and order freely.

## Variables available in every template

| Name | What it is |
|---|---|
| `current_user` | `None` when logged out. Otherwise has `.user_id`, `.username`, `.email`, `.role` (`user` or `admin`) |
| `csrf_token()` | prints the hidden token value |
| `queue_choices` | `{"": "Any queue", "RANKED": "Ranked", "CASUAL": "Casual"}` |
| `month_choices` | `{1: "1 month", 2: ..., 6: "6 months"}` |

Use `{% if current_user %}` to show different things to logged-in visitors, and `{% if current_user and current_user.role == 'admin' %}` for admin-only items.

## Page by page

Template files and routes. If you name your file differently, either rename it to match or tell Brad to change the one `render_template("...")` line in `backend/server.py`.

### Home / search: `home.html`, route `/`
Search form: `GET`, field `q`, action `{{ url_for('home') }}`.

| Variable | Contents |
|---|---|
| `q` | what was typed |
| `players` | list of players. Each: `game_name`, `tagline`, `riot_id` (like `LunarRaven#7777`), `tier`, `division` (`tier` is empty when unranked) |
| `top_followed` | list for the "most followed" report. Each: `game_name`, `tagline`, `riot_id`, `followers` |
| `db_info` | `.version`, `.database` (small status line, optional) |

Link to a profile with `{{ url_for('player', game_name=p.game_name, tagline=p.tagline) }}`.

### Player profile: `player.html`, route `/player/<game_name>/<tagline>`
This is the page that shows the database data. Filter form: `GET`, fields `queue` and `months`.

| Variable | Contents |
|---|---|
| `player` | `.game_name`, `.tagline`, `.riot_id` |
| `ranks` | list. Each: `queue`, `tier`, `division`, `lp`, `wins`, `losses`, `win_rate_pct` |
| `stats` | `.games`, `.wins`, `.win_rate_pct` (can be `None` when there are no games) |
| `roles` | teammate averages, one row per role. Each: `role`, `shared_games`, `avg_kills`, `avg_deaths`, `avg_assists`, `kda`, `rating` (`Good`, `Average` or `Bad`) |
| `selected_queue`, `selected_months` | current filter values, for pre-selecting dropdowns |
| `good_kda`, `average_kda` | thresholds, for the legend text |

Rating colors: the placeholder CSS uses classes `rating-good`, `rating-average`, `rating-bad` (from `{{ r.rating|lower }}`).

"Follow this player" form (logged-in only): `POST` to `{{ url_for('save_search', game_name=player.game_name, tagline=player.tagline) }}` with fields `queue`, `months` and the CSRF field.

Privacy rule from our project: we show teammates only as role averages, never as named players. Keep it that way.

### Log in: `login.html`, route `/login`
`POST` to `{{ url_for('login') }}`. Fields: `username`, `password`, hidden `next` (`value="{{ next }}"`), CSRF. The variable `form` holds the previously typed values (use `{{ form.get('username', '') }}`).

### Sign up: `signup.html`, route `/signup`
`POST` to `{{ url_for('signup') }}`. Fields: `username`, `email`, `password`, `confirm_password`, CSRF.

### My account: `account.html`, route `/account` (login required)
`searches` is a list of saved searches. Each: `search_id`, `player`, `game_name`, `tagline`, `queue_category` (`RANKED`, `CASUAL` or `None`), `months`, `saved_on`.
* Edit link: `{{ url_for('edit_search', search_id=s.search_id) }}`
* Delete link: `{{ url_for('delete_search', search_id=s.search_id) }}`
* Change password form: `POST` to `{{ url_for('change_password') }}`. Fields: `current_password`, `new_password`, `confirm_password`, CSRF.

### Other pages
| File | Route | Notes |
|---|---|---|
| `search_edit.html` | `/searches/<id>/edit` | variable `search`. Form fields `queue`, `months`, CSRF |
| `confirm.html` | any "are you sure?" delete | variables `title`, `message`, `action`, `cancel_url`, `button`. Form is `POST` to `{{ action }}` with CSRF |
| `admin_users.html` | `/admin/users` (admins only) | variables `users`, `form`. Create-user form fields: `username`, `email`, `role`, `password`, `confirm_password`, CSRF |
| `error.html` | 404, 403, 500... | variables `code`, `title`, `message` |

## Who can see what

* Anyone: home, search, player profiles, sign up, log in.
* Logged in: save a search, My account (edit and delete their own searches, change password).
* Admin: the Admin page (list users, create users, delete users).

If a visitor opens a page they may not use, the server redirects them to the login page or shows the 403 error page. You do not need to hide anything yourself for security, but hiding links they cannot use is good design.

## Quick Jinja cheat sheet

```
{{ value }}                        print a value (HTML is escaped automatically)
{{ value|capitalize }}             filter: Gold -> Gold, gold -> Gold
{% if x %} ... {% else %} ... {% endif %}
{% for p in players %} ... {% endfor %}
{{ url_for('player', game_name='A', tagline='1') }}   build a link
{# this is a comment #}
```

## Bringing your own files in

1. Drop your CSS, images and JS into `frontend/static/`.
2. Open the matching file in `frontend/templates/` and replace the HTML, keeping the must-keep items and field names above.
3. Run the site and click through every page. If something shows `None` or is blank, the variable name is probably misspelled.
4. Commit and push. Tell Brad if you needed a new piece of data on a page. It is one small change in `backend/server.py`.
