# BrainFodder diary

## 2026-11-15

- Why: Instagram, YouTube and X feeds had nothing worth reading; Cesar wanted an RSS reader like the old Google Reader, and did not love NetNewsWire
- Name: BrainFodder
- Platform: Mac only, in the browser
- Must-haves he picked: folders with unread counts, j/k keyboard flow, list vs expanded view, star and share
- Repo: public is fine
- Folders he asked for: Tennis, Tech, Misc
- Tennis: 10 feeds covering player stories, latest scores, new rackets and gear reviews
- Tech: AI, Apple, Tesla, SpaceX and fintech
- Misc: the original reading list (The Browser, Kottke, Marginal Revolution, Hacker News best, Works in Progress, Asterisk, Quanta, Gwern, Maggie Appleton, Dan Luu, Craig Mod) plus positive, interesting stuff with no gossip, in the spirit of Veritasium, Cleo Abram and Hannah Fry
- Build choices: Vercel hosting like his other sites, a single index.html plus one serverless function to fetch feeds (browsers are blocked from fetching other sites directly), reading state kept in the browser so there is no database or login
- YouTube channels come in through YouTube's own channel feeds; Shorts are dropped so only full videos show
- Rejected for now: syncing read state across devices, since he only reads on the Mac

## 2026-11-15, first run against real feeds

- Tested all 45 starter feeds before going live. The starter list now holds the final feed addresses, so a first open skips the search for each feed
- Feed swaps, and why:
  - ATP Tour: atptour.com refuses outside requests (403). Now a Google News search for atptour.com stories; headlines and snippets only, links go through Google
  - WTA: wtatennis.com has no feed. Now a Google News search for wtatennis.com stories
  - ESPN Tennis: the feed answers empty. Swapped for Tennis365 (player stories and results)
  - This Week in Fintech: no feed anywhere on the site. Swapped for Fintech Blueprint (lex.substack.com)
  - Gwern: the only feed is a Substack last updated in 2021. Swapped for Construction Physics
  - Hannah Fry: @HannahFry does not exist; her channel is @fryrsquared
  - Marginal Revolution: the homepage refuses outside requests, the /feed address works
  - Fix the News: the feed could not be found from the homepage; it lives at substack.fixthenews.com/feed
- Finextra lists upcoming events with 2027 dates; any future date now counts as the day it arrived, so they don't sit on top for weeks
- YouTube: each channel's normal feed is mostly Shorts (14 of Cleo's last 15), so after dropping Shorts only 1 to 4 videos were left. Every channel now has two feeds: the long videos playlist (UULF) and the Shorts playlist (UUSH), 15 each. Smarter Every Day has no Shorts, so only the long one
- Cesar likes Shorts, but only from channels he follows. Shorts are no longer dropped
- Shorts player (y, or the Shorts button): plays unseen Shorts from your subscriptions, newest first; when one ends BrainFodder loads the next itself, so YouTube's end screen and suggestions never show. A Short counts as seen once it starts playing
- Long videos also play inside BrainFodder (Play on the item)
- Premium: storing his Google login is not possible and a sign-in token would not remove ads; ads in the player depend on being signed in to youtube.com in the same browser. Chrome allows that, Safari may not
- Hosting stays Vercel: a web page can't fetch other sites' feeds, so the feed fetcher needs a server, which GitHub Pages can't run. Each deploy is well under 1 MB
- A native Mac app was considered and dropped the same evening: Cesar wants a live page
- Live test on Vercel (brainfodder.vercel.app), all 50 feeds through the deployed API:
  - NASASpaceflight and Finextra answered from the Mac but refuse Vercel's servers (403). Both now come through a Google News search for their own site, the same way as ATP and WTA
  - Simon Willison, Maggie Appleton, Dan Luu and Craig Mod failed with "Entity expansion limit exceeded". The XML parser counts every &lt; and &amp; in a feed and stopped at 1000; long feeds with escaped HTML have more. The cap is now 2 million, with the guards against booby-trapped feeds (DOCTYPE entities) kept
- Live check in Chrome: all 50 feeds load with unread counts, none flagged; j/k move through items; no console errors on load or in use. Shorts player: 18 new Shorts queued, the next one started by itself when one ended, j skipped, Esc closed. Not checked: whether Premium removes ads in the player
- Live address: https://brainfodder.vercel.app (Vercel team cesarxdesign1, project brainfodder, deploys on every push to main)
