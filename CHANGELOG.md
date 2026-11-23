# Changelog

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
