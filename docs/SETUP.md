# TeamTracker.gg: setup and run guide

Do this once on a fresh clone. It works the same for everyone on the team.

## 1. Install these first

| Tool | Why | Check it works |
|---|---|---|
| Git | clone the repo | `git --version` |
| Python 3.10 or newer | runs Flask | `python --version` (Windows) or `python3 --version` (Mac) |
| Docker Desktop | runs PostgreSQL | `docker --version` (open Docker Desktop and wait until it says "running") |

## 2. Clone the repo

```
git clone https://github.com/tbrad5016/teamtracker.git
cd teamtracker
```

## 3. Create your private `.env` file

The `.env` file holds the database password and the Flask secret key. It is listed in `.gitignore`, so it never goes to GitHub. Every teammate makes their own.

Windows PowerShell:
```
Copy-Item .env.example .env
```
Mac / Linux:
```
cp .env.example .env
```

Open `.env` in any editor and change two lines:

```
POSTGRES_PASSWORD=pick_a_password_with_letters_and_numbers_only
SECRET_KEY=paste_a_long_random_string_here
DB_PORT=5435
```

To generate a SECRET_KEY, run this and paste the output:
```
python -c "import secrets; print(secrets.token_hex(32))"
```
(On a Mac use `python3`.)

## 4. Start the database (Docker)

```
docker compose down -v
docker compose up -d
```

* `down -v` wipes any old database volume. Run it whenever `db/schema.sql` or `db/seed.sql` changes, because Docker only runs those files the first time a database is created.
* The first start loads `db/schema.sql` and then `db/seed.sql` (30 players, 20 users, 60 matches, and so on).
* Check that it is up with `docker compose ps`. The status should say "running".
* If you change the password in `.env` later, run `docker compose down -v` again, because the password is stored in the database volume.

## 5. Install the Python packages

Create a virtual environment so the packages stay inside the project folder.

Windows PowerShell:
```
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If PowerShell refuses to run the activate script, run `Set-ExecutionPolicy -Scope Process RemoteSigned` once and try again.

Mac / Linux:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You should see `(venv)` at the start of your prompt. Next time you only need the activate line, not the install.

## 6. Test the database connection

```
python backend/database.py
```
It should print the database name and the PostgreSQL version. If it prints an error, see Troubleshooting below.

## 7. Create the first admin account

```
python backend/create_admin.py --username YOUR_NAME --email you@example.com
```
It asks for a password twice. Typing is hidden. The password is hashed before it is stored. It is never written to any file.

Normal visitors sign up themselves on the `/signup` page and get the role `user`. Only an admin can create other admins.

## 8. Run the website

```
python backend/server.py
```
Open http://127.0.0.1:5001 in your browser. Stop the server with Ctrl+C.

Flask runs in debug mode, so when you save a Python file the server restarts itself, and when you save an HTML or CSS file you just refresh the browser. If CSS changes do not show up, do a hard refresh (Ctrl+Shift+R on Windows, Cmd+Shift+R on Mac).

## 9. What to click through (also your screenshots for the check-in)

1. Home page (`/`): type `LunarRaven#7777` and press Search.
2. The profile page shows ranks, win rate, and teammate averages by role. **This is the GUI screenshot that shows the database working.**
3. Change Queue or Time period and press "Apply filters". The numbers change.
4. Log in with the admin account you created in step 7. The header shows your username.
5. Search a name that does not exist (`Nobody#0000`) to see the "couldn't find that profile" message.

The Register page and the saved-search pages are not built in the front end yet. The backend for them works. To show it, use the commands in `docs/API.md`, or the quick test below.

### Quick test of sign-up and saved searches without any page (optional)

Open the site in a browser, open the developer console (F12, Console tab), and paste:

```
const s = await (await fetch('/api/session')).json();
const h = {'Content-Type':'application/json','X-CSRF-Token': s.csrfToken};
await fetch('/api/register',{method:'POST',headers:h,body:JSON.stringify({username:'demo1',email:'demo1@example.com',password:'password123'})}).then(r=>r.json())
```
You should see `{ok: true, username: "demo1"}`. Then log in as `demo1` in the header's login form.

## Troubleshooting

| Message or symptom | Fix |
|---|---|
| `Missing POSTGRES_PASSWORD` | You have no `.env` file, or it is in the wrong folder. It must sit next to `docker-compose.yml`. |
| `Missing SECRET_KEY` | Add a `SECRET_KEY=` line to `.env`. |
| `password authentication failed` | The password in `.env` is different from the one the database was created with. Run `docker compose down -v` then `docker compose up -d`. |
| `connection refused` or the website shows "Database unavailable" | Docker Desktop is not running, or the container is down. Run `docker compose up -d`. |
| `port is already allocated` | Another program uses port 5435. Change `DB_PORT` in `.env`, then run `docker compose down -v` and `docker compose up -d`. |
| `Address already in use` when starting Flask | Another program uses port 5001. Start it on another port: `PORT=5002 python backend/server.py` (Mac) or `$env:PORT=5002; python backend/server.py` (PowerShell). |
| `relation "registered_users" does not exist` or `column "role" does not exist` | You have an old database volume. Run `docker compose down -v` then `docker compose up -d`. |
| `ModuleNotFoundError: No module named 'flask'` | The virtual environment is not active. Run the activate line from step 5 again. |
| "Security token missing or expired" (400) | Your session cookie was cleared. Reload the page and try again. |

## Database tables, in one place

`db/schema.sql` creates 8 tables: Registered_Users (now with a `role` column), Players, Queue_Types, Matches, Match_Teams, Participants, Player_Ranks, Saved_Searches. Each foreign key and CHECK constraint is in that file. `db/seed.sql` holds the sample data.
