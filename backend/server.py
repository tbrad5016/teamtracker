# server.py  (TeamTracker.gg, Phase 5)
# ------------------------------------------------------------------
# The Flask web server. It connects the three layers:
#
#   browser  ->  frontend/templates (HTML) + frontend/static (CSS)
#            ->  this file (routes: decide which page to show, check who is logged in)
#            ->  database.py (the only code that runs SQL)
#            ->  PostgreSQL
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
from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.exceptions import HTTPException

import database as db   # importing this also loads the .env file

BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend" / "templates"),   # HTML pages
    static_folder=str(BASE_DIR / "frontend" / "static"),        # CSS, images, JS
)

# The secret key signs the login cookie. It comes from .env, never from the code.
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Missing SECRET_KEY. Copy .env.example to .env and fill in a value.")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # JavaScript cannot read the login cookie
    SESSION_COOKIE_SAMESITE="Lax",      # the cookie is not sent on cross-site POSTs
    MAX_CONTENT_LENGTH=64 * 1024,       # refuse huge form submissions
    TEMPLATES_AUTO_RELOAD=True,         # edit an HTML file, refresh the browser
)

# Drop-down choices. Keys are what the form sends; values are what the user reads.
QUEUE_CHOICES = {"": "Any queue", "RANKED": "Ranked", "CASUAL": "Casual"}
MONTH_CHOICES = {m: f"{m} month" if m == 1 else f"{m} months" for m in range(1, 7)}

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,100}@[^@\s]{1,150}\.[^@\s]{2,}$")


# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------
def parse_queue(value):
    """'RANKED' / 'CASUAL' stay as they are; anything else means 'any queue' (None)."""
    value = (value or "").upper()
    return value if value in ("RANKED", "CASUAL") else None


def parse_months(value, default=6):
    try:
        months = int(value)
    except (TypeError, ValueError):
        return default
    return months if 1 <= months <= 6 else default


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
    """Shared by signup and the admin 'create user' form. Returns an error or None."""
    if not USERNAME_RE.match(username):
        return "Username must be 3-30 characters: letters, numbers, dots and underscores only."
    if not EMAIL_RE.match(email) or len(email) > 255:
        return "Please enter a valid email address."
    return check_new_password(password, confirm)


