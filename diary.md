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

## 2026-11-16

- Repeat news: two sources often report the same thing (the same score from yesterday). Cesar asked for a cheap model to group the same news from different sources into one entry, summarise it, and offer the one source that adds most beyond the summary as further reading
- It must run on his Max plan, not a paid API, and only from his Mac: if anyone else opens the public link, they can't fetch or use his plan. His phone doesn't matter
- His call: no automatic refresh. One Fetch button starts everything, and whatever runs quits as soon as the fetch is done, not after a timer
- Built: helper/helper.py. macOS holds port 47823 on 127.0.0.1 and starts the helper when the page connects; it answers only brainfodder.vercel.app (and Pages and localhost), and quits after every request except the browser's pre-check. The helper fetches all feeds itself (a Python port of api/feed.js; item ids checked identical) and streams them to the page
- Grouping: Claude Haiku 5.5 through Claude Code (`claude -p --model haiku`, no tools, own system prompt, no project files), so it uses the Max plan. Step 1 sorts the last 48 hours of news (videos excluded) into stories: same event only, not same topic. Step 2, per story with 2+ sources: the helper reads the articles (Google News links only give headlines), Haiku writes a headline, 2 to 3 sentence summary, picks the source that adds most and says what it adds
- First test run: 196 new items, 17 stories, 18 Haiku calls, about 108,000 tokens, 79 seconds. Later presses only send Haiku items it hasn't seen
- Fixed after the test: with headline-only sources Haiku wrote "no details available" into summaries; the prompt now forbids mentioning what is missing
- Fixed: a refused request (wrong website) left the helper running; it now quits after every request
- Story card: one per story, read together, counted once in the sidebar
- Lesson: the first version bumped the IndexedDB version to add a stories store; Chrome holds an upgrade until every open tab on the old version closes, so yesterday's open tab blocked the page. Stories now live in their own database, `brainfodder-stories`; the items database is never upgraded
- api/feed.js on Vercel is no longer used by the page
- First live press on Cesar's Chrome: Chrome asked once to let the site reach apps on this device (Local Network Access); after Allow, the helper fetched 50 feeds in 8 s, grouped 219 items into 22 stories with 23 Haiku calls (about 122,000 tokens, 89 s), and quit. Unread went from 717 to 674. That run sent every item of the last 48 hours, because none had been grouped yet; later presses only send new items
- Moved to GitHub Pages (Cesar's call): https://cesarxdesign.github.io/BrainFodder/. api/feed.js, vercel.json and package files removed; the Vercel project `brainfodder` deleted, so Vercel again holds only cxd and stats. The helper no longer answers brainfodder.vercel.app (that address is free for anyone to take now)
- Browser data belongs to one web address, so reading history, stars, stories and feeds were carried from the Vercel address to the Pages one through a one-off relay on the Mac: 1,477 items, 22 stories, same unread count. Chrome's local network permission was already granted for the new address
- First Fetch from Pages: 9 new items, 2 more stories, 3 Haiku calls, about 37,000 tokens, 44 s. Most of those tokens are the grouping list, which resends every item of the last 48 hours
- Trimmed what each Fetch sends Haiku (Cesar's go): new items go in full; existing stories and older single items go in only when they share 2 or more distinctive words with a new item, and older items as headline only. Story writing reads the full article for at most 5 sources, one per feed, 500 words each; the rest go in as headlines
- After the trim: 6 new items, a 74-line list, 2 stories, 3 Haiku calls, about 12,000 tokens, 23 s (before: 9 new items, about 37,000 tokens). Grouping still joined new items to existing stories (a Marginal Revolution post joined the Starship story)
- Cesar asked for . and , as next and previous too (same as j and k, also in the Shorts player)
- Thumbs up/down on every article and story card (Cesar's ask): an internal signal for keeping or dropping sources later; nothing acts on it yet. Each vote is saved on the article and tallied per source (up / down on the subscription in localStorage), so the tally survives the 90-day pruning of read articles. A story card's vote goes to the source it recommends reading. Pressing the same thumb again takes the vote back
- Full articles in place (Cesar's ask): when a feed gives less than 600 characters, the helper reads the article page at Fetch time and the item shows it in full (at least 150 words, up to 6 pictures; on the first Fetch also short items from the last 7 days). OpenAI and Finextra block reading their pages, so they stay headline plus link
- Google News items can't open in place: the real article address needs Google's internal API, which the permission check blocks. ATP and WTA stay on Google News (free sites, a click opens them). NASASpaceflight and Finextra are back on their own feeds, which work from the Mac; existing installs switch over by themselves, and items that reappear under a new id keep their read state
- Paywalls dropped (rules agreed by Cesar): publishers NYT / The Athletic, WSJ, FT, Bloomberg, The Times, Telegraph, Economist, Washington Post, Business Insider, Barron's, New Yorker, The Information, LA Times, Boston Globe, The Australian, Spectator, Foreign Affairs, HBR, Stratechery, Puck, Seeking Alpha; metered sites (Atlantic, Wired) stay. Also dropped: an article whose page has under 150 readable words and says to subscribe to continue. Starred items are never dropped
- Lesson: these values were first shipped without asking; they were switched off until Cesar agreed them
- First Fetch with full articles: 183 read in full, 15 paywalled items dropped, 34 new items, 14 stories, about 53,000 tokens, 90 s
- Fixed after it: older Google News items from paywalled publishers stayed (only ones in the current feed were dropped); the helper now sends the publisher names and the page drops Google items whose titles end with them. A BBC Sounds page came through as menu text; outside a real article container only paragraphs count now, so it stays headline plus link. Articles read before this fix are read again on the next Fetch
- Full articles now stop at the last paragraph of running text, and list items or headings that are mostly a link are skipped, so related-story cards and their pictures don't follow the article. Articles read earlier are read again once
- Sort switch in the top bar (Cesar's ask): Newest first (as before) or Oldest first; one setting for every feed and folder, remembered in the browser. The backlog's "oldest-first per feed" item is done by it
- Old pages that Google News searches keep returning (e.g. 2019 WTA player profiles) arrive unread on later Fetches and sit on top with Oldest first; Cesar's call: leave them
- Oldest first is the default (Cesar's call); existing installs switched over once, and the switch shows Oldest first on the left
- ATP Tour and WTA removed, Ubitennis added in their place (Cesar's call): neither site has a feed of its own, and their Google News searches returned site pages (draws, head-to-heads, Stats Centre pages, player profiles, schedules) mixed with news; limiting the search to news addresses or to recent days didn't stop it. Existing installs switch over by themselves; the pages go with the two subscriptions
- Every page load or reload now runs one Fetch, the same as pressing the button (Cesar's call, 2026-11-16). Still no timer: the helper starts with that request and quits when it's done. Away from his Mac the load-time fetch fails quietly; the button still says why
- Load-time fetch tested live: one load = one run (2 new items, 2,576 tokens). A first test made 3 runs in a row because my test script hung the tab, not because of the page
- Dan Luu's feed is 6.6 MB (every essay in full) and downloads slowly, so since 17:30 on 2026-11-16 it has held each Fetch for 17-205 s and often times out; open question for Cesar
- Cesar's correction: fetch when the page is opened, not on every reload (reloads happen a lot). A reload, back/forward, or a tab Chrome slept and woke doesn't fetch; the Fetch button (r) still does
- Dan Luu removed (Cesar's call): the 6.6 MB feed held every Fetch for up to 205 s. Existing installs drop it by themselves; its unstarred items go on the next prune
