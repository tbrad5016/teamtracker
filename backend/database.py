# database.py  (TeamTracker.gg, Phase 5)
# ------------------------------------------------------------------
# This file is the ONLY place in the project that talks to PostgreSQL.
# The Flask routes (server.py) just call the functions in here.
#
# Security rules this file follows:
#   * Every query passes user input as parameters (%s / %(name)s). User input is
#     never pasted into the SQL text, which is what stops SQL injection.
#   * No passwords live in the code. The database password comes from the
#     environment (.env file). User passwords are stored only as salted hashes.
# ------------------------------------------------------------------

import hashlib   # password hashing
import hmac      # constant-time comparison of hashes
import os        # random salt + environment variables
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Read the .env file in the project root (it is NOT committed to GitHub).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing {name}. Copy .env.example to .env and fill in a value."
        )
    return value


# Connection settings. The password and port must match docker-compose.yml,
# which reads the same .env file.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),   # IPv4 on purpose: "localhost" can resolve to IPv6 on Windows
    "port": int(os.environ.get("DB_PORT", "5435")),
    "dbname": "teamtracker",
    "user": "teamtracker",
    "password": _required_env("POSTGRES_PASSWORD"),
}

# Fixed rating scale (Phase 1, "Performance Rating Scale").
# KDA = (kills + assists) / max(deaths, 1), using each role's averages.
GOOD_KDA = 3.5       # at or above this  -> Good
AVERAGE_KDA = 2.5    # at or above this  -> Average, below it -> Bad

# Only games inside this window are used (Phase 1/2: the previous six months).
# game_creation is stored in milliseconds since 1970. This constant is fixed
# text, never user input; the number of months is passed as a parameter.
IN_WINDOW = ("m.game_creation >= "
             "(EXTRACT(EPOCH FROM (NOW() - make_interval(months => %(months)s))) * 1000)::bigint")

RANKED_SOLO_QUEUE = 420   # Riot's id for "Ranked Solo/Duo" (see Queue_Types)


# ---------- connection helpers ----------
def query(sql, params=None):
    """Run a SELECT and return a list of dicts (one dict per row)."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE. Returns the number of rows affected."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            count = cur.rowcount
        conn.commit()          # without this the change is thrown away
        return count
    except Exception:
        conn.rollback()        # cancel the half-finished change, then pass the error on
        raise
    finally:
        conn.close()


def get_connection_info():
    """Used on the home page to show the app really is connected to PostgreSQL."""
    return query("SELECT current_database() AS database, "
                 "current_setting('server_version') AS version;")[0]


# ---------- passwords ----------
# New hashes look like:  pbkdf2_sha256$<iterations>$<salt>$<hash>
# Phase 4 hashes (the seed data) look like:  <salt>$<hash>  (100,000 iterations).
# verify_password() understands both. A plain password is never stored.
HASH_ITERATIONS = 600_000
LEGACY_ITERATIONS = 100_000


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, HASH_ITERATIONS)
    return f"pbkdf2_sha256${HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    try:
        parts = stored.split("$")
        if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
            iterations, salt_hex, digest_hex = int(parts[1]), parts[2], parts[3]
        elif len(parts) == 2:
            iterations, salt_hex, digest_hex = LEGACY_ITERATIONS, parts[0], parts[1]
        else:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt_hex), iterations)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# ---------- users: signup, login, password change ----------
def add_user(username, email, password, role="user"):
    # user_id and created_at are filled in by PostgreSQL (SERIAL / DEFAULT).
    # Raises psycopg2.errors.UniqueViolation if the username or email is taken.
    return execute(
        "INSERT INTO Registered_Users (username, email, password_hash, role) "
        "VALUES (%s, %s, %s, %s);",
        (username, email, hash_password(password), role),
    )


def get_user(user_id):
    """The logged-in user's details (never includes the password hash)."""
    rows = query(
        "SELECT user_id, username, email, role FROM Registered_Users WHERE user_id = %s;",
        (user_id,),
    )
    return rows[0] if rows else None


def check_login(username, password):
    """Return the user if the username and password are right, otherwise None."""
    rows = query(
        "SELECT user_id, password_hash FROM Registered_Users WHERE username = %s;",
        (username,),
    )
    if rows and verify_password(password, rows[0]["password_hash"]):
        return get_user(rows[0]["user_id"])
    return None


