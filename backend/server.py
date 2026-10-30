# server.py  (TeamTracker.gg, Phase 5)
# ------------------------------------------------------------------
# The Flask web server. It does two jobs:
#
#   1. Serves the front end exactly as written (plain HTML, CSS, JavaScript):
#        frontend/templates/*.html   ->  /home.html, /results.html, /list.html  (and / = home)
#        frontend/static/*           ->  /styles.css, /script.js, /img/...
#      No Python code is mixed into the front-end files.
#
#   2. Provides a JSON API under /api/... The front-end JavaScript calls it with
#      jQuery ($.ajax) and draws the results. The format is in docs/API.md.
#
#   browser (HTML/CSS/JS)  ->  this file (/api routes)  ->  database.py  ->  PostgreSQL
#
# Run it from the project root with:   python backend/server.py
# Then open:                           http://127.0.0.1:5001
# ------------------------------------------------------------------

import hmac
import os
import re
import secrets
from functools import wraps
from pathlib import Path

import psycopg2
import psycopg2.errors
from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

import database as db   # importing this also loads the .env file

BASE_DIR = Path(__file__).resolve().parent.parent
PAGES_DIR = BASE_DIR / "frontend" / "templates"     # the HTML pages
ASSETS_DIR = BASE_DIR / "frontend" / "static"       # CSS, JavaScript, images

# static_url_path="" serves the assets at the site root, so the front end can link
# them the simple way: <link href="styles.css">, <script src="script.js">, img/logo.png
app = Flask(__name__, static_folder=str(ASSETS_DIR), static_url_path="")

# The secret key signs the login cookie. It comes from .env, never from the code.
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Missing SECRET_KEY. Copy .env.example to .env and fill in a value.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # JavaScript cannot read the login cookie
    SESSION_COOKIE_SAMESITE="Lax",      # the cookie is not sent on cross-site POSTs
    MAX_CONTENT_LENGTH=64 * 1024,       # refuse huge request bodies
    SEND_FILE_MAX_AGE_DEFAULT=0,        # edit an HTML/CSS/JS file, refresh, see the change
)

# ---- front-end filter values  ->  database filters -------------------
# The profile page sends queue = any | solo | flex (ranked / casual also work).
#   value -> (queue category, exact Riot queue id)
QUEUE_FILTERS = {
    "any":    (None, None),
    "solo":   (None, 420),          # Ranked Solo/Duo
    "flex":   (None, 440),          # Ranked Flex
    "ranked": ("RANKED", None),     # solo + flex together
    "casual": ("CASUAL", None),     # normals + ARAM
}
RANK_QUEUE_CODES = {420: "RANKED_SOLO_5x5", 440: "RANKED_FLEX_SR"}    # Riot's own codes
PROFILE_PERIODS = (1, 3, 6, 12)     # months offered by the profile page
SAVED_QUEUES = ("any", "ranked", "casual")      # what Saved_Searches can store

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,100}@[^@\s]{1,150}\.[^@\s]{2,}$")


# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------
def api_error(message, status):
    return jsonify({"error": message}), status


def body():
    """The request data, whether the browser sent JSON or a normal form."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else request.form


def text(name, source=None):
    """A text field from the request body ('' if missing or not text)."""
    value = (source if source is not None else body()).get(name, "")
    return value.strip() if isinstance(value, str) else ""


def raw_text(name):
    """Like text() but keeps spaces (passwords)."""
    value = body().get(name, "")
    return value if isinstance(value, str) else ""


def whole_number(value, allowed):
    """int(value) if it is in `allowed`, otherwise None."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number in allowed else None


def check_new_password(password, confirm):
    """Return an error message, or None if the new password is fine."""
    if len(password) < 8:
        return "The password must be at least 8 characters."
    if len(password) > 128:
        return "The password must be 128 characters or fewer."
    if password != confirm:
        return "The two passwords do not match."
    return None


def check_new_account(username, email, password, confirm):
    """Shared by sign-up and the admin 'create user' call. Returns an error or None."""
    if not USERNAME_RE.match(username):
        return "Username must be 3-30 characters: letters, numbers, dots and underscores only."
    if not EMAIL_RE.match(email) or len(email) > 255:
        return "Please enter a valid email address."
    return check_new_password(password, confirm)


def find_player(riot_id):
    """'LunarRaven#7777' (any capitals) -> player row, or None.
    Without a '#tag', a keyword that matches exactly one player also works."""
    riot_id = (riot_id or "").strip()[:60]
    if not riot_id:
        return None
    if "#" in riot_id:
        game_name, tagline = riot_id.rsplit("#", 1)
        return db.get_player(game_name.strip(), tagline.strip())
    matches = db.search_players(riot_id, limit=2)
    if len(matches) == 1:
        return db.get_player(matches[0]["game_name"], matches[0]["tagline"])
    return None


