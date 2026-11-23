# Changelog

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
