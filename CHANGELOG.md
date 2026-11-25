# Changelog

## 2026.11.25.9

- 🩹 Fix a day going missing from a calendar roster: the day next to the selected one is often
  rendered without its own date link, which dropped it entirely (so tomorrow's shift could vanish).
  Such a day is now dated from its neighbours and kept.

## 2026.11.25.8

- 🔵 The shift browser gained a **Today** button that jumps straight back to today (or the next
  shift) after paging around.
- 🗓️ A day the portal lists only with a note ("no information for this day yet") stays on the
  calendar, so today is never missing from it; only an empty parser artefact is left out.

## 2026.11.25.7

- ◀▶ The **shift-detail card is now a browser**: arrows page through the coming days, each shift
  shown with its place, times and full leg table, a day off as such. The roster sensor carries each
  day's legs so the card can leaf through them.

## 2026.11.25.6

- 🧩 The dashboard cards size to their content in the new **sections** dashboard layout, so the fact
  tiles of the shift card and long tables/lists are no longer clipped at the bottom.

## 2026.11.25.5

- 🗒️ The roster card drops the code from an absence, like the calendar does: **Krank** and **Frei**
  instead of "Krank (k)" and "Frei (R)", while a real shift keeps its number and an unknown entry
  keeps its own code.

## 2026.11.25.4

- 💼 The accounts card is tidier: a tile the portal does not provide (weekend points on a portal
  without them) is **hidden** instead of showing an empty "–", it gained a **Time account today**
  tile in hours:minutes, and the monthly planned-hours tile works again.
- 🗒️ The roster card shows an unrecognised entry by its own code (e.g. **SF Neu**) rather than
  "Unknown (SF Neu)", matching the calendar.

## 2026.11.25.3

- 🗓️ Next month's shifts are detailed on a **navigation-based portal**: the roster is opened on a
  shift's own day (roster.aspx?YYYY-MM-DD) before its detail page is read, exactly as clicking
  "next" in the browser does — so the shifts of the following month get their legs, not only the
  current month. Covered by a regression test against a portal that mimics this behaviour.

## 2026.11.25.2

- ⏱️ Time accounts now read in the portal's own **hours:minutes** form: the accounts card shows the
  overtime as **−10:17**, not the confusing decimal **−10.3 h**. The exact value is also on the
  overtime and time-account sensors as a `balance` attribute.
- 🗓️ An unrecognised roster entry now keeps its own code in the calendar (e.g. **SF Neu**) instead
  of the generic "Dienstplan", and an empty placeholder day no longer becomes an event.
- 🔎 Next month's shifts: the month is re-opened before its shifts are read, and a shift whose detail
  page carries no legs is logged, so a missing breakdown can be traced.

## 2026.11.25.1

- 🧾 New **Perdis: shift detail** dashboard card: the next shift broken into its legs as a real
  table — reporting point, time, line, course and relief direction, with the breaks called out.
  Its visual editor lets you hide the course or relief column and the breaks. The legs now also
  ride on the **next shift** sensor as a `legs` attribute, for your own templates and cards.

## 2026.11.25

- 🗓️ Next month's shifts are now detailed again: a sick day (which the roster still lists with
  times) no longer counts as a "no detail page" and no longer stops the breakdown of the shifts
  that follow it.
- 🧾 An absence now reads as just its name in the calendar: "Krank k" and "Krank (k)" both become
  plain **Krank**, and a day off is **Frei** without its code. The duty number and lines stay on
  the real shifts.
- 🔔 Friendlier roster-change messages, e.g. **"Frei eingetragen für Montag, 30.11."** instead of
  "aus unknown wurde frei", each with the full weekday and date.
- 🏷️ A known operator names the account **"&lt;short&gt; - &lt;personnel number&gt;"** (e.g.
  `VGF - 12345`); a portal added by hand keeps the personnel number and surname.
- 🧰 Even wider Home Assistant support (verified down to **2023.8**): graceful fallbacks for the
  service responses and validation errors, the re-authentication, the device info, the frozen
  entity descriptions, the operator dropdown sorting and the coordinator's own config entry.

