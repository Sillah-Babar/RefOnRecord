# RefOnRecord — Web Client

A single-page browser application for the RefOnRecord Resume Verifier API.  
Users can create and manage resume projects, add work experiences, request
employment verification from former colleagues, and share their verified resume
with recruiters via a unique public link.

## Features

| Feature | API resource(s) used |
|---|---|
| Register / Login / Logout | `POST /api/users/`, `POST /api/auth/login/`, `DELETE /api/auth/logout/` |
| View & edit resume projects | `GET/PUT /api/users/{uid}/projects/{pid}/` |
| Create / delete projects | `POST/DELETE /api/users/{uid}/projects/` |
| Add / edit / delete experiences | `POST/PUT/DELETE …/experiences/` |
| Request verification from verifier | `POST …/verification-requests/` |
| View verification status & comments | `GET …/verification-requests/` |
| Create / delete share links | `POST/DELETE …/shares/` |
| Copy share URL to clipboard | (client-side) |
| View public resume via share token | `GET /api/shares/{token}/` |
| Print public resume | (browser print, print CSS) |
| Auto-refresh pending verifications | polls `GET …/experiences/` every 30 s |

## Dependencies

- No build step required — vanilla HTML / CSS / JavaScript (ES2020).
- Google Fonts (Inter) loaded from CDN at runtime — works offline with
  system-font fallback.
- A running instance of the RefOnRecord API reachable at the URL configured
  in `app.js` (`API_BASE` constant, default `http://74.241.132.64:8080`).

## Setup

1. Clone or copy the `client/` directory to your machine.
2. *(Optional)* If your API runs on a different host, edit the first constant
   in `app.js`:
   ```js
   const API_BASE = 'http://<your-api-host>:<port>';
   ```
3. The API must allow CORS from the origin you serve the client from
   (or `*`).  The production instance at `74.241.132.64:8080` is already
   configured for this.

## Running

**Option A — Python built-in server (recommended)**

```bash
cd client
python3 -m http.server 3000
# open http://localhost:3000 in your browser
```

**Option B — Node `serve`**

```bash
npx serve client -p 3000
```

**Option C — VS Code Live Server extension**

Right-click `index.html` → *Open with Live Server*.

> **Important:** Do not open `index.html` directly as a `file://` URL.
> Browsers block cross-origin `fetch()` from `file://`, so all API calls
> will fail.  Always serve via a local HTTP server.

## Code Quality / Linting

ESLint with the `eslint:recommended` ruleset can be run with:

```bash
npx eslint app.js
```

The file begins with `'use strict';` and uses no global variables beyond
the constants and functions defined within it.

## File Structure

```
client/
├── index.html   – Static SPA shell; all views are <div> elements
├── style.css    – All styles; responsive, includes print CSS
├── app.js       – All application logic (routing, API client, UI)
└── README.md    – This file
```

## Screen Workflow

```
[Auth view]
  Sign In  ──────────────────────────────► [Dashboard]
  Register ─► (shows success toast) ──────► [Auth / login tab]

[Dashboard]
  Open resume ─────────────────────────── ► [Project view]
    ├── Overview tab   (edit metadata, save)
    ├── Experiences tab
    │     ├── Add / Edit / Delete experience
    │     └── Verifications modal (view + request)
    └── Share Links tab
          ├── Create share link  (copy URL auto-offered)
          ├── Copy URL / View public resume
          └── Delete share link

[Public view]  (opened via  #share/<token>  hash)
  Print button ──► browser print dialog
  Open App    ──► [Dashboard or Auth]
```

## Sources

All code written from scratch by the RefOnRecord team (PWP 2026).  
External resources:
- [Inter font](https://fonts.google.com/specimen/Inter) — SIL Open Font Licence
- [MDN Web Docs](https://developer.mozilla.org/) — API reference
