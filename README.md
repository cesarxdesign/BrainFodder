# BrainFodder

A Google Reader style RSS reader for the Mac browser. Started 2026-11-15.

## How it works

- Folders on the left with bold unread counts: Tennis, Tech, Misc
- Expanded view (full articles inline) or List view (headlines), toggle with 1 and 2
- Keyboard first: j/k next and previous, s star, m read/unread, v open original, Shift+A mark all read, ? for the full list
- Items are marked read as you move onto them or scroll past them; "Keep unread" holds one back
- Star to keep, Share (Mac share sheet, or copies the link), Email
- Add any website or feed address; it finds the feed on its own. YouTube channel pages work too
- OPML import and export in Settings
- Feeds refresh on open, every 30 minutes, and on r

## Data

- Subscriptions, folders and view settings: browser localStorage, key `brainfodder.v1`
- Articles with read and star state: browser IndexedDB, database `brainfodder`
- Everything lives in the one browser it is used in; nothing syncs. Export OPML to move feeds
- Read items older than 90 days are pruned; starred items are kept forever

## Files

- `index.html` the whole app (code)
- `api/feed.js` Vercel function that fetches a feed server side (browsers can't, because of CORS), finds the feed on a website, and returns JSON (code)
- `vercel.json` gives the function 30 seconds
- `diary.md` every decision and fact about the project
- `BACKLOG.md` what is next

## Hosting

Vercel, deployed from GitHub `cesarxdesign/BrainFodder` (public). No build step.
