# Profile data format

The results page and My Profile page fill in every number, bar and badge from JSON returned by your backend (the Python script run against the database). Nothing on those pages is hard-coded.

## Switching from demo data to the real backend

In `script.js`, change `USE_MOCK_PROFILE_DATA` from `true` to `false`. The pages then call the endpoints below.

| Page | Endpoint (set in the `data-endpoint` attribute in the HTML) | Request |
| --- | --- | --- |
| `results.html` | `/api/profile` | `GET /api/profile?riotId=LunarRaven%237777&queue=any&period=6` |
| `list.html` (My Profile) | `/api/me/profile` | `GET /api/me/profile?queue=any&period=6` (the backend works out who is logged in from the session) |

Query parameters:

- `riotId`: what the visitor typed in the search bar, with the `#tag` (results page only)
- `queue`: `any`, `solo` or `flex`
- `period`: number of months, `1`, `3`, `6` or `12`

Clicking "Apply filters" sends a new request with the chosen `queue` and `period`, and the page redraws from the response. The filters are also written to the page URL (`?search=...&queue=solo&period=3`), so reloading keeps them.

## Response (HTTP 200, JSON)

```json
{
  "riotId": "LunarRaven#7777",
  "avatarUrl": "https://example.com/icon.png",
  "ranks": [
    { "queue": "RANKED_SOLO_5x5", "rank": "Diamond II", "lp": 0, "wins": 47, "losses": 45 },
    { "queue": "RANKED_FLEX_SR", "rank": "Platinum III", "lp": 47, "wins": 48, "losses": 53 }
  ],
  "summary": { "games": 21, "wins": 8 },
  "roles": [
    { "role": "TOP", "games": 11, "avgKills": 4.5, "avgDeaths": 4.7, "avgAssists": 5.9, "kda": 2.21 },
    { "role": "JUNGLE", "games": 12, "avgKills": 5.6, "avgDeaths": 4.8, "avgAssists": 8.4, "kda": 2.9 },
    { "role": "MIDDLE", "games": 16, "avgKills": 6.4, "avgDeaths": 4.6, "avgAssists": 7.4, "kda": 3.04 },
    { "role": "BOTTOM", "games": 12, "avgKills": 7.3, "avgDeaths": 3.7, "avgAssists": 6.2, "kda": 3.66 },
    { "role": "UTILITY", "games": 13, "avgKills": 1.3, "avgDeaths": 5.2, "avgAssists": 10.3, "kda": 2.22 }
  ]
}
```

What the page does with each field:

- `riotId`: the heading. `avatarUrl` is optional (the placeholder image stays if it is missing).
- `ranks`: one table row each. `queue` can be the Riot code (`RANKED_SOLO_5x5`, `RANKED_FLEX_SR`) or a display name. Win rate is worked out from `wins` and `losses`. The rank table does not change with the filters unless your script changes it.
- `summary`: the "Games in this filter" and "Wins" tiles for the chosen filters. The win rate tile is `wins / games`.
- `roles`: one table row each, in the order you send them. `role` can be the Riot codes `TOP`, `JUNGLE`, `MIDDLE`, `BOTTOM`, `UTILITY` (shown as "Support") or `SUPPORT`, or a display name. Send only the roles you want shown.
- `kda`: send the finished number, calculated from the totals as (kills + assists) / deaths. The page does not recalculate it, because averaging already-rounded values gives slightly different results.
- The bar length is `kda` out of 5, and the Good / Average / Bad badge and bar color come from `kda` (3.5 or more is Good, 2.5 to 3.5 is Average, below 2.5 is Bad). The numbers 3.5, 2.5 and 5 are the constants `GOOD_KDA_MIN`, `AVERAGE_KDA_MIN` and `KDA_BAR_MAX` at the top of the profile section in `script.js`, and the explanation sentence on the page is built from them.
- A missing or `null` number is shown as a dash.
- If `roles` is empty the table shows "No games found for this filter."

## Other responses

- HTTP 404, or HTTP 200 with `{ "found": false }`: the page shows "Oops, we couldn't find that profile! Try searching for a different Riot ID!"
- HTTP 401 (My Profile only): "Please log in to view your profile."
- Any other error: "Something went wrong loading this profile. Please try again in a moment."