## 2026.11.24.5

- ⏱️ New **Time account today** sensor, read from the daily-values page ("Tageswerte"): the day's
  balance at a glance, with the planned and worked hours, the running account and the last ten days
  in its attributes. Portals that do not offer the page simply do not get the sensor.
- 🧮 Upcoming shifts are now broken down for the **whole roster ahead**, next month included — not
  only the first few days. A shift keeps its breakdown until it actually changes, so only genuinely
  new days ever cost an extra request.
- 📖 The calendar reads a shift more clearly: every leg leads with its **place and time**, then its
  **line and course**, with the relief direction in parentheses (e.g. `Hbf 10:32–14:32 · Line 21 ·
  Course 11 (+/-)`). Breaks are shown as breaks, and the old summary line at the top is gone.
- 🧰 Runs on **much older Home Assistant versions** (down to 2024.3): the time-zone lookup, the
  options section, the card path, the coordinator setup and the re-authentication all fall back
  gracefully on cores that predate the newer APIs.
- 🃏 The readme now explains what to do when the **dashboard cards do not appear** in the card
  picker — almost always a cached frontend that a reload clears.

## 2026.11.24.4

- 🔀 Each shift leg now shows its **relief direction** (the `+/-` marker from the detail page), so a
  driver sees where they take a vehicle over and where they hand it off.
- 👀 Duty swaps are **read-only** for now: the **Open duty swaps** sensor and the **Perdis: duty
  swaps** card list the open offers and the request window. Entering and answering swaps from Home
  Assistant will follow once it is fully tested against a live portal.

## 2026.11.24.3

- 🔄 **Duty swaps** on portals that offer them: a new **Open duty swaps** sensor lists the open
  offers and the period new requests may cover, and a new **Perdis: duty swaps** Lovelace card
  shows them with one-tap **Accept**, **Reject** and **Withdraw**, plus a small form to **request**
  a swap (with a **Check** that only validates it first).
- 🛠️ New services `perdis_roster.swap_request`, `swap_accept`, `swap_reject` and `swap_withdraw`
  for automations and scripts. Every swap is only ever submitted when you trigger it; nothing is
  sent to the portal on its own. Portals without a swap page simply do not get the sensor or card.

## 2026.11.24.2

- 🗓️ The month calendar is read more completely: each day's date comes from its own link, the shift
  times, reporting point and paid hours come straight from the day's tooltip, and the faded days of
  the neighbouring months are ignored. Absence codes (free day, vacation, sick) are recognised.
- 🏖️ Remaining vacation is read from the leave page's summary ("Restanspruch"), including the
  layout that lists several leave accounts side by side in one row.

## 2026.11.24.1

- 🏷️ The account is now named "&lt;personnel number&gt; - &lt;surname&gt;" (e.g. `12345 - Mustermann`),
  read from the login and the portal header, in whichever order the header writes the name.
- 🗂️ The portal pages are matched to the standard WebComm filenames and more menu labels
  (`Summen`, `Tageswerte`, `Urlaubswunsch` …), so page discovery works on more portals.
- ⏱️ The time-account balance is also read when the accounts page lists it as a
  "Konto / Von / Bis / Wert" table with the value in the last column.

## 2026.11.24

- 🧩 The calendar now always shows the leg-by-leg breakdown of a shift (preparation, driving legs
  with their line, breaks), not only its start and end. The detail page is read for every working
  day in the window that still lacks the breakdown, even on portals whose month roster already
  shows the times. Portals that serve no detail page are detected and left alone.

## 2026.11.23.5

- 🕐 Exact shift times, reporting points, lines and a leg-by-leg breakdown are now read from each
  shift's own detail page, not only the duty number from the month roster. The calendar shows the
  real start and end and the legs; a new "Fetch exact shift times for this many days ahead" option
  (default 10, 0 = off) bounds how many detail pages are fetched.
- 🗓️ The month roster is read even when a day cell shows only a code (no tooltip), and the month is
  taken from the page heading so number-only calendars are dated correctly.
