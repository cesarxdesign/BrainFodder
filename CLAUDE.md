# BrainFodder

Read README.md first, then diary.md, then BACKLOG.md.

- The front end is index.html; keep it one self-contained file (no build step)
- Fetching runs only through helper/helper.py on Cesar's Mac: macOS (launchd, helper/com.cesarxdesign.brainfodder.plist) starts it when the page's Fetch button connects to 127.0.0.1:47823, and it quits as soon as that request is answered. It fetches feeds and groups repeated news with Haiku through Claude Code on his Max plan. Never a paid API key, never a timer, nothing running between clicks
- api/feed.js on Vercel is no longer used by the page
- localStorage key `brainfodder.v1`, IndexedDB `brainfodder` (items) and `brainfodder-stories` (stories) hold the user's reading history; never change their shape without a migration, and never bump a database version (an open older tab blocks the upgrade): add a new database instead
- The starter feeds (DEFAULT_SUBS) only apply on first open; changing them does not touch an existing install
- Target: Mac, desktop browser
- No em dashes in UI copy
- Every new fact or decision goes into diary.md
- Commit and push to main after every change, without asking; versions are git tags (v0.1, v0.2 ...)
