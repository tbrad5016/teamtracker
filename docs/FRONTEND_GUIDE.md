# Front-end guide (for Sophia)

Your pages stay plain HTML, CSS and JavaScript. The backend serves them as they are and answers your `$.ajax` calls with JSON. You do not write any Python.

## Where your files go

```
frontend/
  templates/   home.html, results.html, list.html   <- your HTML pages
  static/      styles.css, homeCSS.css, profileCSS.css, script.js, auth.js, img/...
```

Everything is served from the site root, so your links work exactly as you wrote them: `href="styles.css"`, `src="script.js"`, `img/profilePicImg.PNG`, `href="results.html"`.

**Put your images in `frontend/static/img/`.** The profile picture file `img/profilePicImg.PNG` was not in the files we received, so the picture shows as broken until it is added. The name is case sensitive on Mac and Linux, so keep `.PNG` exactly.

## What we changed in your files (3 small things)

1. `script.js`: `USE_MOCK_PROFILE_DATA` is now `false`, so the pages call the real backend. The fake `SEARCH_SUGGESTIONS` list was replaced by a call to `/api/search` (real players).
2. `home.html`, `results.html`, `list.html`: two lines added below `script.js`:
   `<script src="auth.js"></script>` and `<script src="account.js"></script>`
   Add the same two lines to every new page.
3. A new file, `static/auth.js`, which belongs to the backend. It handles login. Please do not edit it. If you need something changed, tell Brad.

If you send updated versions of your files, keep those three things.

## What the backend does for you

| Your page or element | What happens |
|---|---|
| `results.html?search=Name%23Tag` | `script.js` calls `GET /api/profile?riotId=...&queue=...&period=...`. The reply matches `docs/profile-data-format.md`. Capitals do not matter. |
| `#login-box` form | `auth.js` sends it to `/api/login`. A wrong password shows the error message next to the button. A good login reloads the page. |
| Logged in | `auth.js` swaps `#login-box` for an `#account-box` (picture, username, Log Out). It uses the same markup and CSS as `list.html`. |
| `list.html` while logged out | The page shows "Please log in" and the account box says "Not logged in". |
| Log Out link (`#logout-link`) | Logs out and goes to `home.html`. |

Keep these ids because the scripts look for them: `#login-box`, `#username`, `#pw`, `#account-box`, `#home-search`, `#search-box`, `#player-profile`, `#profile-message`, `#queue`, `#period`, `#rank-rows`, `#role-rows`, `#summary-games`, `#summary-wins`, `#summary-winrate`, `#profile-username`.

## Pages the backend side already built (restyle them if you like)

`register.html`, `account.html` and `admin.html` use your `styles.css` and `profileCSS.css`, plus `forms.css` (buttons and form fields). `account.js` runs them, and `auth.js` adds the "Follow this player" button to profiles. Keep their ids and the `data-page` attribute on `<body>`. The search suggestions in `script.js` now call `GET /api/search`, so no names are hard-coded.

Still open: the My Profile page needs a decision (see `docs/API.md`, "Open decisions").

## Try it

Follow `docs/SETUP.md`, then open http://127.0.0.1:5001. Edit a file, save, and refresh the browser (hard refresh: Ctrl+Shift+R). If a page looks blank, open the browser's developer console (F12) and look for red errors.

Sample players to search: `LunarRaven#7777`, `QuietRaven#5150`.
