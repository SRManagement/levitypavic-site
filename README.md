# SRM Dashboard

Private earnings dashboard for Levity Pavic: Fanvue earnings (live) minus Fanvue's cut, chatter pay, expenses from the SRM Expenses Google Sheet, and optional tax. Card 0029 charges come straight from the bank through Plaid; the ones you approve are written into the sheet.

Vercel builds from the `src` folder (Settings → Root Directory = `src`). Leave that as is.

## Update 78: the record celebration moves to the next morning (just upload; includes 43–77)
- The evening report is back to standard (no all-time-high check: the day still has hours left at 8 PM).
- **Morning, after a best day ever:** a bonus slide appears right after the overnight money. "Yesterday · Monday, October 5 · ✦ Record day".
  It shows the whole day's gross (12 AM to 11:59 PM) with how far it beat your previous best, new subs and net, the previous best and its date,
  the warm glow, and the confetti cannons from both sides.
  The voice says: "Yesterday was a record high. You made $X gross, beating your previous best of $Y. That's an all time high, congratulations."
- On a normal morning the slide (and its progress bar) simply isn't there. A record needs a week of history.
- **Earnings milestone pushes (new file src/earnings_push.py):** every time the day's gross crosses another $1,000, your phone gets
  one push: "You have hit 1k on the day 😛", "2k 🫣", "3k 😮‍💨", "4k 😳", "5k 🤑" (6k and up: 🔥 💸 🚀 👑 🤯), with the gross so far and the time.
  It works with SRM closed: the every-minute check re-pulls today's Fanvue numbers every 5 minutes. Each milestone goes out once.
  If two are crossed between checks, only the newest is sent. The first run after this update just notes where today already is.

## Update 77: all-time high celebration, closing lines spoken (just upload; includes 43–76)
- **Evening report, best day ever:** when today's gross so far beats every earlier day on record (needs a week of history), the earnings slide
  gets an "✦ All-time high" badge with your previous best and its date. The gross row glows warm, and once the number finishes counting up,
  two confetti cannons fire from the lower left and right, up and inward. The pieces flutter down slowly in warm colors.
  The voice adds: "That's an all time high, congratulations." Only on that slide, only in the evening report.
- **Closing lines are now read out:** morning "Carpe diem." (said KAR-pay DEE-em), afternoon "Stay sharp.", evening "Rest well."

## Update 76: pausing is invisible (just upload; includes 43–75)
- Holding to pause on iPhone, and tap / space-bar pause on the computer, no longer put a pause symbol on screen.
  The progress bar and voice just stop, and carry on when you let go or tap again.

## Update 75: hold to pause on iPhone (just upload; includes 43–74)
- Hold a finger anywhere on a brief: the voice and the progress bar pause. Let go and it carries on.
  A quick tap still goes back (left side) / forward (right side). No long-press menu pops up.

## Update 74: simpler sound pill (just upload; includes 43–73)
- The welcome's sound control is now a small icon-only pill: a speaker icon. Tap it and a slash goes through it (silent); tap again for sound.
  It still disappears once the brief moves past the welcome. The mute icon at the top right uses the same slashed speaker.

## Update 73: sound on by default (just upload; includes 43–72)
- Every brief starts with sound. The "Tap for sound" pill is gone; a "Sound off" pill sits at the top during the welcome
  instead (tap it to mute this one), and it disappears once the brief moves on. Mute never carries over to the next brief.