# ------------------------------------------------------------------
# Login state, CSRF protection, and role checks
# ------------------------------------------------------------------
@app.before_request
def load_current_user():
    """Look up who is logged in on every API request (so a deleted user is logged out)."""
    g.user = None
    if not request.path.startswith("/api/"):
        return
    user_id = session.get("user_id")
    if user_id is not None:
        g.user = db.get_user(user_id)
        if g.user is None:
            session.clear()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    """Every request that changes data must carry the CSRF token (header X-CSRF-Token).
    The front end gets the token from GET /api/session. This stops other websites
    from making a logged-in browser change data."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = (request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or "").encode()
        expected = session.get("csrf", "").encode()
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, "Security token missing or expired. Reload the page and try again.")


@app.after_request
def no_cache_for_api(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return api_error("Please log in first.", 401)
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            return api_error("Only administrators can do this.", 403)
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------
# The front-end files
# ------------------------------------------------------------------
@app.get("/")
def front_page():
    return send_from_directory(PAGES_DIR, "home.html")


@app.get("/<name>.html")
def html_page(name):
    return send_from_directory(PAGES_DIR, f"{name}.html")


# ------------------------------------------------------------------
# API: who am I?  sign up, log in, log out
# ------------------------------------------------------------------
@app.get("/api/session")
def api_session():
    """Tells the page whether someone is logged in, and hands out the CSRF token."""
    user = g.user
    return jsonify({
        "loggedIn": user is not None,
        "username": user["username"] if user else None,
        "role": user["role"] if user else None,
        "csrfToken": csrf_token(),
    })


@app.post("/api/register")
def api_register():
    username, email, password = text("username"), text("email"), raw_text("password")
    confirm = raw_text("confirmPassword") or password        # confirmation is optional here
    error = check_new_account(username, email, password, confirm)
    if error:
        return api_error(error, 400)
    try:
        db.add_user(username, email, password)               # sign-up is always the 'user' role
    except psycopg2.errors.UniqueViolation:
        return api_error("That username or email is already registered.", 409)
    return jsonify({"ok": True, "username": username}), 201


@app.post("/api/login")
def api_login():
    user = db.check_login(text("username"), raw_text("password"))
    if not user:
        # Same message for "no such user" and "wrong password" on purpose.
        return api_error("Wrong username or password.", 401)
    session.clear()                       # new session on login (stops session fixation)
    session["user_id"] = user["user_id"]
    return jsonify({"ok": True, "username": user["username"], "role": user["role"],
                    "csrfToken": csrf_token()})


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})


# ------------------------------------------------------------------
# API: player profiles (public) and search
# ------------------------------------------------------------------
def build_profile(player):
    """The JSON the profile page draws (format: docs/API.md)."""
    queue_key = (request.args.get("queue") or "any").lower()
    category, queue_id = QUEUE_FILTERS.get(queue_key, QUEUE_FILTERS["any"])
    months = whole_number(request.args.get("period"), PROFILE_PERIODS) or 6
    puuid = player["puuid"]

    stats = db.get_win_rate(puuid, category, months, queue_id)
    return {
        "riotId": player["riot_id"],
        "ranks": [
            {"queue": RANK_QUEUE_CODES.get(r["queue_id"], r["queue"]),
             "rank": f"{r['tier'].capitalize()} {r['division']}",
             "lp": r["lp"], "wins": r["wins"], "losses": r["losses"]}
            for r in db.get_ranks(puuid)
        ],
        "summary": {"games": stats["games"], "wins": stats["wins"]},
        "roles": [
            {"role": r["role"], "games": r["shared_games"],
             "avgKills": r["avg_kills"], "avgDeaths": r["avg_deaths"],
             "avgAssists": r["avg_assists"], "kda": r["kda"]}
            for r in db.get_teammate_roles(puuid, category, months, queue_id)
        ],
    }


@app.get("/api/profile")
def api_profile():
    if not request.args.get("riotId", "").strip():
        return api_error("Type a Riot ID, like Name#1234.", 400)
    player = find_player(request.args.get("riotId"))
    if player is None:
        return jsonify({"found": False, "error": "We could not find that player."}), 404
    return jsonify(build_profile(player))


@app.get("/api/me/profile")
@login_required
def api_my_profile():
    # Registered_Users is not linked to a Riot account yet (no column for it in the
    # schema), so there is no player to show. See docs/API.md, "Open decision".
    return jsonify({"found": False,
                    "error": "This account is not linked to a Riot ID yet."}), 404


@app.get("/api/search")
def api_search():
    """Autocomplete: Riot IDs that contain what was typed (max 10)."""
    keyword = request.args.get("q", "").strip()[:50]
    if not keyword:
        return jsonify({"results": []})
    return jsonify({"results": [p["riot_id"] for p in db.search_players(keyword, limit=10)]})


@app.get("/api/reports/most-followed")
def api_most_followed():
    return jsonify({"players": [{"riotId": p["riot_id"], "followers": p["followers"]}
                                for p in db.get_most_followed()]})


# ------------------------------------------------------------------
# API: the logged-in user's own data (saved searches CRUD + password)
# ------------------------------------------------------------------
def saved_search_json(row):
    return {"id": row["search_id"], "riotId": row["player"], "queue": row["queue"].lower(),
            "period": row["months"], "savedOn": row["saved_on"]}


def read_search_filters():
    """(queue_category, months) from the request body, or an error message."""
    queue = (text("queue") or "any").lower()
    if queue not in SAVED_QUEUES:
        return None, None, "queue must be any, ranked or casual."
    months = whole_number(body().get("period", 6), range(1, 7))
    if months is None:
        return None, None, "period must be a whole number from 1 to 6."
    return (None if queue == "any" else queue.upper()), months, None


@app.get("/api/me/searches")                                                   # READ
@login_required
def api_list_searches():
    return jsonify({"searches": [saved_search_json(r)
                                 for r in db.get_saved_searches(g.user["user_id"])]})


@app.post("/api/me/searches")                                                  # CREATE
@login_required
def api_add_search():
    player = find_player(text("riotId"))
    if player is None:
        return api_error("We could not find that player.", 404)
    category, months, error = read_search_filters()
    if error:
        return api_error(error, 400)
    db.add_saved_search(g.user["user_id"], player["puuid"], category, months)
    return jsonify({"ok": True}), 201


@app.put("/api/me/searches/<int:search_id>")                                   # UPDATE
@login_required
def api_update_search(search_id):
    # get_saved_search() only finds searches that belong to the logged-in user.
    if db.get_saved_search(search_id, g.user["user_id"]) is None:
        return api_error("We could not find that saved search.", 404)
    category, months, error = read_search_filters()
    if error:
        return api_error(error, 400)
    db.update_saved_search(search_id, g.user["user_id"], category, months)
    return jsonify({"ok": True})


@app.delete("/api/me/searches/<int:search_id>")                                # DELETE
@login_required
def api_delete_search(search_id):
    if db.get_saved_search(search_id, g.user["user_id"]) is None:
        return api_error("We could not find that saved search.", 404)
    db.delete_saved_search(search_id, g.user["user_id"])
    return jsonify({"ok": True})


@app.post("/api/me/password")
@login_required
def api_change_password():
    new_password = raw_text("newPassword")
    error = check_new_password(new_password, raw_text("confirmPassword") or new_password)
    if error:
        return api_error(error, 400)
    if not db.change_password(g.user["user_id"], raw_text("currentPassword"), new_password):
        return api_error("Your current password is incorrect.", 400)
    return jsonify({"ok": True})


# ------------------------------------------------------------------
# API: admin only. Create users, see all users, delete users
# ------------------------------------------------------------------
@app.get("/api/admin/users")
@admin_required
def api_admin_list_users():
    return jsonify({"users": [
        {"id": u["user_id"], "username": u["username"], "email": u["email"], "role": u["role"],
         "joined": u["joined"], "savedSearches": u["saved_searches"]}
        for u in db.list_users()
    ]})


@app.post("/api/admin/users")
@admin_required
def api_admin_create_user():
    username, email, password = text("username"), text("email"), raw_text("password")
    role = text("role") or "user"
    if role not in ("user", "admin"):
        return api_error("Role must be user or admin.", 400)
    error = check_new_account(username, email, password, raw_text("confirmPassword") or password)
    if error:
        return api_error(error, 400)
    try:
        db.add_user(username, email, password, role)
    except psycopg2.errors.UniqueViolation:
        return api_error("That username or email is already registered.", 409)
    return jsonify({"ok": True, "username": username, "role": role}), 201


@app.delete("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_delete_user(user_id):
    target = db.get_user(user_id)
    if target is None:
        return api_error("We could not find that account.", 404)
    if target["user_id"] == g.user["user_id"]:
        return api_error("You cannot delete the account you are logged in with.", 400)
    removed = len(db.get_saved_searches(user_id))       # these go too (ON DELETE CASCADE)
    db.delete_user(user_id)
    return jsonify({"ok": True, "deletedSearches": removed})


# ------------------------------------------------------------------
# Errors: the API always answers in JSON, never with a stack trace
# ------------------------------------------------------------------
def error_response(code, message):
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), code
    return f"{code}: {message}\n", code, {"Content-Type": "text/plain; charset=utf-8"}


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return error_response(error.code, error.description)


@app.errorhandler(psycopg2.OperationalError)
def handle_database_down(error):
    # Python could not reach PostgreSQL at all (Docker stopped, wrong port...).
    return error_response(503, "We cannot reach the database right now. "
                               "If you run this project: is Docker running? Try: docker compose up -d")


@app.errorhandler(psycopg2.Error)
def handle_database_error(error):
    return error_response(500, "The database could not complete that request. Nothing was changed.")


if __name__ == "__main__":
    # debug=True restarts the server when you save a Python file. Never use it on a public server.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=True)
