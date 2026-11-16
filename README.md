# BrainFodder

A Google Reader style RSS reader for the Mac browser. Started 2026-11-15.

## How it works

- Folders on the left with bold unread counts: Tennis, Tech, Misc
- Expanded view (full articles inline) or List view (headlines), toggle with 1 and 2
- Keyboard first: j/k (or . and ,) next and previous, s star, m read/unread, v open original, Shift+A mark all read, ? for the full list
- Items are marked read as you move onto them or scroll past them; "Keep unread" holds one back
- Star to keep, Share (Mac share sheet, or copies the link), Email
- Add any website or feed address; it finds the feed on its own. YouTube channel pages work too
- OPML import and export in Settings
- Opening or reloading the page fetches once, as does the Fetch button (or r): it fetches every feed and groups the same news from several sources into one story card (headline, short summary, the source that adds most, every source listed). It works only on Cesar's Mac; anywhere else nothing is fetched and the load stays quiet
- Shorts: y plays your unseen Shorts, newest first; the next starts by itself

## Data

- Subscriptions, folders and view settings: browser localStorage, key `brainfodder.v1`
- Articles with read and star state: browser IndexedDB, database `brainfodder`
- Everything lives in the one browser and the one web address it is used at; nothing syncs. Export OPML to move feeds
- Read items older than 90 days are pruned; starred items are kept forever

## Files

- `index.html` the whole app (code)
- `helper/helper.py` runs on Cesar's Mac only: fetches feeds (browsers can't, because of CORS) and groups repeated news with Claude Haiku through Claude Code on his Max plan (code)
- `helper/com.cesarxdesign.brainfodder.plist` and `helper/install.sh` set macOS to start the helper when Fetch is pressed; it quits when that fetch is answered. Log: ~/Library/Logs/BrainFodder/helper.log
- `diary.md` every decision and fact about the project
- `BACKLOG.md` what is next

## Hosting

https://cesarxdesign.github.io/BrainFodder/, GitHub Pages from `main` of `cesarxdesign/BrainFodder` (public). No build step, no server: fetching happens on Cesar's Mac.

On a new Mac: run `helper/install.sh`, be signed in to Claude Code, and allow Chrome's "access other apps and services on this device" prompt on the first Fetch.