- Browsers only allow sound after you've touched the page. SRM now "unlocks" its player on your first tap, click or key,
  so a brief that opens later plays with sound by itself. If a brief opens the instant the iPhone app launches, before
  any touch, your first tap anywhere starts the voice (that tap doesn't skip or pause).
- Mac Safari: Safari → Settings → Websites → Auto-Play → SRM → "Allow All Auto-Play" makes it play with sound even before any click.

## Update 72: the briefs play on the computer and on the phone separately (just upload; includes 43–71)
- Each brief (morning, afternoon, evening) plays once a day on the computer AND once a day on the phone. Seeing it on one
  no longer uses up the other's showing.
- Because the "already seen" tracking is new, today's briefs will play once more on each device after you upload.

## Update 71: no square around the suns, weather strip ends at night (just upload; includes 43–70)
- The glow around the sun / moon / weather icon is now a soft radial light behind it. Safari drew the old glow filter as a square.
- **Weather strip:** the day runs in even steps up to an hour after sunset, rounded to the nearest hour (sunset 6:33 → 8 PM).
  The exact sunset time sits in its own cell, then one "Tonight" cell with tonight's low.
  The voice now also says "Sunset is at 6:33 PM."
- Old cached weather from before this update is ignored, so the sunset cell always shows.

## Update 70: a look of its own for each brief (just upload; includes 43–69)
- **Morning (dawn):** plum sky warming to peach at the bottom. A sun rises over the horizon above "Good morning". A warm glow comes up
  from below, specks of light drift upward, and the gradient goes peach to rose to lilac.
- **Afternoon (daylight):** clear deep-blue sky, a bright sun with turning rays above "Good afternoon", slow light rays and a soft glare
  from the top-right corner, and a cool white to sky-blue to teal gradient.
- **Evening (night):** unchanged: moon, stars, indigo and amber.

## Update 69: tap to go back / forward in the briefs, better weather strip, edit to-dos in place (just upload; includes 43–68)
- **Briefs:** tap the left side to go back a screen, the right side to go forward, the middle to pause.
  A screen you've already heard comes back silent; only new ones are read out.
- **Weather strip:** the hourly cells now span the same width as the UV scale, and run past midnight if needed.
  Today's exact sunset time is its own cell, in time order. (The separate sunset chip is gone.)
- **Calendar:** tap any to-do, anytime item or reminder title to edit it in place. Enter or tapping anywhere else saves; Esc undoes.

## Update 68: upcoming reminders live in the bell (just upload; includes 43–67)
- The big "coming up" banner is gone. Reminders in the next hour now sit at the top of the bell: yellow within the hour,
  red within 30 minutes, and they count toward the badge. Tap one to open that day in the calendar.
- ✕ dismisses it on every device. It stays in the calendar, and the phone pushes still go out.
  If you move the reminder to a new time, it shows up in the bell again. "Clear all" clears these too.

## Update 67: weather city in Moderator, keyboard dictation for scheduling (just upload; includes 43–66)
- **Moderator → Weather city:** type a city ("Austin" or "Austin, TX") and Save. Every morning brief uses it, ahead of
  any automatic location. Clear it and Save to go back to automatic (network location on iPhone, device location on the Mac).
- **Schedule:** always opens to the text box with the keyboard up. SRM's own mic is gone: iOS made it ask for permission every time.
  On iPhone, tap the 🎤 on the keyboard and say it. Apple's dictation never asks, and the same smart parsing runs on what you say.

## Update 66: no location pop-ups (just upload; includes 43–65)
- iPhone Home Screen web apps can't keep a location (or mic) permission. iOS asks again every launch, and Safari's settings don't carry over.
  So the weather never asks on the iPhone. It uses your device's location if the permission is already on; otherwise your network's location
  (Vercel gives the city, no permission needed); otherwise the last precise spot from your Mac, as long as you're still in that area.
  Travelling? The network location takes over automatically.
- On the Mac it may ask once, and then no more than once a week.

## Update 65: morning weather + UV, health numbers that line up (just upload; includes 43–64; new file src/weather.py)
- **Weather in the morning brief**, a new scene after the money screen. It uses your device's own location (iPhone / Mac location
  services); nothing to set in Moderator. The first time, Safari asks to use your location: tap Allow.
  - Screen: an animated icon (sun turning, clouds drifting, rain or snow falling, lightning flicker), the temperature now, high / low,
    the next hours in 3-hour steps, a UV scale with today's peak and when it hits, chance of rain, wind and sunset.
  - Voice: "Today in Los Angeles: partly cloudy, with a high of 78 and a low of 61. UV peaks at 8, very high, around 1 PM."
    It mentions rain from a 30 percent chance up.
  - Data is from Open-Meteo (free, no key). The last location is remembered, so it still works if the location is slow to come.