def change_password(user_id, old_password, new_password):
    """Return True if the old password was right and the new one was saved."""
    rows = query("SELECT password_hash FROM Registered_Users WHERE user_id = %s;", (user_id,))
    if not rows or not verify_password(old_password, rows[0]["password_hash"]):
        return False
    return execute(
        "UPDATE Registered_Users SET password_hash = %s WHERE user_id = %s;",
        (hash_password(new_password), user_id),
    ) == 1


# ---------- admin: list and delete users ----------
def list_users():
    # REPORT: JOIN + GROUP BY. Every account with how many searches it has saved.
    return query("""
        SELECT u.user_id, u.username, u.email, u.role,
               to_char(u.created_at, 'YYYY-MM-DD') AS joined,
               COUNT(s.search_id)                  AS saved_searches
        FROM Registered_Users u
        LEFT JOIN Saved_Searches s ON s.user_id = u.user_id
        GROUP BY u.user_id
        ORDER BY u.role, u.username;
    """)


def delete_user(user_id):
    # ON DELETE CASCADE on Saved_Searches.user_id also removes this user's saved searches.
    return execute("DELETE FROM Registered_Users WHERE user_id = %s;", (user_id,))


# ---------- players: search and profile ----------
def search_players(keyword, limit=50):
    # Search by Riot ID ("name#tagline"). An empty keyword matches every player.
    # % and _ typed by the user are escaped so they are searched literally.
    safe = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return query("""
        SELECT p.riot_id_game_name AS game_name,
               p.riot_id_tagline   AS tagline,
               p.riot_id_game_name || '#' || p.riot_id_tagline AS riot_id,
               r.tier, r.rank_division AS division
        FROM Players p
        LEFT JOIN Player_Ranks r ON r.puuid = p.puuid AND r.queue_id = %s
        WHERE (p.riot_id_game_name || '#' || p.riot_id_tagline) ILIKE %s
        ORDER BY p.riot_id_game_name, p.riot_id_tagline
        LIMIT %s;
    """, (RANKED_SOLO_QUEUE, f"%{safe}%", limit))


def get_player(game_name, tagline):
    rows = query("""
        SELECT puuid,
               riot_id_game_name AS game_name,
               riot_id_tagline   AS tagline,
               riot_id_game_name || '#' || riot_id_tagline AS riot_id
        FROM Players
        WHERE LOWER(riot_id_game_name) = LOWER(%s) AND LOWER(riot_id_tagline) = LOWER(%s)
        LIMIT 1;
    """, (game_name, tagline))
    return rows[0] if rows else None


def get_most_followed(limit=5):
    # REPORT: JOIN + GROUP BY. Which players are saved by the most accounts.
    return query("""
        SELECT p.riot_id_game_name AS game_name,
               p.riot_id_tagline   AS tagline,
               p.riot_id_game_name || '#' || p.riot_id_tagline AS riot_id,
               COUNT(*) AS followers
        FROM Saved_Searches s
        JOIN Players p ON p.puuid = s.puuid
        GROUP BY p.puuid
        ORDER BY followers DESC, p.riot_id_game_name
        LIMIT %s;
    """, (limit,))


def get_ranks(puuid):
    # JOIN: the player's current rank in each ranked queue.
    return query("""
        SELECT r.queue_id, q.description AS queue, r.tier, r.rank_division AS division,
               r.league_points AS lp, r.wins, r.losses,
               ROUND(100.0 * r.wins / NULLIF(r.wins + r.losses, 0), 1)::float AS win_rate_pct
        FROM Player_Ranks r
        JOIN Queue_Types q ON q.queue_id = r.queue_id
        WHERE r.puuid = %s
        ORDER BY q.queue_id;
    """, (puuid,))


def get_win_rate(puuid, category, months, queue_id=None):
    # The player's own games in the chosen queue category and time window.
    # category is 'RANKED', 'CASUAL' or None (= any queue).
    return query(f"""
        SELECT COUNT(*) AS games,
               COALESCE(SUM(CASE WHEN mt.win THEN 1 ELSE 0 END), 0) AS wins,
               ROUND(100.0 * SUM(CASE WHEN mt.win THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1)::float
                   AS win_rate_pct
        FROM Participants pa
        JOIN Match_Teams mt ON mt.match_id = pa.match_id AND mt.team_id = pa.team_id
        JOIN Matches m      ON m.match_id = pa.match_id
        JOIN Queue_Types q  ON q.queue_id = m.queue_id
        WHERE pa.puuid = %(puuid)s
          AND (%(category)s::varchar IS NULL OR q.category = %(category)s)
          AND (%(queue_id)s::int IS NULL OR q.queue_id = %(queue_id)s)
          AND {IN_WINDOW};
    """, {"puuid": puuid, "category": category, "months": months,
          "queue_id": queue_id})[0]