def safe_next(target):
    """Only allow redirects to pages on this site (stops open-redirect tricks)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("home")


# ------------------------------------------------------------------
# Login state, CSRF protection, and role checks
# ------------------------------------------------------------------
@app.before_request
def load_current_user():
    """Look up who is logged in on every request (so a deleted user is logged out)."""
    g.user = None
    if request.endpoint == "static":
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
    """Every POST form must carry the hidden csrf_token field, or it is rejected."""
    if request.method == "POST":
        sent = request.form.get("csrf_token", "").encode()
        expected = session.get("csrf", "").encode()
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, "This form has expired. Go back, refresh the page and try again.")


@app.context_processor
def inject_template_variables():
    """Names every template can use without being passed them."""
    return {
        "csrf_token": csrf_token,
        "current_user": g.get("user"),
        "queue_choices": QUEUE_CHOICES,
        "month_choices": MONTH_CHOICES,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "info")
            if request.method == "GET":
                return redirect(url_for("login", next=request.path))
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403, "Only administrators can open this page.")
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------
# Public pages: home (search) and player profile
# ------------------------------------------------------------------
@app.route("/")
def home():
    keyword = request.args.get("q", "").strip()[:50]
    return render_template(
        "home.html",
        q=keyword,
        players=db.search_players(keyword),
        top_followed=db.get_most_followed(),
        db_info=db.get_connection_info(),
    )


@app.route("/player/<game_name>/<tagline>")
def player(game_name, tagline):
    found = db.get_player(game_name, tagline)
    if found is None:
        abort(404, "We could not find that player.")
    category = parse_queue(request.args.get("queue"))
    months = parse_months(request.args.get("months"))
    return render_template(
        "player.html",
        player=found,
        ranks=db.get_ranks(found["puuid"]),
        stats=db.get_win_rate(found["puuid"], category, months),
        roles=db.get_teammate_roles(found["puuid"], category, months),
        selected_queue=category or "",
        selected_months=months,
        good_kda=db.GOOD_KDA,
        average_kda=db.AVERAGE_KDA,
    )


# ------------------------------------------------------------------
# Signup, login, logout
# ------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        error = check_new_account(username, email, password, request.form.get("confirm_password", ""))
        if error:
            flash(error, "error")
        else:
            try:
                db.add_user(username, email, password)       # signup is always the 'user' role
            except psycopg2.errors.UniqueViolation:
                flash("That username or email is already registered.", "error")
            else:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login"))
    return render_template("signup.html", form=request.form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))
    if request.method == "POST":
        user = db.check_login(request.form.get("username", "").strip(),
                              request.form.get("password", ""))
        if user:
            target = safe_next(request.form.get("next"))
            session.clear()                       # new session on login
            session["user_id"] = user["user_id"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(target)
        # Same message for "no such user" and "wrong password" on purpose.
        flash("Wrong username or password.", "error")
    return render_template("login.html", form=request.form,
                           next=request.args.get("next") or request.form.get("next", ""))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ------------------------------------------------------------------
# My account: saved searches (create / read / update / delete) + password change
# ------------------------------------------------------------------
@app.route("/account")
@login_required
def account():
    return render_template("account.html", searches=db.get_saved_searches(g.user["user_id"]))


@app.route("/account/password", methods=["POST"])
@login_required
def change_password():
    new_password = request.form.get("new_password", "")
    error = check_new_password(new_password, request.form.get("confirm_password", ""))
    if error:
        flash(error, "error")
    elif not db.change_password(g.user["user_id"],
                                request.form.get("current_password", ""), new_password):
        flash("Your current password is incorrect.", "error")
    else:
        flash("Your password was changed.", "success")
    return redirect(url_for("account"))


@app.route("/player/<game_name>/<tagline>/save", methods=["POST"])           # CREATE
@login_required
def save_search(game_name, tagline):
    found = db.get_player(game_name, tagline)
    if found is None:
        abort(404, "We could not find that player.")
    db.add_saved_search(g.user["user_id"], found["puuid"],
                        parse_queue(request.form.get("queue")),
                        parse_months(request.form.get("months")))
    flash(f"Saved a search for {found['riot_id']}.", "success")
    return redirect(url_for("account"))


@app.route("/searches/<int:search_id>/edit", methods=["GET", "POST"])        # UPDATE
@login_required
def edit_search(search_id):
    # get_saved_search() only finds searches that belong to the logged-in user.
    saved = db.get_saved_search(search_id, g.user["user_id"])
    if saved is None:
        abort(404, "We could not find that saved search.")
    if request.method == "POST":
        db.update_saved_search(search_id, g.user["user_id"],
                               parse_queue(request.form.get("queue")),
                               parse_months(request.form.get("months")))
        flash(f"Updated your saved search for {saved['player']}.", "success")
        return redirect(url_for("account"))
    return render_template("search_edit.html", search=saved)


@app.route("/searches/<int:search_id>/delete", methods=["GET", "POST"])      # DELETE
@login_required
def delete_search(search_id):
    saved = db.get_saved_search(search_id, g.user["user_id"])
    if saved is None:
        abort(404, "We could not find that saved search.")
    if request.method == "POST":
        db.delete_saved_search(search_id, g.user["user_id"])
        flash(f"Deleted your saved search for {saved['player']}.", "success")
        return redirect(url_for("account"))
    return render_template(
        "confirm.html",
        title="Delete saved search",
        message=f"Delete your saved search for {saved['player']}?",
        action=url_for("delete_search", search_id=search_id),
        cancel_url=url_for("account"),
        button="Yes, delete it",
    )


# ------------------------------------------------------------------
# Admin: create users, see all users, delete users
# ------------------------------------------------------------------
@app.route("/admin/users", methods=["GET", "POST"])
@admin_required
def admin_users():
    if request.method == "POST":                                             # CREATE
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        error = check_new_account(username, email, password, request.form.get("confirm_password", ""))
        if role not in ("user", "admin"):
            error = "Role must be user or admin."
        if error:
            flash(error, "error")
        else:
            try:
                db.add_user(username, email, password, role)
            except psycopg2.errors.UniqueViolation:
                flash("That username or email is already registered.", "error")
            else:
                flash(f"Created the {role} account '{username}'.", "success")
                return redirect(url_for("admin_users"))
    return render_template("admin_users.html", users=db.list_users(), form=request.form)


@app.route("/admin/users/<int:user_id>/delete", methods=["GET", "POST"])     # DELETE
@admin_required
def admin_delete_user(user_id):
    target = db.get_user(user_id)
    if target is None:
        abort(404, "We could not find that account.")
    if target["user_id"] == g.user["user_id"]:
        flash("You cannot delete the account you are logged in with.", "error")
        return redirect(url_for("admin_users"))
    if request.method == "POST":
        db.delete_user(user_id)
        flash(f"Deleted the account '{target['username']}' and its saved searches.", "success")
        return redirect(url_for("admin_users"))
    count = len(db.get_saved_searches(user_id))
    return render_template(
        "confirm.html",
        title="Delete account",
        message=f"Delete the account '{target['username']}'? "
                f"This also deletes its {count} saved search(es).",
        action=url_for("admin_delete_user", user_id=user_id),
        cancel_url=url_for("admin_users"),
        button="Yes, delete the account",
    )


# ------------------------------------------------------------------
# Friendly error pages (users never see a raw stack trace)
# ------------------------------------------------------------------
def show_error(code, title, message):
    return render_template("error.html", code=code, title=title, message=message), code


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return show_error(error.code, error.name, error.description)


@app.errorhandler(psycopg2.OperationalError)
def handle_database_down(error):
    # Python could not reach PostgreSQL at all (Docker stopped, wrong port...).
    return show_error(503, "Database unavailable",
                      "We cannot reach the database right now. "
                      "If you run this project: is Docker running? Try: docker compose up -d")


@app.errorhandler(psycopg2.Error)
def handle_database_error(error):
    return show_error(500, "Something went wrong",
                      "The database could not complete that request. Nothing was changed.")


if __name__ == "__main__":
    # Development server: bound to this computer only. Port 5001 because macOS
    # uses port 5000 for AirPlay.
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5001")), debug=True)