- **Health numbers, checked across all three briefs:**
  - Morning is all sleep-based: resting HR is labeled "asleep" (WHOOP measures it during sleep), breathing rate was added,
    the HRV arrow compares against your last week (it was 2 nights), and the strain chip now says "Yesterday's strain" (that's what it is).
  - Evening heart rate covers awake time only. WHOOP's day starts when you fall asleep, so its average includes last night.
    SRM takes last night's sleep back out, at your sleeping heart rate, and shows "Awake avg".
  - Afternoon and evening workout HR are from the workouts themselves. Day strain, calories and steps are WHOOP's own day totals.

## Update 64: night look for the evening report (just upload; includes 43–63)
- **Evening report:** a warm crescent moon rises above "Good evening, Ryan" and above tonight's bedtime.
  Deep navy background, indigo and amber light drifting slowly, a few twinkling stars, moonlit gradients and warm progress bars.
- **Rollover:** unchecked to-dos and anytime items carry over to the next day at midnight (already in place; timed reminders don't roll over).
  The evening report now says so: "Still open: Call bank and Post reel. They will roll over to tomorrow."
  The checklist screen also has a small note about it.

## Update 63: cleaner on iPhone, month comparison in the evening only (just upload; includes 43–62)
- On a phone, a headline's sub-line ("for today yet", "83 active min", "asleep of 8.2h needed") now sits on its own line under it.
  Chips, legends and labels are centered, and a 5-digit step count fits inside its wheel.
- Morning and afternoon are updates on the day: just the money in that window, with no month comparison on screen or in the voice.
- The evening report wraps up the day: a "Month to date / Same day last month / On pace for" row under today's money,
  and the voice says how far ahead of or behind last month you are.

## Update 62: evening report, every workout spoken, afternoon to 7:59 PM (just upload; includes 43–61)
**Evening report, 8 PM to 11:59 PM** (once a day, same rules as the others; opening SRM for the first time at night
plays this instead of a stale morning brief):
1. "Good evening, Ryan. Syncing data now." → "Here's your evening report."
2. **Earnings so far today** (12 AM to now): the same money screen as the morning.
3. **Today's checklist:** "You have X out of Y tasks completed for the day. Still open: …" (open items listed first).
4. **Today's training:** day strain and steps wheels, workout count and active minutes, heart-rate zones across every
   workout, calories, day average / max heart rate, and every workout with its time, minutes, miles, strain, average HR and zone. All of it is spoken.
5. **Tonight:** the bedtime, a countdown to it, and how the sleep need adds up. It's an estimate from your WHOOP data:
   your baseline need, plus half of last night's shortfall, plus about 5 minutes for each strain point above 8, minus today's naps.
   That need is divided by your usual sleep efficiency and counted back from your usual wake-up time.
6. "Rest well." on screen (silent).
**Connections → Play evening report** to test it.

**Afternoon review:** now from 2 to 7:59 PM. The "waiting for approval" screen is gone. Every workout WHOOP detected
today is spoken (sport, minutes, miles for runs, strain, average heart rate, main zone), plus your steps so far.

## Update 61: afternoon review, 2 to 6 PM (just upload; includes 43–60)
Plays once a day between 2 and 6 PM, the first time you're at SRM (same rules as the morning). Same voice, plain lines:
1. "Good afternoon, Ryan. Syncing data now." → "Here's your afternoon update."
2. **Strain & workout:** two wheels: day strain so far and today's workout strain (0–21). Sport, minutes, calories,
   time in heart-rate zones 1–5, average / max heart rate, your recent workout average. No workout yet → "Your day strain is 9.4, with no weightlifting detected for today yet."
3. **Today so far:** gross, new subs, net, month to date vs last month, month pace.
4. **Tasks:** "You have X out of Y tasks completed for the day." Every reminder for today, checked ones included
   (a timed reminder counts as done once its time has passed), with a progress wheel.
5. **Waiting for approval:** the card charges waiting, with the total.
6. "Stay sharp." on screen (silent).
**Connections → Play afternoon review** to test it. WHOOP: tap **Reconnect WHOOP** once so SRM gets the workout permission.

## Update 60: the brief waits for you (just upload; includes 43–59)
- A window left open overnight no longer plays to an empty room (or misses the morning): after 6 AM the brief starts
  the first time you're actually there: SRM on screen and focused, and you open it, click, type, scroll or move the mouse.

## Update 59: money compares with last month, not last week (just upload; includes 43–58)
- Overnight money no longer compares with last week. It shows **month to date vs the same days last month** (a fair
  race: same number of days) and **where the month is headed** ("On pace for $9,800 · last month $8,100").
- Spoken: "Overnight you made $1,244 gross and 14 new subs. Month to date you're at $6,420, 21 percent ahead of last month."

## Update 58: plain voice, spoken "syncing", icons (just upload; includes 43–57)
- While it loads, the voice says "Good morning, Ryan. Syncing data now." Then: "Happy <day>, let's review your overnight data."
- No personality: exact lines only, e.g. "You had a 78 percent recovery and a 91 percent sleep score." Money and day the
  same way. The last screen ("Carpe diem.") is silent.
- The three pills on the first screen are now icons (moon, dollar, calendar) that pop in. Other chips are plain icon + text.

## Update 57: the test plays exactly what tomorrow morning plays (just upload; includes 43–56)
- Fixed: the browser was reusing old voice clips, so a new voice (e.g. Leo) or new lines didn't always play. Every brief
  now fetches freshly spoken lines, and **Play morning brief** waits for your voice choice to save first.

## Update 56: pick the voice, two wheels, WHOOP test (just upload; includes 43–55)
- **Connections → Morning brief → Voice:** all of Grok's voices (Leo by default); **Preview** plays a sample. Saved for
  every device.
- **Connections → WHOOP → Test WHOOP:** shows what SRM can read right now (recovery, sleep, strain) or the exact reason
  it can't. The brief now says why there's no WHOOP data (not connected / couldn't reach / not scored yet).
- Sleep & recovery: **recovery and sleep performance are two wheels side by side**, then hours, the REM / deep / light /
  awake split, HRV, resting heart rate, strain.
- The last scene always says exactly what's on screen: "Carpe diem."

## Update 55: Connections panel (just upload; includes 43–54)
- Moderator now holds only the settings (model, Fanvue %, chatter %, tax). Its footer has **Connections** · **Expenses**.
- **Connections** has everything SRM is plugged into, each with its status and buttons: Fanvue (reconnect), Bank card
  feed (Grok Bot setup), WHOOP (connect), Phone notifications (devices, minute check, send test) and Morning brief
  (play). A red dot on the Connections button means one of them needs attention.

## Update 54: smoother morning brief that starts by itself + Monthly payment for OPEX (just upload; includes 43–53)
- **Morning brief:** no "tap to begin": the greeting writes in while the night is pulled, then it unfolds by itself.
  Lighter animations (no live blur; the dashboard behind is hidden while it plays), each scene rises in piece by piece,
  the day is a timeline that draws down (long titles cut off cleanly, max 5 timed + 4 to-dos, "+N more"), one gradient
  across "Ryan", and it ends on **Carpe diem.** If the browser holds sound back, a small "Tap for sound" pill shows.
  On the Mac web app you can let it talk without a tap: SRM's menu → Settings for this website → Auto-Play → Allow All.
- **Monthly payment (OPEX):** Moderator → Expenses → Verified → open a merchant → the calendar button on a charge →
  pick 2–48 months. The dashboard counts it as equal monthly parts from the day it was paid (e.g. a $1,999 laptop over
  12 months = $166.58 a month), so one big buy doesn't wreck that month's OPEX. **The Google Sheet is never changed**
  (the accountant sees the real charge). Off = counted all at once again.

## Update 52: "Good morning, Ryan" (just upload; includes 43–51)
The first time SRM is opened after 6 AM PT (once a day, on any device) it plays a ~1 minute brief, pulled live:
- **Sleep & recovery (WHOOP):** recovery ring, hours slept vs needed, REM / deep / light / awake split, HRV (vs your
  recent normal), resting heart rate, sleep performance, yesterday's strain.
- **Overnight (12 AM → when you woke up, from WHOOP):** gross, new subs, net after Fanvue + chatters, vs the same window
  last week, best hour, month so far vs last month, expenses waiting.
- **Your day:** timed reminders, to-dos, anytime count.
- Grok writes the lines from the real numbers; Grok's **Leo** voice reads them (one line per scene). Tap to begin
  (browsers need one tap for sound), tap to pause, swipe / arrow keys to skip, ✕ to close. Captions show the words.
- **Moderator → Play morning brief** replays it any time (doesn't use up the day's showing).

**Connect WHOOP (one time):**
1. Go to developer.whoop.com → sign in with your WHOOP account → **Create app**.
   Scopes: read:recovery, read:sleep, read:cycles, read:profile (and offline if listed).
   Redirect URL: `https://<your SRM domain>/api/whoop/callback`.
2. Vercel → SRM → Settings → Environment Variables: `WHOOP_CLIENT_ID` and `WHOOP_CLIENT_SECRET` from that app. Redeploy.
3. SRM → Moderator → **Connect WHOOP** → allow. It says "WHOOP connected ✓".
Uses `XAI_API_KEY` for the lines and the voice (optional `XAI_MORNING_VOICE`, default `leo`).
Files: `src/morning.py`, `src/whoop.py`. New-sub counts per hour start with this update's Fanvue sync.

## Update 51: chart values only while you hold (just upload; includes 43–50)
- On iPhone, the hour / day values on the chart show while your finger is on it (drag to move through them) and
  disappear the moment you lift it. Mouse hover on the Mac is unchanged.

## Update 50: every notification comes once (just upload; includes 43–49)
- Reminders still send ⏳ an hour before and ⚠️ ten minutes before, but each of those goes out exactly once: it's
  marked sent before it's sent, and the every-minute check can't run twice at the same time (Vercel sometimes starts
  the same minute's run twice).
- A charge buzzes once, even when the bank swaps its id going from pending to posted (matched by place, amount, day).
- One subscription per device: an old one left over on the same phone or Mac is replaced, so nothing arrives doubled.

## Update 49: reminder settings behind a cog (just upload; includes 43–48)
- The device count, last check and **Send test** moved off the calendar into a small round ⚙︎ under **Schedule**
  (tap it to open, tap anywhere else to close). A red dot on it means something needs a look.
- Schedule sits higher, centered in the bottom area, with a soft fade behind it; it no longer jumps when pressed.

## Update 48: clearer "notifications off" message (just upload; includes 43–47)
- If Turn on can't get permission, the reason shows inside the calendar (not as a red bar across the dashboard), with
  the Mac steps on a Mac: quit SRM (⌘Q), check System Settings → Notifications → SRM Dashboard, reopen, Turn on.

## Update 47: computer opens to typing (just upload; includes 43–46)
- Schedule on a computer (Mac web app / browser) opens straight to the text box, ready to type; Enter adds it.
  The mic button next to Add still switches to voice. On iPhone it still opens straight to the mic.

## Update 46: expense pushes (just upload; includes 43–45)
- Everything that lands in the bell now also buzzes your phone once, with the real details:
  - 💳 **Amazon · $42.18** — Needs your approval. Tap to review. (opens Expenses)
  - ✅ **OpenAI · $20.00** — Logged to the sheet (merchants you approved before)
  - 💰 **Fanvue payout → Chase** — +$1,234.50 landed
  - Chatting invoices and month-end Fanvue drafts the same way. More than 3 at once → the first 3, then "+N more".
- Checked by the same every-minute job as reminders (no extra cost to speak of). The first run only remembers what's
  already in the bell, so nothing old gets replayed. Logic: `src/expense_push.py`.

## Update 45: rocket-fast voice scheduling, instant calendar (just upload; includes 43 + 44)
- **Voice:** opens straight to the mic and keeps listening through pauses, ums and thinking. Only your tap on the mic
  ends it. Then a live bar fills while it works. Hearing it and reading it happen in one call now (one wait, not two).
- **Fast + smart reading:** Grok runs on its lightest thinking setting (reasoning effort "low"; model `grok-4.7`, falls
  back to `grok-4.6`; set `XAI_CAL_MODEL` on Vercel to pick another). It pulls out only the task, the day ("tomorrow",
  "tuesday next week", "the 14th") and the time if one was said, ignores filler, and takes your last word when you
  correct yourself ("at 3, no, 4"). No time said → a to-do for that day; no day → Anytime.
- **Calendar speed:** all upcoming items load once, so switching days is instant (no server wait per tap). No more live
  blur behind the panel, the background animations rest while it's open, and taps get instant press feedback.

## Update 44: stays live while open, steady little universe (just upload; includes update 43)
- **Quiet refresh:** while SRM is open and on screen, every 2 minutes it does what opening the app does (Fanvue,
  bank, sheet), with nothing shown. It only redraws when a number changed (no chart re-animation), and waits while
  you're typing or hovering the chart. Minimized / hidden / asleep: nothing runs; it catches up when you come back.
  Replaces the old bank-only check, and Fanvue is pulled at most once per 90 seconds across all your devices.
- **Universe icon:** the planets are placed from the clock instead of a looping animation, so they can't jump or restart.

## Update 43: mic + reminder fixes you can see (just upload)
- **Mic:** an iPhone Home Screen app has no Microphone switch of its own (that's why Settings → SRM only shows
  Notifications). It uses Safari's: **Settings → Apps → Safari → Microphone → Ask** (or Allow). When that's on Deny,
  iOS refuses without asking. The Schedule screen now says exactly why the mic didn't start (blocked, busy in another
  app like Wispr Flow, none found) and what to do. Tapping × still switches to typing / keyboard dictation.
- **Reminders:** the calendar's bottom line shows how many devices get reminders, when the every-minute check last ran,
  and what Apple answered for the last push. **Send test** sends the real ⏳ and ⚠️ messages so you see what's coming.
  If it says the check isn't running: Vercel → SRM → Settings → Cron Jobs must show `/api/agenda/tick` enabled.

## Update 42: mic stays listening, bell · calendar · lock (just upload)
- Schedule opens listening and stays that way until you've spoken and paused (about 2 seconds) or tap the mic.
  The mic's start-up click and room noise no longer end it early. If the mic is blocked, it says so and stays put.
- Top right order: notifications, calendar, Moderator.

## Update 41: calendar + phone reminders, Moderator as an icon

**After uploading, three steps:**
1. **Vercel → your SRM project → Settings → Environment Variables:** add `XAI_API_KEY` (the same xAI key Autothot uses).
   It reads what you say or type ("tomorrow at 3 call the bank") and turns your voice into text. Then **Redeploy**.
2. **Optional:** add `CRON_SECRET` (any long random text). Vercel then signs its every-minute reminder check, so nobody
   else can trigger it. It works without it too (the check only sends reminders that are due).
3. **On your iPhone:** open SRM from the Home Screen icon → calendar icon (top right) → **Turn on** → Allow.
   You get a test notification. For buzz-only (no ring), keep the phone on silent with "Play Haptics in Silent Mode" on.

**What's new**
- **Calendar** (calendar icon, top right). Opens on Today:
  - **Scheduled**: things at a time, with a time rail (yellow within the hour, red within 30 minutes).
  - **To do today**: things for the day, tick them off. Unfinished ones carry over to the next day.
  - **Anytime**: to-dos with no day.
  - Week strip Mon–Sun for this week; tap the date at the top for the month. Past days and old months are cleared by
    themselves, so it stays fast.
- **Schedule**: opens listening. Talk, and it stops after you pause (or tap the mic). The thin × under the mic switches
  to typing (your Wispr Flow keyboard works there). You see what it understood and tap **Add**.
- **Reminders on your phone**: ⏳ about an hour before ("⏳ Call the bank · In 1 hour · 3:00 PM") and ⚠️ ten minutes
  before. One buzz each. In the app, a yellow banner shows anything in the next hour; red within 30 minutes.
- **Moderator** is now a round lock icon next to the bell.

Files: `agenda.py` (calendar), `webpush.py` (phone notifications), `server.py` (routes, /sw.js), `static/index.html`,
`vercel.json` (every-minute check, needs Vercel Pro), `requirements.txt` / `pyproject.toml` (adds `cryptography`).

## Update 39: card feed hardened (includes 36, 37 and 38, just upload)

A full audit of the Grok Bot card feed. Grok Bot reads your bank and transcribes it, so on some runs it may reword a description, shift a date, leave out an id, mislabel pending/posted or repeat a line. The dashboard now copes with all of that:

- **Matching:** every listed transaction is matched to what's already stored with one optimal assignment (Hungarian algorithm), not one at a time. It uses everything the dashboard has seen: bank ids, every name and date a charge was listed under, and abbreviations (AMZN = AMAZON). Identical charges ($50 top-ups a day apart) stay separate.
- **Pending → posted:** the same record and sheet row move to the posted amount (tips, hotel holds and gas pumps included). Leftover pending lines and mislabels are ignored.
- **Declines:** a pending charge is taken out only after 3 complete sweeps over 12+ hours without it. An empty or wrong-account sweep never takes anything out, and the dashboard warns you about it.
- **Refunds** on the card now come into Expenses → New as negative amounts (✓ lowers your costs). Your Apple trade-in refund will land here.
- **Duplicate warning:** a charge that looks like another one (same place, same or similar amount, within 3 days) says so on its card, so a repeat can't slip into the sheet. If it's pending vs posted, the card explains which one to keep.
- **Approving while a sweep runs:** ✓ and ✕ never collide with a sweep. If you tap ✓ on a pending charge that posted a second earlier, the posted one is approved.
- **Grok Bot's instructions** now give exact field rules, and the key goes in a header, never a URL. The instructions update themselves, so there's nothing to re-paste.

Tested by simulating 270 months of bank activity: pending→posted, tips, holds, declines, twin charges, refunds and Fanvue deposits, run through deliberately sloppy "AI" output:
- **Results:** in every month, no charge was lost, nothing stayed stuck as pending, and every extra card was flagged before it could reach the sheet.
- **Flagged look-alikes you'd still see in Expenses → New:**
  - about 1 every 5 months when Grok Bot can see the bank's transaction ids;
  - about 1 a month when it can't.
- The code was also reviewed by a separate agent. All 7 defects it found are fixed and re-tested.

---

## Update 38: profit on the Income tab (just upload)

The Income tab's BUSINESS INCOME table now shows what each month actually left you:
Month | Fanvue gross | Fanvue fee | Net payout | **Chatting** | **OPEX** | **Net profit** | Status.
- Net payout = what Fanvue pays out (gross minus its fee).
- Net profit = Net payout minus Chatting and OPEX, before tax. It matches the dashboard's Net for that month.
- The FANVUE PAYOUTS table moved right (it starts at column J now). Nothing in it changed.
It rewrites itself on the next dashboard load. Approving an expense or invoice updates it on the following load.

---

## Update 37: card feed through Grok Bot (includes update 36, just upload)

Plaid closed this app's Plaid account on Oct 4, so card 0029 now comes in through a **Grok Bot routine**. Grok Bot reads Chase through its own Finance (Plaid) link and sends the last 14 days to the dashboard every 2 hours. Everything after that works like before.

**Set it up once (2 minutes):**
1. Upload this zip and wait for Vercel to show **Ready**.
2. Open the dashboard → **Moderator** → **Bank** → **Set up card feed (Grok Bot)**.
3. Tap **Copy Grok Bot setup**, paste it into Grok Bot and send. It makes the "SRM card sweep" routine and runs it once.
4. Within a minute, Moderator shows "✓ Grok Bot · Chase ••0029 · swept just now", and new charges appear in **Expenses → New**.

**How it behaves:**
- Pending charges come in marked **pending** (rows in the sheet get " · pending"). When the bank posts one, the same row is updated to the posted amount (tips included), never added twice.
- A pending charge the bank drops (declined, hotel or gas hold released) comes back out after two sweeps in a row without it.
- Charges the Plaid feed already brought in are recognised, not repeated. Fanvue MassPay deposits still land in Expenses → New for the Income tab.
- When Apple charges the card for the laptop, it's recognised as the row already in the sheet and you won't be asked about it.
- If Grok Bot misses sweeps for 6 hours, or tells the dashboard it can't reach Chase, a warning shows at the top.
- **New key** in Moderator cuts off the old key. Then copy the setup into Grok Bot again.

---

## Update 36: one weekly agency card + new laptop logged (just upload)

- **Fixed the double "Fanvue payout to Coinbase" card.** Each week there's now only **Chatting agency · <week>**. Its ✓ writes the invoice to the Chatting list **and** logs that week's Fanvue payout to Coinbase in the Income tab (same amount). The extra Coinbase card and its bell note are cleared on the next load.
- **New laptop logged.** On the next load the dashboard adds this row to the OPEX list once: 2026-10-04 · Apple – MacBook Pro 14-inch M5 Pro (order W1817786310) · Hardware · $2,750.55 (price + tax). The $645 trade-in refund isn't in yet; it gets logged when Apple pays it.
- **Plaid account closed by Plaid (Oct 4).** Replaced by the Grok Bot card feed in update 37.

---

---

## Update 4: app icon (just upload)

Same upload as always. Adds the twin-bars icon for the browser tab and for your iPhone home screen. It also includes everything from update 3, so if you skipped that one, this covers both.

To put it on your iPhone: open the site in **Safari** → **Share** → **Add to Home Screen**. If you'd already added it before, delete the old one and add it again so the new icon shows.

---

## Update 3: just upload

Unzip, then GitHub **Add file → Upload files** → drag in `README.md` and the `src` folder → **Commit changes**. Nothing to delete or set up.

What changed:
- **Expenses → Verified** is one list now (no Rolling / One-time). It's split into **Business expenses** and **Chatter pay**, one row per merchant with its total, number of charges, last charge and a bar for its share. Tap a merchant to see every charge; the ✕ next to a charge trashes just that one (Recover it from Trash).
- A sheet item written like **"iPhone 12 (x3 units)"** counts as 3 charges and shows "3 × $235.00".
- New **Opex exp** box next to Chatter cut and Fanvue cut (tap it to open Expenses). On a computer the five boxes sit in one row; on a phone Net and Gross sit on top and the three expense boxes share the row under them.

---

## Update 2: bank feed (Plaid), do these first

You already did the original setup below. For this update:

### A. Let the robot write to the sheet
Open the **SRM Expenses** sheet → **Share** → find `srm-dashboard@autothot.iam.gserviceaccount.com` → change **Viewer** to **Editor** → **Save**.

### B. Get your Plaid keys (about 10 minutes)
1. Go to **dashboard.plaid.com** and sign up. Pick the free **Trial** plan and finish the identity check.
2. If Plaid asks for company info or an **application profile**, fill it in (app name "SRM Dashboard" is fine). Chase won't connect to apps with an empty profile.
3. Open **Developers → Keys** (sometimes under Team Settings). Copy the **client_id** and the **Production secret**.
4. In Vercel → **srm-dashboard** → **Settings** → **Environment Variables**, add two, both as **Secret**:
   - `PLAID_CLIENT_ID` = the client_id
   - `PLAID_SECRET` = the Production secret

### C. Upload this zip
Same as last time: unzip → GitHub **Add file → Upload files** → drag in `README.md` and the `src` folder → **Commit changes**. Nothing needs deleting this time.

### D. Connect the card
1. When Vercel shows the new deployment as **Ready**, open the dashboard on a computer browser.
2. **Moderator** → **Connect bank** → Plaid's window opens → pick **Chase** → log in → select the card ending **0029** → **Continue**.
3. The Bank line in Moderator turns to "✓ Chase ••0029".

### E. Turn off Grok's card sweep
From now on the dashboard pulls card 0029 itself. If Grok keeps adding card charges to the sheet, they'll count twice. Keep using the sheet (by hand or Grok) for things that don't go through the card: Ryan's invoices, chatter payroll, anything paid another way.

### How the bank feed behaves
- Every page load checks Plaid for new **posted** charges on card 0029. Charges show up once the bank posts them, usually 1–2 days after you buy.
- New charges wait in **Expenses → New**. **✓** writes the row into your sheet right away, just above the Total line, and stretches the Total to include it. **✕** sends it to **Trash** (you can Recover it).
- It remembers your answer per merchant: after one ✓ for Atlas Cloud, future Atlas charges go into the sheet automatically; after one ✕ for a coffee shop, future ones are skipped automatically. Recovering something from Trash flips that merchant back to "add automatically".
- Rows it writes copy how your sheet already describes that merchant (for example "Atlas Cloud – Manual Top-up"). New merchants use the bank's name and the category "Software/AI"; edit either in the sheet if you like.
- It writes the bank's transaction ID in a **Bank ID** column. Leave that column alone; it's how a charge is never added twice.
- It only looks at charges posted after the last date that was in the sheet when you connected, so nothing Grok already logged comes in again.
- If Chase ever asks you to log in again, the Bank line in Moderator says so. Click it, log in, done.

---

## Original setup (already done, kept for reference)

Do steps 1–3 in Vercel **before** uploading, so the new version works the moment it goes live.

### Step 1: Add storage in Vercel (about 2 minutes)

The old site lost its Fanvue login and history every time Vercel restarted it. This fixes that.

1. Go to vercel.com and open the **srm-dashboard** project.
2. Click the **Storage** tab at the top.
3. Click **Create Database** (or **Browse Marketplace**) and pick **Upstash** → **Upstash for Redis**.
4. Choose the **Free** plan and any region in the US West. Name it `srm`. Click **Create**.
5. When it asks which project to connect, pick **srm-dashboard**, leave every environment ticked, and click **Connect**.

That's it. Vercel adds the connection settings automatically.

### Step 2: Let the site read your Google Sheet (about 10 minutes)

This creates a "robot" Google user that can only *view* your SRM Expenses sheet.

1. Go to **console.cloud.google.com** and sign in with any Google account you own. Your personal Gmail works.
2. Click the project picker at the top left → **New Project** → name it `srm-dashboard` → **Create**. Make sure it's selected afterwards.
3. In the search bar at the top, type **Google Sheets API**, click it, and click **Enable**.
4. In the search bar, type **Service accounts** and open it. Click **+ Create service account**, name it `srm-dashboard`, click **Create and continue**, then click **Done** (skip the optional steps).
5. Click the new service account in the list. Copy its **email** (it ends in `.iam.gserviceaccount.com`).
6. Open the **Keys** tab → **Add key** → **Create new key** → **JSON** → **Create**. A `.json` file downloads.
7. Open your **SRM Expenses** Google Sheet → **Share** → paste the robot email → set it to **Editor** → untick "Notify people" → **Share**.
8. Open the downloaded `.json` file in a plain text editor (Mac: right-click → Open With → TextEdit). Select everything and copy it.
9. In Vercel: **srm-dashboard** → **Settings** → **Environment Variables** → add:
   - Key: `GOOGLE_SERVICE_ACCOUNT_JSON`
   - Value: paste what you copied
   - Click **Save**.
10. Delete the downloaded `.json` file from your Downloads folder. It's a key, so don't leave copies around.

If step 6 says key creation is disabled, start again at step 1 signed in with your personal Gmail instead of the business account.

### Step 3: Check your other Vercel variables

Still in **Settings → Environment Variables**:

| Variable | What to do |
|---|---|
| `DASH_PASSWORD` | **Must exist.** The old built-in fallback password (`srm-private`) has been removed, so without this you can't log in. Make it something long. |
| `FANVUE_CLIENT_ID` | Keep. |
| `FANVUE_CLIENT_SECRET` | Keep. |
| `FANVUE_REDIRECT_URI` | Keep whatever is there. It must match the redirect URL saved in your Fanvue app. |
| `FANVUE_REFRESH_TOKEN` | **Delete it if it's there.** Fanvue issues a new key every time it refreshes, and re-using an old one can log you out of the connection. |

### Step 4: Upload the new code

1. Unzip `srm-dashboard-update.zip`. You'll get a folder called `srm-dashboard-main`.
2. Go to **github.com/SRManagement/srm-dashboard** → **Add file** → **Upload files**.
3. Open the unzipped `srm-dashboard-main` folder and drag **everything inside it** (`README.md` and the `src` folder) onto the GitHub page.
4. Choose **Commit directly to the main branch** → **Commit changes**.

### Step 5: Delete the old files (uploads can't delete)

On GitHub, open each item below. For a **folder**, click the **…** menu at the top right of the folder page → **Delete directory**. For a **file**, click the **…** menu (or trash icon) → **Delete file**. Then **Commit changes**. (If you don't see "Delete directory", open each file in the folder and delete them one by one.)

**Required:**
- `src/api` folder. Those old files would take over the Fanvue login and break it.

**Recommended** (old snapshot data the site no longer uses, including your card charges):
- `src/data` folder

**Optional cleanup** (old duplicates and notes; Vercel ignores them since it only builds `src`):
- In `src`: `FULL_PACK.md`, `START_HERE.md`, `Procfile`, `render.yaml`
- At the top level: the `api`, `data` and `static` folders, plus `server.py`, `requirements.txt`, `pyproject.toml`, `vercel.json`, `Procfile`, `render.yaml`, `FULL_PACK.md`, `HEAL.md`, `START_HERE.md`

### Step 6: First visit

1. Wait for Vercel to show the green check on the newest deployment, then open the site.
2. Enter your password. The site sends you to Fanvue to log in **once**, because the new storage starts empty.
3. Back on the dashboard, the loading balls say "Pulling Fanvue history" for a minute or so while it downloads everything since April. This only happens the first time.
4. Sanity check: set the range to **All time** and compare **Gross total** with the all-time gross on Fanvue's own Insights page. They should match, give or take refunds.
5. Open **Expenses** and check the Verified tab looks like your sheet.

If anything isn't set up right, a red banner at the top of the dashboard says exactly what's missing.

---

## How the numbers work

For any date range:

- **Gross**: what fans paid (from Fanvue).
- **Fanvue cut**: Gross × Fanvue % (Moderator, default 20%).
- **Chatter cut**:
  - Weeks with a real agency invoice in the sheet: the invoice amount, spread across that Monday–Sunday week by each day's Messages + Tips, so a range like "Today" gets its fair share.
  - Weeks with no invoice yet (the current week): (Messages + Tips gross) × (1 − Fanvue %) × Chatter %. That's 25% for weeks ending Aug 30, 2026 or later, and 20% before.
  - "Chatter Payroll" payments count on the day they were paid.
- **Opex**: every expense row in the sheet that isn't chatter pay (minus anything you trashed in the dashboard).
- **Tax**: only when the Tax switch is on. It's a % of what's left. "Calculate" estimates the % from this year's profit (2026 federal + California + self-employment).
- **Net** = Gross − Fanvue − Chatter − Opex − Tax.

The chart's **Net** is simpler on purpose: Gross − Fanvue cut − the chatter % formula. Invoices and expenses can't be split by the hour, so they appear only in the totals.

## Files

| File | What it does |
|---|---|
| `src/server.py` | Web routes and password login |
| `src/calc.py` | All the money math |
| `src/fanvue.py` | Fanvue login and earnings sync |
| `src/sheet.py` | Reads expenses from the Google Sheet and writes approved bank charges into it |
| `src/bank.py` | Card charges from Plaid |
| `src/store.py` | Saved data (Upstash Redis) |
| `src/static/index.html` | The whole page |
| `src/agenda.py` | Calendar, reminders and the every-minute check |
| `src/webpush.py` | Phone push notifications |
| `src/expense_push.py` | Expense pushes (from the bell) |
| `src/morning.py` | The morning brief |
| `src/whoop.py` | WHOOP band (sleep, recovery, strain) |