- 🔔 Notifications: assign the employee as a **person** entity and set a **notification service**
  (e.g. `notify.mobile_app_phone`) or any `domain.service`/script to call on roster changes. The
  `perdis_roster_event` already lets automations run any custom action.

## 2026.11.23.4

- 🏷️ The account is now named "<transit company> - <employee name>" (read from the portal header),
  instead of the personnel number; it falls back to the number when the portal shows no name.

## 2026.11.23.3

- 🚌 Added the VGF Frankfurt and üstra Hannover WebComm portals to the operator list, both verified.
- 🔧 A manually entered address no longer needs the `/WebComm/` folder: it is appended automatically.
- 🔎 Only sensors a portal can actually fill are created. At setup the integration probes which
  pages the portal serves and which account values it returns, and leaves out the rest, so a portal
  that does not expose weekend points or time accounts no longer shows them as permanently unknown.
- 🗓️ The roster is now read from portals that render it as an ASP.NET calendar (the shift in each
  day's tooltip), not only from table layouts, and the canonical WebComm page names
  (`roster.aspx`, `balances.aspx`, `planbals.aspx`) are tried when the menu labels are not
  recognised. This fixes portals that previously returned no data at all.

## 2026.11.23.2

- 🆔 Renamed the integration domain from `perdis` to `perdis_roster` for a clearer, less
  product-bound identifier. This only affects fresh installs; there is no released version with the
  old domain to migrate from.

## 2026.11.23.1

- 🃏 The dashboard cards are now fully configurable, each with a grouped visual editor (Content,
  Appearance, Behaviour): account, title, header icon, accent colour and a full Lovelace tap
  action on every card.
  - Shift card: choose which facts (wake up, leave, paid, rest) to show, and toggle the location,
    lines, countdown and progress bar.
  - Roster card: hide day types, switch off the week grouping, the tags, the location, the lines
    or the today highlight.
  - Accounts card: pick and order the tiles (now including planned hours of the month) and set a
    fixed number of columns.
- 💅 Fresher card look: an accent-tinted hero block on the shift card, softer tiles and hover
  feedback, all theme-aware in light and dark.
- 🩹 Compatibility with Home Assistant 2026.9 and newer: the calendar entity registers again, and
  the device is looked up without the deprecated `device_registry.async_get_device`.


## 2026.11.23

First release of **Perdis Duty Roster**, an unofficial integration for the duty rosters of
MOBILE-PERDIS portals (INIT does not document their interfaces).

- 🚌 Setup with a list of transit companies whose WebComm portal was checked (BOGESTRA, DVG
  Duisburg, RegioBus Hannover, Rheinbahn, rnv, Salzburg AG, Transdev NL, WSW) or any address
  copied from the browser.
- 🔐 WebComm sign-in like a browser: ASP.NET cookie check, view state, automatic renewal of an
  expired session, a repair notice when the password changed.
- 🧭 The roster, account and weekend points pages are found in the portal menu; columns are
  recognised by their header text in German, English and Dutch; times past midnight and split
  shifts are handled; later months are read through the page's "next" button.
- 📱 Experimental AppComm (Perdis mobile) client for the JSON service behind the app, with
  configurable endpoints and a flexible reader for its answers.
- 📊 Sensors for the next shift, wake-up and leave-home time, rest before the next shift, today and
  tomorrow, the next day off, working days in a row, free weekends, planned hours, overtime,
  vacation, weekend points and the distance to the group average.
- 🔔 Roster changes are detected, kept for 14 days and reported as a notification and an event.
- ⚡ Device triggers and `perdis_event` for wake up, leave home, shift start and end, free weekend
  and roster changes, set as timers to the second.
- 🗓️ Calendar with every shift and day off.
- 🃏 Three dashboard cards (next shift, roster, accounts) that register themselves, with a visual
  editor, in German and English.
- 🛠️ Services `perdis.refresh` and `perdis.get_duties`, diagnostics without personal data.
- 💾 The last roster is cached, survives portal maintenance and is only written when it changed.
- 🪶 No extra Python packages: HTML is read with the standard library.
- 🌍 English and German translations.
