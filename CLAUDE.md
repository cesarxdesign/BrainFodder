# BrainFodder

Read README.md first, then diary.md, then BACKLOG.md.

- The front end is index.html; keep it one self-contained file (no build step)
- The only server code is api/feed.js; keep it a stateless proxy
- localStorage key `brainfodder.v1` and IndexedDB `brainfodder` hold the user's reading history; never change their shape without a migration
- The starter feeds (DEFAULT_SUBS) only apply on first open; changing them does not touch an existing install
- Target: Mac, desktop browser
- No em dashes in UI copy
- Every new fact or decision goes into diary.md
- Commit and push to main after every change, without asking; versions are git tags (v0.1, v0.2 ...)