def get_teammate_roles(puuid, category, months, queue_id=None):
    # REPORT (the core TeamTracker query): self-join + subquery + GROUP BY.
    # "me" and "mate" are the same table (Participants): same match, same team,
    # different player. Teammates are grouped by ROLE only, so no teammate is
    # ever named (Phase 1 ethical consideration).
    return query(f"""
        SELECT role, shared_games, avg_kills, avg_deaths, avg_assists, kda,
               CASE WHEN kda >= %(good)s    THEN 'Good'
                    WHEN kda >= %(average)s THEN 'Average'
                    ELSE 'Bad' END AS rating
        FROM (
            SELECT mate.role,
                   COUNT(*)                                   AS shared_games,
                   ROUND(AVG(mate.kills), 1)::float           AS avg_kills,
                   ROUND(AVG(mate.deaths), 1)::float          AS avg_deaths,
                   ROUND(AVG(mate.assists), 1)::float         AS avg_assists,
                   ROUND((AVG(mate.kills) + AVG(mate.assists))
                         / GREATEST(AVG(mate.deaths), 1), 2)::float AS kda
            FROM Participants me
            JOIN Participants mate ON mate.match_id = me.match_id
                                  AND mate.team_id  = me.team_id
                                  AND mate.puuid   <> me.puuid
            JOIN Matches m         ON m.match_id = me.match_id
            JOIN Queue_Types q     ON q.queue_id = m.queue_id
            WHERE me.puuid = %(puuid)s
              AND mate.role IS NOT NULL
              AND (%(category)s::varchar IS NULL OR q.category = %(category)s)
              AND (%(queue_id)s::int IS NULL OR q.queue_id = %(queue_id)s)
              AND {IN_WINDOW}
            GROUP BY mate.role
        ) AS by_role
        ORDER BY array_position(ARRAY['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY'], role::text);
    """, {"puuid": puuid, "category": category, "months": months, "queue_id": queue_id,
          "good": GOOD_KDA, "average": AVERAGE_KDA})


# ---------- saved searches (every one is scoped to the logged-in user) ----------
def get_saved_searches(user_id):
    # JOIN: shows the player's Riot ID instead of a bare puuid.
    return query("""
        SELECT s.search_id,
               p.riot_id_game_name AS game_name,
               p.riot_id_tagline   AS tagline,
               p.riot_id_game_name || '#' || p.riot_id_tagline AS player,
               s.queue_category,
               s.time_period_months,
               COALESCE(s.queue_category, 'ANY')   AS queue,
               COALESCE(s.time_period_months, 6)   AS months,
               to_char(s.created_at, 'YYYY-MM-DD') AS saved_on
        FROM Saved_Searches s
        JOIN Players p ON p.puuid = s.puuid
        WHERE s.user_id = %s
        ORDER BY s.search_id;
    """, (user_id,))


def get_saved_search(search_id, user_id):
    # Returns None if the search does not exist OR belongs to someone else.
    rows = query("""
        SELECT s.search_id,
               p.riot_id_game_name || '#' || p.riot_id_tagline AS player,
               s.queue_category,
               COALESCE(s.time_period_months, 6) AS months
        FROM Saved_Searches s
        JOIN Players p ON p.puuid = s.puuid
        WHERE s.search_id = %s AND s.user_id = %s;
    """, (search_id, user_id))
    return rows[0] if rows else None


def add_saved_search(user_id, puuid, queue_category, months):
    # queue_category may be None, which is stored as NULL (= any queue).
    return execute(
        "INSERT INTO Saved_Searches (user_id, puuid, queue_category, time_period_months) "
        "VALUES (%s, %s, %s, %s);",
        (user_id, puuid, queue_category, months),
    )


def update_saved_search(search_id, user_id, queue_category, months):
    return execute(
        "UPDATE Saved_Searches SET queue_category = %s, time_period_months = %s "
        "WHERE search_id = %s AND user_id = %s;",
        (queue_category, months, search_id, user_id),
    )


def delete_saved_search(search_id, user_id):
    return execute(
        "DELETE FROM Saved_Searches WHERE search_id = %s AND user_id = %s;",
        (search_id, user_id),
    )


# Self-test. Runs ONLY when you type:  python backend/database.py
if __name__ == "__main__":
    print(get_connection_info())
