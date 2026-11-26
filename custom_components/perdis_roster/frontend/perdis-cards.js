/**
 * Dashboard cards of the Perdis Duty Roster integration.
 *
 *   perdis-card               all-in-one: a tab bar over the cards below, mobile-first like the app
 *   perdis-shift-card         the next shift: times, place, countdown, wake-up and leave-home time
 *   perdis-roster-card        the coming days, grouped by week, with days off and changes marked
 *   perdis-accounts-card      overtime, vacation, weekend points and free weekends at a glance
 *   perdis-shift-detail-card  page through the shifts, each broken into its legs as a table
 *   perdis-calendar-card      a month calendar of the roster, entity found automatically
 *   perdis-swap-card          the open duty swaps the portal lists
 *
 * The integration loads this file on every dashboard, so the cards appear in the card picker
 * without adding a resource. They work without any configuration: without a `device_id` they show
 * the first Perdis account, and the entities of an account are found by their `perdis_role`
 * attribute, so renaming an entity never breaks a card.
 *
 * Every card has a visual editor that exposes its options (account, title, icon, accent colour,
 * tap action, and which parts to show). Plain web components without any library keep the file
 * small and independent of the frontend version of Home Assistant.
 */

const VERSION = "2026.11.26.6";
const DOMAIN = "perdis_roster";

// --- Texts ---------------------------------------------------------------------------------

const TEXTS = {
  en: {
    nextShift: "Next shift",
    roster: "Roster",
    accounts: "Accounts",
    running: "Running",
    startsIn: "starts in",
    endsIn: "ends in",
    wakeUp: "Wake up",
    leaveHome: "Leave",
    rest: "Rest before",
    paidHours: "Paid",
    shortRest: "Short rest",
    noShift: "No upcoming shift in your roster.",
    noAccount: "No Perdis account found. Set up the Perdis Duty Roster integration first.",
    noDays: "The roster is empty for the coming days.",
    today: "Today",
    tomorrow: "Tomorrow",
    close: "Close",
    week: "Week",
    changed: "changed",
    split: "split",
    hours: "h",
    days: "days",
    clock: "",
    updated: "Updated", justNow: "just now", updating: "Updating…", refreshRoster: "Refresh roster",
    units: { day: ["day", "days"], hour: ["hour", "hours"], minute: ["minute", "minutes"] },
    unitsIn: { day: ["day", "days"], hour: ["hour", "hours"], minute: ["minute", "minutes"] },
    points: "pts",
    overtime: "Overtime balance",
    vacation: "Vacation left",
    planned: "planned",
    weekendPoints: "Weekend points",
    average: "average",
    freeWeekends: "Free weekends",
    nextFreeWeekend: "next",
    plannedWeek: "Planned this week",
    plannedMonth: "Planned this month",
    offline: "Portal offline – showing the saved roster",
    types: {
      work: "Duty", reserve: "Reserve", training: "Training", free: "Day off", vacation: "Vacation",
      compensation: "Time off", sick: "Sick", unknown: "Unknown",
    },
    categories: { early: "Early", day: "Day", late: "Late", night: "Night", split: "Split" },
    facts: {
      wake_up: "Wake up", leave_home: "Leave", paid: "Paid hours", rest: "Rest before",
      duration: "Shift length", breaks: "Breaks",
    },
    tiles: {
      overtime: "Overtime balance", daily: "Time account today", vacation: "Vacation left",
      weekend_points: "Weekend points", free_weekends: "Free weekends",
      planned_week: "Planned this week", planned_month: "Planned this month",
    },
    shiftDetail: {
      title: "Shift detail",
      place: "Place", time: "Time", line: "Line", course: "Course", direction: "Relief",
      break: "Break", min: "min", noDetail: "No leg-by-leg breakdown for this shift yet.", dayOff: "No shift on this day.",
    },
    calendar: "Calendar",
    swaps: "Swaps",
    allInOne: "All-in-one",
    views: { dayGridMonth: "Month", listWeek: "Week list", listMonth: "Month list" },
    editor: {
      // Common
      device_id: "Perdis account",
      title: "Title",
      icon: "Header icon",
      show_header: "Show the header",
      accent: "Accent colour",
      tap_action: "Tap action",
      // Shift card
      show_countdown: "Show the countdown",
      show_progress: "Show the progress bar while on duty",
      show_lines: "Show the lines",
      show_location: "Show the reporting point",
      show_facts: "Facts to show",
      // Roster card
      days: "Days to show",
      show_days_off: "Show days off",
      compact: "Compact rows",
      group_by_week: "Group by calendar week",
      highlight_today: "Highlight today",
      show_tags: "Show the tags (changed, split, shift type)",
      hide_types: "Hide these day types",
      // Accounts card
      show_tiles: "Tiles to show",
      columns: "Columns (0 = automatic)",
      // Shift detail card
      show_course: "Show the course column",
      show_relief: "Show the relief column",
      show_breaks: "Show the breaks",
      // Calendar card
      initial_view: "Start view",
      tabs: "Tabs to show",
      logo: "Logo (image address)",
      // Section headers
      sec_content: "Content",
      sec_appearance: "Appearance",
      sec_behavior: "Behaviour",
    },
    helper: {
      device_id: "Leave empty for the first account.",
      title: "Leave empty for the default title.",
      icon: "Leave empty for the default icon.",
      accent: "Leave empty to colour the card by the shift type.",
      hide_types: "Leave empty to show every day.",
      logo: "Leave empty for the operator's name badge. Example: /local/my-logo.png",
    },
  },
  de: {
    nextShift: "Nächster Dienst",
    roster: "Dienstplan",
    accounts: "Konten",
    running: "Läuft",
    startsIn: "beginnt in",
    endsIn: "endet in",
    wakeUp: "Aufstehen",
    leaveHome: "Losfahren",
    rest: "Ruhezeit davor",
    paidHours: "Bezahlt",
    shortRest: "Verkürzte Ruhezeit",
    noShift: "Kein kommender Dienst im Dienstplan.",
    noAccount: "Kein Perdis-Konto gefunden. Richte zuerst die Integration Perdis Duty Roster ein.",
    noDays: "Für die kommenden Tage ist der Dienstplan leer.",
    today: "Heute",
    tomorrow: "Morgen",
    close: "Schließen",
    week: "KW",
    changed: "geändert",
    split: "geteilt",
    hours: "Std.",
    days: "Tage",
    clock: "Uhr",
    updated: "Aktualisiert", justNow: "gerade eben", updating: "Aktualisiere…",
    refreshRoster: "Dienstplan aktualisieren",
    units: { day: ["Tag", "Tage"], hour: ["Stunde", "Stunden"], minute: ["Minute", "Minuten"] },
    // After "in" German takes the dative: "in 2 Tagen", "in 1 Tag".
    unitsIn: { day: ["Tag", "Tagen"], hour: ["Stunde", "Stunden"], minute: ["Minute", "Minuten"] },
    points: "Pkt.",
    overtime: "Zeitkonto",
    vacation: "Resturlaub",
    planned: "verplant",
    weekendPoints: "WE-Punkte",
    average: "Schnitt",
    freeWeekends: "Freie Wochenenden",
    nextFreeWeekend: "nächstes",
    plannedWeek: "Geplant diese Woche",
    plannedMonth: "Geplant diesen Monat",
    offline: "Portal nicht erreichbar – gespeicherter Dienstplan",
    types: {
      work: "Dienst", reserve: "Bereitschaft", training: "Schulung", free: "Frei", vacation: "Urlaub",
      compensation: "Ausgleich", sick: "Krank", unknown: "Unbekannt",
    },
    categories: { early: "Früh", day: "Mittel", late: "Spät", night: "Nacht", split: "Geteilt" },
    facts: {
      wake_up: "Aufstehen", leave_home: "Losfahren", paid: "Bezahlte Stunden", rest: "Ruhezeit davor",
      duration: "Dienstdauer", breaks: "Pausen",
    },
    tiles: {
      overtime: "Zeitkonto", daily: "Tageskonto heute", vacation: "Resturlaub", weekend_points: "WE-Punkte",
      free_weekends: "Freie Wochenenden", planned_week: "Geplant diese Woche", planned_month: "Geplant diesen Monat",
    },
    shiftDetail: {
      title: "Dienstdetails",
      place: "Ort", time: "Zeit", line: "Linie", course: "Kurs", direction: "Ablösung",
      break: "Pause", min: "Min.", noDetail: "Für diesen Dienst liegt noch keine Aufschlüsselung vor.", dayOff: "An diesem Tag kein Dienst.",
    },
    calendar: "Kalender",
    swaps: "Tausch",
    allInOne: "Alles-in-einem",
    views: { dayGridMonth: "Monat", listWeek: "Wochenliste", listMonth: "Monatsliste" },
    editor: {
      device_id: "Perdis-Konto",
      title: "Titel",
      icon: "Symbol in der Kopfzeile",
      show_header: "Kopfzeile anzeigen",
      accent: "Akzentfarbe",
      tap_action: "Tippen-Aktion",
      show_countdown: "Countdown anzeigen",
      show_progress: "Fortschritt während des Dienstes anzeigen",
      show_lines: "Linien anzeigen",
      show_location: "Meldeort anzeigen",
      show_facts: "Angezeigte Eckdaten",
      days: "Angezeigte Tage",
      show_days_off: "Freie Tage anzeigen",
      compact: "Kompakte Zeilen",
      group_by_week: "Nach Kalenderwoche gruppieren",
      highlight_today: "Heute hervorheben",
      show_tags: "Markierungen anzeigen (geändert, geteilt, Dienstart)",
      hide_types: "Diese Tagesarten ausblenden",
      show_tiles: "Angezeigte Kacheln",
      columns: "Spalten (0 = automatisch)",
      show_course: "Spalte Kurs anzeigen",
      show_relief: "Spalte Ablösung anzeigen",
      show_breaks: "Pausen anzeigen",
      initial_view: "Startansicht",
      tabs: "Angezeigte Reiter",
      logo: "Logo (Bildadresse)",
      sec_content: "Inhalt",
      sec_appearance: "Darstellung",
      sec_behavior: "Verhalten",
    },
    helper: {
      device_id: "Leer lassen für das erste Konto.",
      title: "Leer lassen für den Standardtitel.",
      icon: "Leer lassen für das Standardsymbol.",
      accent: "Leer lassen, um die Karte nach der Dienstart einzufärben.",
      hide_types: "Leer lassen, um jeden Tag anzuzeigen.",
      logo: "Leer lassen für das Namens-Badge des Betriebs. Beispiel: /local/mein-logo.png",
    },
  },
};

const TYPE_COLORS = {
  work: "var(--primary-color, #03a9f4)",
  reserve: "var(--orange-color, #ff9800)",
  training: "var(--purple-color, #9c27b0)",
  free: "var(--green-color, #4caf50)",
  vacation: "var(--teal-color, #009688)",
  compensation: "var(--light-green-color, #8bc34a)",
  sick: "var(--red-color, #f44336)",
  unknown: "var(--disabled-color, #9e9e9e)",
};
const CATEGORY_ICONS = {
  early: "mdi:weather-sunset-up", day: "mdi:white-balance-sunny", late: "mdi:weather-sunset-down",
  night: "mdi:weather-night", split: "mdi:call-split",
};
const DEFAULT_HEADER_ICON = "mdi:bus-clock";
const OFF_TYPES = ["free", "vacation", "compensation"];
const FACT_KEYS = ["wake_up", "leave_home", "duration", "paid", "breaks", "rest"];
const TILE_KEYS = ["overtime", "daily", "vacation", "weekend_points", "free_weekends", "planned_week", "planned_month"];
// Which account entity each tile needs; a tile is hidden when its portal does not provide it.
const TILE_ROLES = {
  overtime: "overtime", daily: "daily_values", vacation: "vacation", weekend_points: "weekend_points",
  free_weekends: "free_weekends", planned_week: "planned_week", planned_month: "planned_month",
};
const DUTY_TYPE_KEYS = ["work", "reserve", "training", "free", "vacation", "compensation", "sick", "unknown"];

function language(hass) {
  const code = (hass?.locale?.language || hass?.language || "en").split("-")[0];
  return TEXTS[code] ? code : "en";
}

function texts(hass) {
  return TEXTS[language(hass)];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
  ));
}

/** The accent colour of the card: the option, otherwise the colour of the duty type. */
function accentOf(config, dutyType) {
  if (config?.accent) return config.accent;
  return TYPE_COLORS[dutyType] || TYPE_COLORS.work;
}

// --- Actions (tap) -------------------------------------------------------------------------------

function fireEvent(node, type, detail) {
  node.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
}

/** Run a Lovelace action config (more-info, navigate, url, toggle, call-service) like a normal card. */
function handleAction(node, hass, actionConfig, fallbackEntity) {
  const config = actionConfig || { action: "more-info" };
  switch (config.action || "more-info") {
    case "none":
      return;
    case "more-info": {
      const entityId = config.entity || fallbackEntity;
      if (entityId) fireEvent(node, "hass-more-info", { entityId });
      return;
    }
    case "navigate":
      if (config.navigation_path) {
        history.pushState(null, "", config.navigation_path);
        fireEvent(window, "location-changed", { replace: false });
      }
      return;
    case "url":
      if (config.url_path) window.open(config.url_path, config.url_path.startsWith("http") ? "_blank" : "_self");
      return;
    case "toggle": {
      const entityId = config.entity || fallbackEntity;
      if (entityId) hass.callService("homeassistant", "toggle", { entity_id: entityId });
      return;
    }
    case "call-service":
    case "perform-action": {
      const call = config.perform_action || config.service;
      if (!call || !call.includes(".")) return;
      const [domain, service] = call.split(".", 2);
      hass.callService(domain, service, config.data || config.service_data || {}, config.target);
      return;
    }
    default:
  }
}

// --- Finding the entities of an account ----------------------------------------------------------

/** Entity ids that carry a `perdis_role` attribute, in the order Home Assistant lists them. */
function roleEntities(hass) {
  return Object.keys(hass.states).filter((entityId) => hass.states[entityId].attributes?.perdis_role);
}

function deviceOf(hass, entityId) {
  return hass.entities?.[entityId]?.device_id;
}

function firstDevice(hass) {
  const first = roleEntities(hass)[0];
  return first ? deviceOf(hass, first) : undefined;
}

/** role -> entity id for one Perdis device (the first one when `deviceId` is empty). */
function findEntities(hass, deviceId) {
  const device = deviceId || firstDevice(hass);
  const found = {};
  for (const entityId of roleEntities(hass)) {
    const entityDevice = deviceOf(hass, entityId);
    // Without registry information (very old frontends) every Perdis entity is accepted.
    if (device && entityDevice && entityDevice !== device) continue;
    const role = hass.states[entityId].attributes.perdis_role;
    if (!found[role]) found[role] = entityId;
  }
  return found;
}

// --- Formatting ----------------------------------------------------------------------------

/** Points in time follow the time zone setting of the user profile ("server" or "local"). */
function timeFormatter(hass, options) {
  const zone = hass?.locale?.time_zone === "server" ? hass?.config?.time_zone : undefined;
  return new Intl.DateTimeFormat(hass?.locale?.language || "en", { ...options, timeZone: zone });
}

/** Calendar days have no time zone: they are formatted as the local day they name. */
function dayFormatter(hass, options) {
  return new Intl.DateTimeFormat(hass?.locale?.language || "en", options);
}

function formatTime(hass, value) {
  return value ? timeFormatter(hass, { hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "–";
}

function parseDay(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDay(hass, isoDate, options = { weekday: "short", day: "2-digit", month: "2-digit" }) {
  return dayFormatter(hass, options).format(parseDay(isoDate));
}

function relativeDay(hass, isoDate) {
  const t = texts(hass);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((parseDay(isoDate) - today) / 86400000);
  if (days === 0) return t.today;
  if (days === 1) return t.tomorrow;
  return formatDay(hass, isoDate, { weekday: "long", day: "2-digit", month: "2-digit" });
}

/**
 * A span of minutes in its largest units, the word following the number: "1 Tag 3 Stunden",
 * "45 Minuten". Units that are zero are left out. `dative` is for "in …" ("in 2 Tagen").
 */
function formatDuration(hass, minutes, dative = false) {
  if (minutes === null || minutes === undefined || Number.isNaN(Number(minutes))) return "–";
  const t = texts(hass);
  const words = dative ? t.unitsIn : t.units;
  const total = Math.max(Math.round(Number(minutes)), 0);
  const parts = [
    [Math.floor(total / 1440), words.day],
    [Math.floor((total % 1440) / 60), words.hour],
    [total % 60, words.minute],
  ].filter(([count]) => count > 0).map(([count, [one, many]]) => `${count} ${count === 1 ? one : many}`);
  return parts.length ? parts.join(" ") : `0 ${words.minute[1]}`;
}

/** The time until a shift starts or ends: days and hours from a day on, else hours and minutes. */
function formatCountdown(hass, minutes) {
  if (minutes === null || minutes === undefined) return "";
  // From a day on the minutes are noise, so they are dropped.
  const shown = minutes >= 1440 ? Math.floor(minutes / 60) * 60 : minutes;
  return formatDuration(hass, shown, true);
}

/** How long ago a moment was, in the user's language: "vor 5 Minuten", or "gerade eben" within a minute. */
function formatAgo(hass, iso) {
  const moment = iso ? new Date(iso) : null;
  if (!moment || Number.isNaN(moment.getTime())) return "";
  const minutes = Math.floor((Date.now() - moment.getTime()) / 60000);
  if (minutes < 1) return texts(hass).justNow;
  const rtf = new Intl.RelativeTimeFormat(hass?.locale?.language || "en", { numeric: "always" });
  if (minutes < 60) return rtf.format(-minutes, "minute");
  if (minutes < 2880) return rtf.format(-Math.floor(minutes / 60), "hour");
  return rtf.format(-Math.floor(minutes / 1440), "day");
}

/** "Tag" or "Tage" by the number: the unit word of a count, e.g. for the days of vacation left. */
function unitLabel(hass, unit, count) {
  return texts(hass).units[unit][Number(count) === 1 ? 0 : 1];
}

function formatNumber(hass, value, digits = 1) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "–";
  return new Intl.NumberFormat(hass?.locale?.language || "en", {
    maximumFractionDigits: digits, minimumFractionDigits: 0,
  }).format(Number(value));
}

/** A time account in the portal's own hours:minutes form: 10 h 17 min reads "+10:17", not "10.3". */
function formatClockHours(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "–";
  const total = Math.round(Math.abs(Number(value)) * 60);
  const sign = Number(value) < 0 ? "−" : "";
  return `${sign}${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function isoWeek(date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
}

function numericState(hass, entityId) {
  const state = entityId ? hass.states[entityId] : undefined;
  if (!state || ["unknown", "unavailable"].includes(state.state)) return null;
  const value = Number(state.state);
  return Number.isNaN(value) ? null : value;
}

// --- Shared card base ----------------------------------------------------------------------------

const BASE_STYLE = `
  :host { display: block; }
  ha-card { height: 100%; overflow: hidden; }
  .embedded { display: block; }
  .header { display: flex; align-items: center; gap: 10px; padding: 16px 16px 4px; }
  .header .title { font-size: 1.15rem; font-weight: 500; flex: 1; }
  .header ha-icon { color: var(--accent, var(--primary-color)); }
  .content { padding: 8px 16px 16px; }
  .no-header .content { padding-top: 16px; }
  .muted { color: var(--secondary-text-color); }
  .empty { padding: 16px; color: var(--secondary-text-color); }
  .pill { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 2px 10px;
          font-size: 0.8rem; font-weight: 500; white-space: nowrap; }
  .banner { margin: 0 16px 8px; padding: 6px 10px; border-radius: 8px; font-size: 0.85rem;
            background: rgba(var(--rgb-warning-color, 255, 166, 0), 0.15); color: var(--warning-color, #ffa600); }
  ha-icon { --mdc-icon-size: 20px; }
  .clickable { cursor: pointer; }
  .actionable { cursor: pointer; transition: background 120ms ease; border-radius: 12px; }
  .actionable:hover { background: color-mix(in srgb, var(--accent, var(--primary-color)) 7%, transparent); }
`;

class PerdisCardBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._signature = "";
  }

  // Defaults merged into every config; a card overrides this for its own options.
  static defaults() {
    return {};
  }

  setConfig(config) {
    this._config = { ...this.constructor.defaults(), ...config };
    this._signature = "";
    if (this._hass) {
      this._entities = findEntities(this._hass, this._config.device_id);
      this._render();
    }
  }

  set hass(hass) {
    this._hass = hass;
    const entities = findEntities(hass, this._config?.device_id);
    // Render only when one of our entities changed: dashboards set `hass` on every state change.
    const signature = Object.values(entities).map((id) => hass.states[id]?.last_updated).join("|")
      + language(hass);
    if (signature === this._signature) return;
    this._signature = signature;
    this._entities = entities;
    this._render();
  }

  get hass() {
    return this._hass;
  }

  attributes(role) {
    const id = this._entities?.[role];
    return id ? this._hass.states[id]?.attributes || {} : null;
  }

  /** The configured tap action, or more-info on the role entity by default. */
  runTap(role) {
    handleAction(this, this._hass, this._config?.tap_action, this._entities?.[role]);
  }

  frame(title, body, extraStyle = "", accent = "") {
    const showHeader = this._config?.show_header !== false;
    const icon = this._config?.icon || DEFAULT_HEADER_ICON;
    const roster = this.attributes("roster");
    const offline = roster && roster.online === false
      ? `<div class="banner">${escapeHtml(texts(this._hass).offline)}</div>` : "";
    const header = showHeader
      ? `<div class="header"><ha-icon icon="${escapeHtml(icon)}"></ha-icon>
           <span class="title">${escapeHtml(title)}</span></div>`
      : "";
    const style = accent ? `--accent:${accent};` : "";
    // Embedded in the all-in-one card, a panel drops its own ha-card so there is no card-in-a-card;
    // the master card provides the single frame around it.
    if (this._embedded) {
      this.shadowRoot.innerHTML = `
        <style>${BASE_STYLE}${extraStyle}</style>
        <div class="embedded ${showHeader ? "" : "no-header"}" style="${style}">${header}${offline}${body}</div>`;
      return;
    }
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${extraStyle}</style>
      <ha-card style="${style}" class="${showHeader ? "" : "no-header"}">
        ${header}
        ${offline}
        ${body}
      </ha-card>`;
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig(hass) {
    const device = firstDevice(hass);
    return device ? { device_id: device } : {};
  }
}

/** A visual editor whose schema is built from `(hass, config) => [ha-form schema]`. */
function editorFor(buildSchema) {
  return class extends HTMLElement {
    setConfig(config) {
      this._config = { ...config };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    _render() {
      if (!this._hass || !this._config) return;
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.addEventListener("value-changed", (event) => {
          const config = { ...event.detail.value };
          for (const key of Object.keys(config)) {
            const value = config[key];
            if (value === "" || value === undefined || value === null || (Array.isArray(value) && !value.length)) {
              delete config[key];
            }
          }
          this._config = config;
          fireEvent(this, "config-changed", { config });
        });
        this.appendChild(this._form);
      }
      const t = texts(this._hass);
      this._form.hass = this._hass;
      this._form.data = this._config;
      this._form.schema = buildSchema(this._hass, this._config);
      this._form.computeLabel = (schema) => t.editor[schema.name] || schema.name;
      this._form.computeHelper = (schema) => t.helper[schema.name] || "";
    }
  };
}

// Reusable editor field builders.
const field = {
  device: { name: "device_id", selector: { device: { integration: DOMAIN } } },
  title: { name: "title", selector: { text: {} } },
  icon: { name: "icon", selector: { icon: {} } },
  showHeader: { name: "show_header", selector: { boolean: {} } },
  accent: { name: "accent", selector: { color_rgb: {} } },
  tapAction: { name: "tap_action", selector: { ui_action: {} } },
  boolean: (name) => ({ name, selector: { boolean: {} } }),
  select: (name, options, multiple = false) => ({
    name,
    selector: { select: { multiple, mode: multiple ? "list" : "dropdown", options } },
  }),
};

function typeOptions(hass) {
  const t = texts(hass);
  return DUTY_TYPE_KEYS.map((value) => ({ value, label: t.types[value] }));
}

function section(hass, name, schema) {
  return { name, type: "expandable", flatten: true, title: texts(hass).editor[name], schema };
}

// --- Next shift ----------------------------------------------------------------------------------

const SHIFT_STYLE = `
  .hero { position: relative; border-radius: 16px; padding: 14px 16px 16px; overflow: hidden;
          background: var(--secondary-background-color);
          background: color-mix(in srgb, var(--accent) 14%, var(--card-background-color)); }
  .hero::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 5px; background: var(--accent); }
  .duty { display: flex; align-items: baseline; gap: 6px 12px; flex-wrap: wrap; }
  .duty .code { font-size: 2.1rem; font-weight: 700; line-height: 1.05; letter-spacing: -0.5px; }
  .when { margin-top: 6px; font-size: 1rem; }
  .times { font-size: 1.7rem; font-weight: 500; margin: 10px 0 2px; letter-spacing: 0.5px; }
  .place { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
  .lines { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
  .line { background: color-mix(in srgb, var(--accent) 20%, var(--card-background-color));
          border-radius: 6px; padding: 1px 8px; font-weight: 600; font-size: 0.85rem; }
  .progress { height: 6px; border-radius: 3px; background: var(--divider-color); margin-top: 12px; overflow: hidden; }
  .progress > div { height: 100%; background: var(--accent); transition: width 1s linear; }
  .facts { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-top: 14px; }
  .fact { background: var(--secondary-background-color); border-radius: 12px; padding: 10px 10px; text-align: center; }
  /* An odd last tile spans the row, so the grid never ends lopsided. */
  .fact:last-child:nth-child(odd) { grid-column: 1 / -1; }
  .fact .label { font-size: 0.75rem; color: var(--secondary-text-color); display: flex; align-items: center;
                 justify-content: center; gap: 4px; }
  .fact .value { font-size: 1.05rem; font-weight: 600; margin-top: 3px; }
  .fact.warning { background: rgba(var(--rgb-error-color, 219, 68, 55), 0.15); }
  .fact.warning .value { color: var(--error-color, #db4437); }
`;

class PerdisShiftCard extends PerdisCardBase {
  static defaults() {
    return {
      show_countdown: true, show_progress: true, show_lines: true, show_location: true,
      show_facts: [...FACT_KEYS],
    };
  }

  static getConfigElement() {
    return document.createElement("perdis-shift-card-editor");
  }

  _render() {
    const t = texts(this._hass);
    const config = this._config;
    const title = config.title || t.nextShift;
    const shift = this.attributes("next_shift");
    if (shift === null) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);
    if (!shift.date) return this.frame(title, `<div class="empty">${escapeHtml(t.noShift)}</div>`);

    const category = shift.category || "day";
    const accent = accentOf(config, shift.duty_type);
    const countdown = !config.show_countdown ? ""
      : shift.running
        ? `<span class="pill" style="background:${accent};color:var(--text-primary-color,#fff)">${escapeHtml(t.running)} · ${escapeHtml(t.endsIn)} ${formatCountdown(this._hass, shift.minutes_until_end)}</span>`
        : `<span class="pill" style="background:var(--secondary-background-color)">${escapeHtml(t.startsIn)} ${formatCountdown(this._hass, shift.minutes_until_start)}</span>`;
    const progress = config.show_progress && shift.running && shift.start && shift.end
      ? Math.min(100, Math.max(0, ((Date.now() - new Date(shift.start)) / (new Date(shift.end) - new Date(shift.start))) * 100))
      : null;
    const lines = config.show_lines
      ? (shift.lines || []).map((line) => `<span class="line">${escapeHtml(line)}</span>`).join("") : "";
    const rest = shift.rest_before_hours;
    const wanted = new Set(config.show_facts || FACT_KEYS);
    const clock = (value) => `${formatTime(this._hass, value)}${t.clock ? ` ${t.clock}` : ""}`;
    const spanMinutes = shift.start && shift.end ? (new Date(shift.end) - new Date(shift.start)) / 60000 : null;
    const facts = [
      wanted.has("wake_up") && !shift.running && shift.wake_up
        ? [t.facts.wake_up, "mdi:alarm", clock(shift.wake_up), false] : null,
      wanted.has("leave_home") && !shift.running && shift.leave_home
        ? [t.facts.leave_home, "mdi:home-export-outline", clock(shift.leave_home), false] : null,
      wanted.has("duration") && spanMinutes
        ? [t.facts.duration, "mdi:timer-sand", formatDuration(this._hass, spanMinutes), false] : null,
      wanted.has("paid") && shift.hours
        ? [t.facts.paid, "mdi:timer-outline", formatNumber(this._hass, shift.hours, 2), false] : null,
      wanted.has("breaks") && spanMinutes
        ? [t.facts.breaks, "mdi:coffee-outline",
           shift.break_minutes ? formatDuration(this._hass, shift.break_minutes) : "–", false] : null,
      wanted.has("rest") && !shift.running && rest !== null && rest !== undefined
        ? [shift.short_rest ? t.shortRest : t.facts.rest, "mdi:bed-clock",
           formatDuration(this._hass, Math.round(rest * 60)), shift.short_rest] : null,
    ].filter(Boolean).map(([label, icon, value, warning]) => `
      <div class="fact${warning ? " warning" : ""}">
        <div class="label"><ha-icon icon="${icon}" style="--mdc-icon-size:14px"></ha-icon>${escapeHtml(label)}</div>
        <div class="value">${escapeHtml(value)}</div>
      </div>`).join("");

    this.frame(title, `
      <div class="content actionable">
        <div class="hero">
          <div class="duty">
            <span class="code">${escapeHtml(shift.duty || t.types[shift.duty_type] || "")}</span>
            <span class="pill" style="background:${accent};color:var(--text-primary-color,#fff)">
              <ha-icon icon="${CATEGORY_ICONS[category] || "mdi:bus"}" style="--mdc-icon-size:14px"></ha-icon>
              ${escapeHtml(t.categories[category] || t.types[shift.duty_type] || "")}${shift.split_shift ? ` · ${escapeHtml(t.split)}` : ""}
            </span>
            ${countdown}
          </div>
          <div class="when muted">${escapeHtml(relativeDay(this._hass, shift.date))}</div>
          <div class="times">${formatTime(this._hass, shift.start)} – ${formatTime(this._hass, shift.end)}</div>
          ${config.show_location && shift.start_location ? `<div class="place"><ha-icon icon="mdi:map-marker"></ha-icon>${escapeHtml(shift.start_location)}${shift.end_location && shift.end_location !== shift.start_location ? ` → ${escapeHtml(shift.end_location)}` : ""}</div>` : ""}
          ${lines ? `<div class="lines">${lines}</div>` : ""}
          ${progress !== null ? `<div class="progress"><div style="width:${progress.toFixed(1)}%"></div></div>` : ""}
        </div>
        ${facts ? `<div class="facts">${facts}</div>` : ""}
      </div>`, SHIFT_STYLE, accent);
    // Tapping the shift opens the same full breakdown pop-up as a roster day; the next-shift sensor
    // already carries everything the pop-up needs (date, code, times, place, lines, legs).
    this.shadowRoot.querySelector(".content")?.addEventListener("click", () => {
      if (config.tap_action) {
        this.runTap("next_shift");
        return;
      }
      openDayDialog(this._hass, shift, texts(this._hass));
    });
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const SHIFT_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_content", [
    field.select("show_facts", FACT_KEYS.map((value) => ({ value, label: texts(hass).facts[value] })), true),
    { type: "grid", schema: [field.boolean("show_location"), field.boolean("show_lines")] },
    { type: "grid", schema: [field.boolean("show_countdown"), field.boolean("show_progress")] },
  ]),
  section(hass, "sec_appearance", [
    { type: "grid", schema: [field.showHeader, field.icon] },
    field.accent,
  ]),
  section(hass, "sec_behavior", [field.tapAction]),
];

// --- Roster --------------------------------------------------------------------------------------

const ROSTER_STYLE = `
  .week { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px;
          color: var(--secondary-text-color); margin: 12px 0 4px; }
  .week:first-child { margin-top: 0; }
  .day { display: grid; grid-template-columns: 58px 6px 1fr auto; gap: 10px; align-items: center;
         padding: 7px 8px; border-radius: 10px; cursor: pointer; }
  .day:hover { background: color-mix(in srgb, var(--accent, var(--primary-color)) 7%, transparent); }
  .day + .day { margin-top: 2px; }
  .day.today { background: var(--secondary-background-color); }
  .day .date { font-size: 0.85rem; line-height: 1.15; }
  .day .date b { display: block; font-size: 1rem; }
  .day .bar { width: 6px; height: 100%; min-height: 30px; border-radius: 3px; }
  .day .main { min-width: 0; }
  .day .main .title { font-weight: 500; overflow-wrap: anywhere; }
  .day .main .sub { font-size: 0.82rem; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .day .tags { display: flex; gap: 4px; flex-wrap: wrap; justify-content: flex-end; }
  .tag { font-size: 0.7rem; border-radius: 6px; padding: 1px 6px; background: var(--secondary-background-color); }
  .tag.changed { background: rgba(var(--rgb-warning-color, 255, 166, 0), 0.2); color: var(--warning-color, #ffa600); font-weight: 600; }
  .compact .day { padding: 3px 8px; }
  .compact .day .bar { min-height: 20px; }
  .compact .day .main .sub { display: none; }
`;

class PerdisRosterCard extends PerdisCardBase {
  static defaults() {
    return {
      days: 14, show_days_off: true, compact: false, group_by_week: true,
      highlight_today: true, show_location: true, show_lines: true, show_tags: true, hide_types: [],
    };
  }

  static getConfigElement() {
    return document.createElement("perdis-roster-card-editor");
  }

  _hidden() {
    const hidden = new Set(this._config.hide_types || []);
    if (this._config.show_days_off === false) OFF_TYPES.forEach((type) => hidden.add(type));
    return hidden;
  }

  _render() {
    const t = texts(this._hass);
    const config = this._config;
    const title = config.title || t.roster;
    const roster = this.attributes("roster");
    if (roster === null) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);
    const hidden = this._hidden();
    const limit = Number(config.days || 14);
    const days = (roster.days || []).slice(0, limit).filter((day) => !hidden.has(day.duty_type));
    if (!days.length) return this.frame(title, `<div class="empty">${escapeHtml(t.noDays)}</div>`);

    const todayIso = new Date().toLocaleDateString("sv-SE");
    let currentWeek = null;
    const rows = days.map((day) => {
      const week = isoWeek(parseDay(day.date));
      const header = config.group_by_week && week !== currentWeek
        ? `<div class="week">${escapeHtml(t.week)} ${week}</div>` : "";
      currentWeek = week;
      const color = accentOf(config, day.duty_type);
      const typeName = t.types[day.duty_type] || day.duty_type;
      // An unrecognised entry shows its own code ("SF Neu"), not the generic "Unknown" label.
      const label = day.duty_type === "unknown" && day.duty ? day.duty : typeName;
      // An absence reads as just its name ("Krank", "Frei"), with no code and no times — exactly as
      // the calendar shows it. Even when the portal keeps the planned times on a sick day, the day
      // is still "Krank", never its duty code. Only a real shift carries a number, times and lines.
      const absence = OFF_TYPES.includes(day.duty_type) || day.duty_type === "sick";
      const hasTimes = !absence && day.start && day.end;
      const heading = absence
        ? escapeHtml(typeName)
        : hasTimes
          ? `${escapeHtml(day.duty || label)} · ${formatTime(this._hass, day.start)}–${formatTime(this._hass, day.end)}`
          : escapeHtml(day.duty && day.duty.toUpperCase() !== label.toUpperCase() ? `${label} (${day.duty})` : label);
      const subParts = absence ? [day.remark] : [
        config.show_location ? day.start_location : null,
        config.show_lines ? (day.lines || []).join(", ") : null,
        day.remark,
      ];
      const sub = subParts.filter(Boolean).join(" · ");
      const tags = config.show_tags ? [
        day.changed ? `<span class="tag changed">${escapeHtml(t.changed)}</span>` : "",
        !absence && day.split_shift ? `<span class="tag">${escapeHtml(t.split)}</span>` : "",
        !absence && hasTimes && day.category ? `<span class="tag">${escapeHtml(t.categories[day.category] || "")}</span>` : "",
      ].join("") : "";
      const [weekday, ...rest] = formatDay(this._hass, day.date).split(/,?\s+/);
      const today = config.highlight_today && day.date === todayIso ? " today" : "";
      return `${header}
        <div class="day${today}" data-date="${escapeHtml(day.date)}">
          <div class="date"><b>${escapeHtml(weekday)}</b>${escapeHtml(rest.join(" "))}</div>
          <div class="bar" style="background:${color}"></div>
          <div class="main"><div class="title">${heading}</div>${sub ? `<div class="sub">${escapeHtml(sub)}</div>` : ""}</div>
          <div class="tags">${tags}</div>
        </div>`;
    }).join("");
    const accent = accentOf(config, "work");
    this.frame(title, `<div class="content${config.compact ? " compact" : ""}">${rows}</div>`, ROSTER_STYLE, accent);
    // Tapping a day opens its full breakdown in a pop-up by default; a configured tap action wins.
    const byDate = new Map(days.map((entry) => [entry.date, entry]));
    this.shadowRoot.querySelectorAll(".day").forEach((element) => {
      element.addEventListener("click", () => {
        if (config.tap_action) {
          this.runTap("roster");
          return;
        }
        const entry = byDate.get(element.dataset.date);
        if (entry) openDayDialog(this._hass, entry, texts(this._hass));
      });
    });
  }

  getCardSize() {
    return Math.min(2 + Number(this._config?.days || 14), 16);
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const ROSTER_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_content", [
    { name: "days", selector: { number: { min: 3, max: 42, mode: "slider" } } },
    field.select("hide_types", typeOptions(hass), true),
    { type: "grid", schema: [field.boolean("show_location"), field.boolean("show_lines")] },
    { type: "grid", schema: [field.boolean("show_tags"), field.boolean("group_by_week")] },
  ]),
  section(hass, "sec_appearance", [
    { type: "grid", schema: [field.showHeader, field.icon] },
    { type: "grid", schema: [field.boolean("compact"), field.boolean("highlight_today")] },
    field.accent,
  ]),
  section(hass, "sec_behavior", [field.tapAction]),
];

// --- Accounts ------------------------------------------------------------------------------------

const ACCOUNTS_STYLE = `
  .tiles { display: grid; gap: 10px; }
  .tiles.auto { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
  .tile { background: var(--secondary-background-color); border-radius: 14px; padding: 10px 12px; cursor: pointer;
          transition: transform 120ms ease; }
  .tile:hover { transform: translateY(-1px); }
  .tile .label { font-size: 0.78rem; color: var(--secondary-text-color); display: flex; align-items: center; gap: 6px; }
  .tile .value { font-size: 1.5rem; font-weight: 700; margin-top: 4px; letter-spacing: -0.5px; }
  .tile .value small { font-size: 0.85rem; font-weight: 400; color: var(--secondary-text-color); margin-left: 3px; }
  .tile .hint { font-size: 0.78rem; color: var(--secondary-text-color); margin-top: 2px; }
  .positive { color: var(--success-color, #43a047); }
  .negative { color: var(--error-color, #db4437); }
  .meter { position: relative; height: 6px; border-radius: 3px; background: var(--divider-color); margin-top: 8px; }
  .meter .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--accent, var(--primary-color)); }
  .meter .mark { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--primary-text-color); }
`;

class PerdisAccountsCard extends PerdisCardBase {
  static defaults() {
    return {
      show_tiles: ["overtime", "daily", "vacation", "weekend_points", "free_weekends", "planned_week"],
      columns: 0,
    };
  }

  static getConfigElement() {
    return document.createElement("perdis-accounts-card-editor");
  }

  _tile(key) {
    const t = texts(this._hass);
    const hass = this._hass;
    const wrap = (role, icon, label, inner) => `
      <div class="tile" data-role="${role}">
        <div class="label"><ha-icon icon="${icon}" style="--mdc-icon-size:16px"></ha-icon>${escapeHtml(label)}</div>
        ${inner}
      </div>`;
    const value = (text, unit, tone = "") =>
      `<div class="value ${tone}">${text}<small>${escapeHtml(unit)}</small></div>`;
    const hint = (text) => (text ? `<div class="hint">${text}</div>` : "");

    switch (key) {
      case "overtime": {
        const overtime = numericState(hass, this._entities.overtime);
        const tone = overtime === null ? "" : overtime >= 0 ? "positive" : "negative";
        // Shown as hours:minutes like the portal ("+10:17"), not as a decimal number of hours.
        const text = overtime === null ? "–" : `${overtime > 0 ? "+" : ""}${formatClockHours(overtime)}`;
        return wrap("overtime", "mdi:timer-sand", t.overtime, value(text, "", tone));
      }
      case "daily": {
        const daily = numericState(hass, this._entities.daily_values);
        const tone = daily === null ? "" : daily >= 0 ? "positive" : "negative";
        const text = daily === null ? "–" : `${daily > 0 ? "+" : ""}${formatClockHours(daily)}`;
        return wrap("daily_values", "mdi:clock-time-four-outline", t.tiles.daily, value(text, "", tone));
      }
      case "vacation": {
        const vacation = numericState(hass, this._entities.vacation);
        const info = this.attributes("vacation") || {};
        return wrap("vacation", "mdi:island", t.vacation, value(formatNumber(hass, vacation), unitLabel(hass, "day", vacation))
          + hint(info.planned_days ? `${formatNumber(hass, info.planned_days)} ${escapeHtml(t.planned)}` : ""));
      }
      case "weekend_points": {
        const points = numericState(hass, this._entities.weekend_points);
        const info = this.attributes("weekend_points") || {};
        const average = info.group_average;
        let meter = "";
        if (points !== null && average !== null && average !== undefined) {
          const scale = Math.max(points, average) * 1.25 || 1;
          meter = `<div class="meter"><div class="fill" style="width:${(points / scale) * 100}%"></div>
            <div class="mark" style="left:${(average / scale) * 100}%"></div></div>`;
        }
        const hintText = average !== null && average !== undefined
          ? `${escapeHtml(t.average)} ${formatNumber(hass, average)}` : "";
        return wrap("weekend_points", "mdi:scale-balance", t.weekendPoints,
          value(formatNumber(hass, points), t.points) + hint(hintText) + meter);
      }
      case "free_weekends": {
        const free = numericState(hass, this._entities.free_weekends);
        const nextFree = hass.states[this._entities.next_free_weekend]?.state;
        const text = nextFree && !["unknown", "unavailable"].includes(nextFree)
          ? `${escapeHtml(t.nextFreeWeekend)}: ${escapeHtml(formatDay(hass, nextFree))}` : "";
        return wrap("free_weekends", "mdi:calendar-weekend", t.freeWeekends,
          value(formatNumber(hass, free, 0), "") + hint(text));
      }
      case "planned_week":
        return wrap("planned_week", "mdi:calendar-week", t.plannedWeek,
          value(formatNumber(hass, numericState(hass, this._entities.planned_week)), t.hours));
      case "planned_month":
        return wrap("planned_month", "mdi:calendar-month", t.plannedMonth,
          value(formatNumber(hass, numericState(hass, this._entities.planned_month)), t.hours));
      default:
        return "";
    }
  }

  _render() {
    const t = texts(this._hass);
    const config = this._config;
    const title = config.title || t.accounts;
    if (!this._entities?.roster) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);

    const keys = (config.show_tiles && config.show_tiles.length ? config.show_tiles : TILE_KEYS)
      .filter((key) => TILE_KEYS.includes(key))
      // Hide a tile whose portal does not provide it, so no empty "–" cards are shown.
      .filter((key) => this._entities[TILE_ROLES[key]]);
    const tiles = keys.map((key) => this._tile(key)).join("");
    if (!tiles) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`,
      ACCOUNTS_STYLE, accentOf(config, "work"));
    const columns = Number(config.columns) || 0;
    const gridClass = columns > 0 ? "" : " auto";
    const gridStyle = columns > 0 ? `style="grid-template-columns:repeat(${columns},1fr)"` : "";
    const accent = accentOf(config, "work");

    this.frame(title, `<div class="content"><div class="tiles${gridClass}" ${gridStyle}>${tiles}</div></div>`,
      ACCOUNTS_STYLE, accent);
    this.shadowRoot.querySelectorAll(".tile").forEach((element) => {
      element.addEventListener("click", () => {
        if (config.tap_action) handleAction(this, this._hass, config.tap_action, this._entities[element.dataset.role]);
        else handleAction(this, this._hass, { action: "more-info" }, this._entities[element.dataset.role]);
      });
    });
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const ACCOUNTS_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_content", [
    field.select("show_tiles", TILE_KEYS.map((value) => ({ value, label: texts(hass).tiles[value] })), true),
    { name: "columns", selector: { number: { min: 0, max: 4, mode: "slider" } } },
  ]),
  section(hass, "sec_appearance", [
    { type: "grid", schema: [field.showHeader, field.icon] },
    field.accent,
  ]),
  section(hass, "sec_behavior", [field.tapAction]),
];

// --- Duty-swap card ------------------------------------------------------------------------------

const SWAP_STYLE = `
  .content { padding: 8px 12px 12px; display: flex; flex-direction: column; gap: 10px; }
  .window { color: var(--secondary-text-color); font-size: 0.85em; }
  .swap { border: 1px solid var(--divider-color); border-radius: 12px; padding: 10px 12px;
    display: flex; flex-direction: column; gap: 6px; border-left: 4px solid var(--accent, var(--primary-color)); }
  .swap .top { display: flex; justify-content: space-between; gap: 8px; font-weight: 600; }
  .swap .sub { color: var(--secondary-text-color); font-size: 0.85em;
    display: flex; flex-wrap: wrap; gap: 4px 12px; }
  .empty { padding: 4px 0; color: var(--secondary-text-color); }
`;

class PerdisSwapCard extends PerdisCardBase {
  static getConfigElement() {
    return document.createElement("perdis-swap-card-editor");
  }

  _render() {
    const de = language(this._hass).startsWith("de");
    const t = {
      title: de ? "Diensttausch" : "Duty swaps",
      none: de ? "Keine offenen Tausche." : "No open swaps.",
      noCard: de ? "Keine Diensttausch-Daten." : "No duty-swap data.",
      window: de ? "Wünsche möglich für" : "Requests possible for",
    };
    const title = this._config?.title || t.title;
    const attrs = this.attributes("dutyswap");
    if (!attrs) return this.frame(title, `<div class="content"><div class="empty">${escapeHtml(t.noCard)}</div></div>`,
      SWAP_STYLE, accentOf(this._config, "work"));

    const swaps = Array.isArray(attrs.swaps) ? attrs.swaps : [];
    const windowLine = attrs.request_from && attrs.request_to
      ? `<div class="window">${escapeHtml(t.window)} ${escapeHtml(formatDay(this._hass, attrs.request_from))} – ${escapeHtml(formatDay(this._hass, attrs.request_to))}</div>`
      : "";
    const rows = swaps.length
      ? swaps.map((swap) => this._swapRow(swap)).join("")
      : `<div class="empty">${escapeHtml(t.none)}</div>`;

    this.frame(title, `<div class="content">${windowLine}${rows}</div>`,
      SWAP_STYLE, accentOf(this._config, "work"));
  }

  _swapRow(swap) {
    const day = swap.day ? formatDay(this._hass, swap.day) : "";
    const headline = [day, swap.duty, swap.time].filter(Boolean).map(escapeHtml).join(" · ");
    const sub = [swap.partner, swap.status, swap.type].filter(Boolean)
      .map((text) => `<span>${escapeHtml(text)}</span>`).join("");
    return `<div class="swap">
        <div class="top"><span>${headline}</span></div>
        <div class="sub">${sub}</div>
      </div>`;
  }

  getCardSize() {
    return 3;
  }
}

const SWAP_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_appearance", [
    { type: "grid", schema: [field.showHeader, field.icon] },
    field.accent,
  ]),
];

// --- Shift detail (the legs as a table) ----------------------------------------------------------

const DETAIL_STYLE = `
  .detail-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
  .detail-head .code { font-size: 1.5rem; font-weight: 700; }
  .detail-head .when { color: var(--secondary-text-color); }
  table.legs { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  table.legs th, table.legs td { text-align: center; padding: 7px 8px; vertical-align: top; }
  table.legs thead th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;
                        color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); }
  table.legs tbody tr { border-bottom: 1px solid var(--divider-color); }
  table.legs tbody tr:last-child { border-bottom: none; }
  table.legs td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
  table.legs tr.break td { color: var(--secondary-text-color); font-style: italic; }
  .leg-line { display: inline-block; background: color-mix(in srgb, var(--accent) 22%, var(--card-background-color));
              border-radius: 6px; padding: 1px 7px; font-weight: 600; }
  table.legs .to { color: var(--secondary-text-color); padding: 0 1px; }
  .browse { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .browse .nav { flex: 0 0 auto; border: none; border-radius: 10px; width: 36px; height: 36px; cursor: pointer;
    background: var(--secondary-background-color); color: var(--primary-text-color);
    display: inline-flex; align-items: center; justify-content: center; }
  .browse .nav:hover { background: color-mix(in srgb, var(--accent) 16%, var(--secondary-background-color)); }
  .browse .nav[disabled] { opacity: 0.3; cursor: default; }
  .browse .day { flex: 1 1 auto; text-align: center; min-width: 0; }
  .browse .day .main { font-size: 1.25rem; font-weight: 700; overflow-wrap: anywhere; }
  .browse .day .sub { font-size: 0.82rem; color: var(--secondary-text-color); }
  .detail-place { display: flex; align-items: center; justify-content: center; gap: 6px; margin: -6px 0 10px;
    color: var(--secondary-text-color); }
  .detail-msg { color: var(--secondary-text-color); padding: 2px 2px 6px; text-align: center; }
  .to-today { text-align: center; margin: 0 0 12px; }
  .to-today .chip { border: none; cursor: pointer; border-radius: 999px; padding: 5px 16px;
    font-size: 0.82rem; font-weight: 600; color: var(--text-primary-color, #fff);
    background: var(--accent, var(--primary-color)); box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2); }
  .to-today .chip:hover { filter: brightness(1.08); }
`;

const DIALOG_STYLE = `
  .dlg { --accent: var(--primary-color); min-width: min(90vw, 360px); }
  .dlg-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
  .dlg-head .code { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.5px; }
  .dlg-head .when { font-size: 1.05rem; color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .dlg-meta { color: var(--secondary-text-color); margin-bottom: 12px;
    display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .dlg-meta .dot { opacity: 0.5; }
`;


/** A relief marker spaced out for legibility: "+/+" -> "+ / +", "-/-" -> "- / -". */
function formatRelief(relief) {
  return (relief || "").replace(/\s+/g, "").replace("/", " / ");
}


/** Collapse a run of back-to-back breaks into one block, e.g. three short breaks into "Pause 45 Min.". */
function mergeBreaks(legs) {
  const merged = [];
  for (const leg of legs) {
    const last = merged[merged.length - 1];
    if (leg.is_break && last && last.is_break) {
      merged[merged.length - 1] = { ...last, end: leg.end, end_location: leg.end_location || last.end_location };
    } else {
      merged.push(leg);
    }
  }
  return merged;
}


/** One shift's leg table, shared by the shift-detail card and the day pop-up. */
function legsTable(hass, legs, options, t) {
  const showCourse = options.show_course !== false;
  const showRelief = options.show_relief !== false;
  const columns = [t.shiftDetail.place, t.shiftDetail.time, t.shiftDetail.line];
  if (showCourse) columns.push(t.shiftDetail.course);
  if (showRelief) columns.push(t.shiftDetail.direction);
  const header = columns.map((label) => `<th>${escapeHtml(label)}</th>`).join("");
  const rows = mergeBreaks(legs).map((leg) => {
    const time = `${formatTime(hass, leg.start)}–${formatTime(hass, leg.end)}`;
    if (leg.is_break) {
      const minutes = Math.max(Math.round((new Date(leg.end) - new Date(leg.start)) / 60000), 0);
      return `<tr class="break"><td>${escapeHtml(leg.location || "")}</td><td class="num">${time}</td>`
        + `<td colspan="${columns.length - 2}">${escapeHtml(t.shiftDetail.break)} ${minutes} ${escapeHtml(t.shiftDetail.min)}</td></tr>`;
    }
    // Every leg has a start point and an end point; show both as "Von → Bis", even when they are
    // the same relief point, so the destination column is never missing.
    const place = leg.end_location
      ? `${escapeHtml(leg.location || "–")} <span class="to">→</span> ${escapeHtml(leg.end_location)}`
      : escapeHtml(leg.location || "–");
    const cells = [
      `<td>${place}</td>`,
      `<td class="num">${time}</td>`,
      `<td>${leg.line ? `<span class="leg-line">${escapeHtml(leg.line)}</span>` : "–"}</td>`,
    ];
    if (showCourse) cells.push(`<td>${escapeHtml(leg.course || "–")}</td>`);
    if (showRelief) cells.push(`<td class="num">${escapeHtml(formatRelief(leg.relief)) || "–"}</td>`);
    return `<tr>${cells.join("")}</tr>`;
  }).join("");
  return `<table class="legs"><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table>`;
}


/** One day's pop-up body: the shift summary and, when there is one, its leg table. */
function dayDetailBody(hass, day, t) {
  const typeName = t.types[day.duty_type] || day.duty_type;
  // An absence ("Krank", "Frei") shows its name, never its duty code, even with planned times.
  const absence = OFF_TYPES.includes(day.duty_type) || day.duty_type === "sick";
  const working = !absence && Boolean(day.start && day.end);
  const code = absence ? typeName
    : (day.duty_type === "unknown" && day.duty ? day.duty : (working ? (day.duty || typeName) : typeName));
  const when = working ? `${formatTime(hass, day.start)}–${formatTime(hass, day.end)}` : "";
  // The shift's start and its final destination, e.g. "HB → Betriebshof".
  const place = !absence && day.start_location
    ? (day.end_location && day.end_location !== day.start_location
        ? `${day.start_location} → ${day.end_location}` : day.start_location)
    : "";
  const meta = [place, working ? (day.lines || []).join(", ") : "", day.remark]
    .filter(Boolean).map((text) => `<span>${escapeHtml(text)}</span>`).join('<span class="dot">·</span>');
  const legs = absence ? [] : (day.legs || []);
  const body = legs.length
    ? legsTable(hass, legs, {}, t)
    : `<div class="detail-msg">${escapeHtml(working ? t.shiftDetail.noDetail : t.shiftDetail.dayOff)}</div>`;
  return `
    <div class="dlg-head">
      <span class="code">${escapeHtml(code)}</span>
      ${when ? `<span class="when">${escapeHtml(when)}</span>` : ""}
    </div>
    ${meta ? `<div class="dlg-meta">${meta}</div>` : ""}
    ${body}`;
}


/** A shadow-scoped wrapper so the pop-up's styles never leak into the dashboard. */
class PerdisShiftDialog extends HTMLElement {
  render(hass, day, t) {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>${DETAIL_STYLE}${DIALOG_STYLE}</style>`
      + `<div class="dlg">${dayDetailBody(hass, day, t)}</div>`;
  }
}
if (!customElements.get("perdis-shift-dialog")) {
  customElements.define("perdis-shift-dialog", PerdisShiftDialog);
}


/** Open a modal with one day's full shift breakdown — what tapping a roster day shows. */
function openDayDialog(hass, day, t) {
  const content = document.createElement("perdis-shift-dialog");
  content.render(hass, day, t);
  const dialog = document.createElement("ha-dialog");
  dialog.heading = formatDay(hass, day.date, { weekday: "long", day: "numeric", month: "long" });
  dialog.open = true;
  dialog.appendChild(content);
  const close = document.createElement("mwc-button");
  close.setAttribute("slot", "primaryAction");
  close.setAttribute("dialogAction", "close");
  close.textContent = t.close;
  dialog.appendChild(close);
  dialog.addEventListener("closed", () => dialog.remove());
  document.body.appendChild(dialog);
}

class PerdisShiftDetailCard extends PerdisCardBase {
  static defaults() {
    return { show_course: true, show_relief: true, show_breaks: true };
  }

  static getConfigElement() {
    return document.createElement("perdis-shift-detail-card-editor");
  }

  /** The days from today on, which the arrows page through. */
  _upcoming() {
    const roster = this.attributes("roster");
    if (!roster) return null;
    const todayIso = new Date().toLocaleDateString("sv-SE");
    return (roster.days || []).filter((day) => day.date >= todayIso);
  }

  _step(delta, days) {
    const current = days.findIndex((day) => day.date === this._selectedDate);
    const next = Math.max(0, Math.min((current < 0 ? 0 : current) + delta, days.length - 1));
    this._selectedDate = days[next].date;
    this._render();
  }

  _goToday(days) {
    const todayIso = new Date().toLocaleDateString("sv-SE");
    this._selectedDate = days.some((day) => day.date === todayIso)
      ? todayIso : (days.find((day) => day.start && day.end) || days[0]).date;
    this._render();
  }

  _render() {
    const t = texts(this._hass);
    const config = this._config;
    const title = config.title || t.shiftDetail.title;
    const days = this._upcoming();
    if (days === null) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);
    if (!days.length) return this.frame(title, `<div class="empty">${escapeHtml(t.noShift)}</div>`);

    // Start on the next real shift; afterwards keep whatever the arrows last selected.
    if (!this._selectedDate || !days.some((day) => day.date === this._selectedDate)) {
      this._selectedDate = (days.find((day) => day.start && day.end) || days[0]).date;
    }
    const index = days.findIndex((day) => day.date === this._selectedDate);
    const day = days[index];
    const accent = accentOf(config, day.duty_type);
    const working = Boolean(day.start && day.end);
    const typeName = t.types[day.duty_type] || day.duty_type;
    const codeLabel = day.duty_type === "unknown" && day.duty ? day.duty : (working ? (day.duty || typeName) : typeName);
    const mainLine = working
      ? `${escapeHtml(codeLabel)} · ${formatTime(this._hass, day.start)}–${formatTime(this._hass, day.end)}`
      : escapeHtml(codeLabel);

    const nav = (step, icon) => {
      const disabled = (step < 0 && index === 0) || (step > 0 && index === days.length - 1);
      return `<button class="nav" data-step="${step}"${disabled ? " disabled" : ""}>`
        + `<ha-icon icon="${icon}"></ha-icon></button>`;
    };
    const destination = day.end_location && day.end_location !== day.start_location
      ? ` → ${escapeHtml(day.end_location)}` : "";
    const place = working && day.start_location
      ? `<div class="detail-place"><ha-icon icon="mdi:map-marker" style="--mdc-icon-size:16px"></ha-icon>${escapeHtml(day.start_location)}${destination}</div>`
      : "";
    const legs = (day.legs || []).filter((leg) => config.show_breaks !== false || !leg.is_break);
    const body = legs.length
      ? this._legsTable(legs, config, t)
      : `<div class="detail-msg">${escapeHtml(working ? t.shiftDetail.noDetail : t.shiftDetail.dayOff)}</div>`;

    const onToday = day.date === new Date().toLocaleDateString("sv-SE");
    const todayButton = onToday ? ""
      : `<div class="to-today"><button class="chip">${escapeHtml(t.today)}</button></div>`;

    this.frame(title, `
      <div class="content">
        ${todayButton}
        <div class="browse">
          ${nav(-1, "mdi:chevron-left")}
          <div class="day"><div class="main">${mainLine}</div>
            <div class="sub">${escapeHtml(relativeDay(this._hass, day.date))}</div></div>
          ${nav(1, "mdi:chevron-right")}
        </div>
        ${place}${body}
      </div>`, DETAIL_STYLE, accent);
    this.shadowRoot.querySelectorAll(".browse .nav").forEach((button) =>
      button.addEventListener("click", () => this._step(Number(button.dataset.step), days)));
    this.shadowRoot.querySelector(".to-today .chip")?.addEventListener("click", () => this._goToday(days));
  }

  _legsTable(legs, config, t) {
    return legsTable(this._hass, legs, config, t);
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const SHIFT_DETAIL_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_content", [
    { type: "grid", schema: [field.boolean("show_course"), field.boolean("show_relief")] },
    field.boolean("show_breaks"),
  ]),
  section(hass, "sec_appearance", [
    { type: "grid", schema: [field.showHeader, field.icon] },
    field.accent,
  ]),
  section(hass, "sec_behavior", [field.tapAction]),
];

// --- Calendar (wraps the built-in calendar card, entity found automatically) --------------------

class PerdisCalendarCard extends PerdisCardBase {
  static defaults() {
    return { initial_view: "dayGridMonth" };
  }

  static getConfigElement() {
    return document.createElement("perdis-calendar-card-editor");
  }

  setConfig(config) {
    this._config = { ...this.constructor.defaults(), ...config };
    this._inner = null;
    if (this._hass) {
      this._entities = findEntities(this._hass, this._config.device_id);
      this._build();
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._entities = findEntities(hass, this._config?.device_id);
    // The built-in calendar card fetches its own events, so it just needs `hass` on every update.
    if (this._inner) this._inner.hass = hass;
    else this._build();
  }

  get hass() {
    return this._hass;
  }

  async _build() {
    if (this._building || this._inner) return;
    this._building = true;
    const entityId = this._entities?.calendar;
    if (!entityId) {
      this.shadowRoot.innerHTML =
        `<style>${BASE_STYLE}</style><ha-card><div class="empty">${escapeHtml(texts(this._hass).noAccount)}</div></ha-card>`;
      this._building = false;
      return;
    }
    try {
      const helpers = await window.loadCardHelpers();
      const card = helpers.createCardElement({
        type: "calendar",
        initial_view: this._config.initial_view || "dayGridMonth",
        title: this._config.title || "",
        entities: [entityId],
      });
      card.hass = this._hass;
      this._inner = card;
      this.shadowRoot.innerHTML = "";
      this.shadowRoot.appendChild(card);
    } catch (error) {
      this.shadowRoot.innerHTML =
        `<style>${BASE_STYLE}</style><ha-card><div class="empty">${escapeHtml(String(error))}</div></ha-card>`;
    }
    this._building = false;
  }

  getCardSize() {
    return 9;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const CALENDAR_EDITOR = (hass) => [
  field.device, field.title,
  section(hass, "sec_content", [
    field.select("initial_view", ["dayGridMonth", "listWeek", "listMonth"].map(
      (value) => ({ value, label: texts(hass).views[value] }))),
  ]),
];

// --- All-in-one card (a tab bar over the other cards) -------------------------------------------

const MASTER_STYLE = `
  .tabbar { display: flex; gap: 2px; padding: 6px 6px 0; overflow-x: auto; scrollbar-width: none;
            border-bottom: 1px solid var(--divider-color); }
  .tabbar::-webkit-scrollbar { display: none; }
  .tab { flex: 1 0 auto; display: inline-flex; flex-direction: column; align-items: center; gap: 3px;
         padding: 8px 14px; border: none; background: none; cursor: pointer; font: inherit;
         font-size: 0.78rem; color: var(--secondary-text-color); border-bottom: 2px solid transparent;
         transition: color 120ms ease; }
  .tab:hover { color: var(--primary-text-color); }
  .tab.on { color: var(--primary-color); border-bottom-color: var(--primary-color); font-weight: 600; }
  .tab ha-icon { --mdc-icon-size: 22px; }
  .panel { min-height: 40px; }
  .brand { display: flex; align-items: center; gap: 12px; padding: 14px 16px 6px; }
  .brand .badge { background: var(--primary-color); color: var(--text-primary-color, #fff); font-weight: 700;
                  letter-spacing: 0.5px; padding: 5px 11px; border-radius: 10px; font-size: 0.95rem; }
  .brand .logo { height: 34px; max-width: 140px; object-fit: contain; }
  .brand .who { display: flex; flex-direction: column; flex: 1 1 auto; min-width: 0; }
  .brand .name { font-size: 1.05rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .brand .stamp { font-size: 0.75rem; color: var(--secondary-text-color); line-height: 1.3; }
  .brand .stamp.warn { color: var(--warning-color, #ffa600); }
  .refresh { flex: 0 0 auto; width: 40px; height: 40px; border: none; border-radius: 50%; cursor: pointer;
             display: inline-flex; align-items: center; justify-content: center; font: inherit;
             color: var(--primary-color);
             background: color-mix(in srgb, var(--primary-color) 14%, var(--card-background-color));
             transition: background 150ms ease, transform 150ms ease, color 150ms ease; }
  .refresh:hover { background: color-mix(in srgb, var(--primary-color) 24%, var(--card-background-color)); }
  .refresh:active { transform: scale(0.9); }
  .refresh[disabled] { cursor: default; }
  .refresh.busy ha-icon { animation: perdis-spin 1s linear infinite; }
  .refresh.ok { color: var(--success-color, #43a047);
                background: color-mix(in srgb, var(--success-color, #43a047) 16%, var(--card-background-color)); }
  @keyframes perdis-spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .refresh.busy ha-icon { animation-duration: 3s; } }
`;

// The panels the all-in-one card switches between: each one simply reuses the matching standalone
// card, embedded without its own frame. One entry here is all a new panel needs.
const PANELS = {
  shift: { type: "perdis-shift-card", icon: "mdi:bus-clock", label: (t) => t.nextShift },
  roster: { type: "perdis-roster-card", icon: "mdi:calendar-text", label: (t) => t.roster },
  detail: { type: "perdis-shift-detail-card", icon: "mdi:table-clock", label: (t) => t.shiftDetail.title },
  accounts: { type: "perdis-accounts-card", icon: "mdi:scale-balance", label: (t) => t.accounts },
  calendar: { type: "perdis-calendar-card", icon: "mdi:calendar-month", label: (t) => t.calendar },
  swaps: { type: "perdis-swap-card", icon: "mdi:swap-horizontal", label: (t) => t.swaps },
};
const PANEL_KEYS = Object.keys(PANELS);

class PerdisMasterCard extends PerdisCardBase {
  static defaults() {
    return { tabs: ["shift", "roster", "accounts", "calendar"] };
  }

  static getConfigElement() {
    return document.createElement("perdis-card-editor");
  }

  _activeTabs() {
    const wanted = (this._config.tabs || []).filter((key) => PANELS[key]);
    return wanted.length ? wanted : this.constructor.defaults().tabs;
  }

  /** The live child card for a tab, created once and kept so its state survives tab switches. */
  _panel(key) {
    this._cards = this._cards || {};
    if (!this._cards[key]) {
      const card = document.createElement(PANELS[key].type);
      card._embedded = true;  // render without its own ha-card; the master provides the one frame
      const config = { show_header: false };
      if (this._config.device_id) config.device_id = this._config.device_id;
      card.setConfig(config);
      this._cards[key] = card;
    }
    this._cards[key].hass = this._hass;
    return this._cards[key];
  }

  /**
   * The header: the operator's logo (or, without one, its name as a badge) and the account.
   * The roster sensor tells which operator the account belongs to; `logo` is an image address of
   * the user's own, e.g. /local/logo.png, since the operators' logos are not ours to ship.
   */
  _brand() {
    const roster = this.attributes("roster") || {};
    const operator = roster.operator || "";
    const account = roster.account || "";
    const name = this._config.title
      || (operator && account.startsWith(`${operator} - `) ? account.slice(operator.length + 3) : account);
    const badge = operator ? `<span class="badge">${escapeHtml(operator)}</span>` : "";
    const mark = this._config.logo
      ? `<img class="logo" src="${escapeHtml(this._config.logo)}" alt="${escapeHtml(operator)}">`
      : (badge || `<ha-icon icon="${escapeHtml(this._config.icon || DEFAULT_HEADER_ICON)}"></ha-icon>`);
    if (!name && !mark) return "";
    const t = texts(this._hass);
    const refresh = this._entities?.refresh
      ? `<button class="refresh${this._refreshing ? " busy" : ""}${this._flash ? " ok" : ""}"`
        + ` aria-label="${escapeHtml(t.refreshRoster)}" title="${escapeHtml(t.refreshRoster)}"`
        + `${this._refreshing ? " disabled" : ""}>`
        + `<ha-icon icon="${this._flash ? "mdi:check" : "mdi:refresh"}"></ha-icon></button>`
      : "";
    return `<div class="brand" data-badge="${escapeHtml(badge)}">${mark}`
      + `<div class="who"><span class="name">${escapeHtml(name)}</span>`
      + `<span class="stamp${roster.online === false ? " warn" : ""}">${escapeHtml(this._stamp())}</span></div>`
      + `${refresh}</div>`;
  }

  /** "Aktualisiert vor 5 Minuten", or "Aktualisiere…" while a refresh runs. */
  _stamp() {
    const t = texts(this._hass);
    if (this._refreshing) return t.updating;
    const ago = formatAgo(this._hass, this._lastRefresh());
    return ago ? `${t.updated} ${ago}` : "";
  }

  _lastRefresh() {
    const id = this._entities?.last_refresh;
    const state = id ? this._hass.states[id]?.state : null;
    return state && state !== "unknown" && state !== "unavailable" ? state : null;
  }

  /** Ask the portal now (the refresh button entity) and spin until the roster was fetched again. */
  _refresh() {
    const id = this._entities?.refresh;
    if (!id || this._refreshing) return;
    this._refreshing = true;
    this._refreshBaseline = this._lastRefresh();
    this._hass.callService("button", "press", { entity_id: id });
    // A portal that does not answer must not leave the button spinning for ever.
    clearTimeout(this._refreshTimeout);
    this._refreshTimeout = setTimeout(() => this._finishRefresh(false), 30000);
    this._render();
  }

  _finishRefresh(succeeded) {
    clearTimeout(this._refreshTimeout);
    this._refreshing = false;
    this._flash = succeeded;
    if (succeeded) setTimeout(() => { this._flash = false; this._render(); }, 1800);
    this._render();
  }

  connectedCallback() {
    // The "vor 5 Minuten" caption ages on its own, so it is refreshed without a full render.
    this._ticker = setInterval(() => {
      const stamp = this.shadowRoot?.querySelector(".brand .stamp");
      if (stamp && this._hass) stamp.textContent = this._stamp();
    }, 30000);
  }

  disconnectedCallback() {
    clearInterval(this._ticker);
    clearTimeout(this._refreshTimeout);
  }

  _render() {
    if (!this._hass || !this._config) return;
    const t = texts(this._hass);
    const tabs = this._activeTabs();
    if (!this._active || !tabs.includes(this._active)) this._active = tabs[0];
    // The refresh is done as soon as the last-refresh sensor shows a newer moment than at the click.
    if (this._refreshing && this._lastRefresh() !== this._refreshBaseline) {
      this._refreshing = false;
      this._flash = true;
      clearTimeout(this._refreshTimeout);
      setTimeout(() => { this._flash = false; this._render(); }, 1800);
    }
    const header = this._config.show_header !== false ? this._brand() : "";
    const bar = tabs.map((key) => {
      const panel = PANELS[key];
      return `<button class="tab${key === this._active ? " on" : ""}" data-tab="${key}">`
        + `<ha-icon icon="${panel.icon}"></ha-icon><span>${escapeHtml(panel.label(t))}</span></button>`;
    }).join("");
    this.shadowRoot.innerHTML = `<style>${BASE_STYLE}${MASTER_STYLE}</style>
      <ha-card>
        ${header}
        <div class="tabbar" role="tablist">${bar}</div>
        <div class="panel"></div>
      </ha-card>`;
    this.shadowRoot.querySelector(".panel").appendChild(this._panel(this._active));
    const logo = this.shadowRoot.querySelector(".brand .logo");
    if (logo) {
      logo.addEventListener("error", () => {
        const fallback = logo.closest(".brand")?.dataset.badge;
        if (fallback) logo.outerHTML = fallback; else logo.remove();
      });
    }
    this.shadowRoot.querySelector(".refresh")?.addEventListener("click", () => this._refresh());
    this.shadowRoot.querySelectorAll(".tab").forEach((button) =>
      button.addEventListener("click", () => {
        this._active = button.dataset.tab;
        this._render();
      }));
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, rows: "auto" };
  }
}

const EDITOR_STYLE = `
  .tabs-editor { margin-top: 14px; }
  .tabs-editor .hdr { font-size: 0.95rem; font-weight: 500; margin: 4px 2px 8px; }
  .trow { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 10px;
          background: var(--secondary-background-color); margin-bottom: 6px; }
  .trow.off { opacity: 0.5; }
  .trow .lbl { flex: 1; }
  .trow input { width: 18px; height: 18px; accent-color: var(--primary-color); cursor: pointer; }
  .trow button { border: none; background: none; cursor: pointer; color: var(--primary-text-color);
                 display: inline-flex; padding: 2px; border-radius: 6px; }
  .trow button:not([disabled]):hover { background: var(--divider-color); }
  .trow button[disabled] { opacity: 0.3; cursor: default; }
  .trow ha-icon { --mdc-icon-size: 20px; }
`;

// The all-in-one card's editor: the plain fields through ha-form, plus a tab list the user can
// switch on and off and reorder with the arrows — a plain multi-select cannot set an order.
class PerdisMasterEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _emit(patch) {
    const config = { ...this._config, ...patch };
    for (const key of Object.keys(config)) {
      const value = config[key];
      if (value === "" || value === undefined || value === null || (Array.isArray(value) && !value.length)) {
        delete config[key];
      }
    }
    this._config = config;
    fireEvent(this, "config-changed", { config });
    this._render();
  }

  _enabled() {
    const tabs = (this._config.tabs || []).filter((key) => PANELS[key]);
    return tabs.length ? tabs : [...PerdisMasterCard.defaults().tabs];
  }

  _toggle(key) {
    const tabs = this._enabled();
    this._emit({ tabs: tabs.includes(key) ? tabs.filter((other) => other !== key) : [...tabs, key] });
  }

  _move(key, delta) {
    const tabs = this._enabled();
    const index = tabs.indexOf(key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= tabs.length) return;
    [tabs[index], tabs[target]] = [tabs[target], tabs[index]];
    this._emit({ tabs });
  }

  _render() {
    if (!this._hass || !this._config) return;
    const t = texts(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        const value = { ...event.detail.value };
        delete value.tabs;  // the tabs are set by the list below, not the form
        this._emit(value);
      });
      this.appendChild(this._form);
      this._list = document.createElement("div");
      this._list.className = "tabs-editor";
      this.appendChild(this._list);
    }
    const formData = { ...this._config };
    delete formData.tabs;
    this._form.hass = this._hass;
    this._form.data = formData;
    this._form.schema = [
      field.device, field.title, { name: "logo", selector: { text: {} } },
      { type: "grid", schema: [field.showHeader, field.icon] },
    ];
    this._form.computeLabel = (schema) => t.editor[schema.name] || schema.name;
    this._form.computeHelper = (schema) => t.helper[schema.name] || "";

    const enabled = this._enabled();
    const enabledSet = new Set(enabled);
    const ordered = [...enabled, ...PANEL_KEYS.filter((key) => !enabledSet.has(key))];
    this._list.innerHTML = `<style>${EDITOR_STYLE}</style>
      <div class="hdr">${escapeHtml(t.editor.tabs)}</div>
      ${ordered.map((key) => {
        const on = enabledSet.has(key);
        const pos = enabled.indexOf(key);
        return `<div class="trow${on ? "" : " off"}">
          <input type="checkbox" data-toggle="${key}" ${on ? "checked" : ""}>
          <span class="lbl">${escapeHtml(PANELS[key].label(t))}</span>
          <button data-up="${key}"${on && pos > 0 ? "" : " disabled"}><ha-icon icon="mdi:chevron-up"></ha-icon></button>
          <button data-down="${key}"${on && pos >= 0 && pos < enabled.length - 1 ? "" : " disabled"}><ha-icon icon="mdi:chevron-down"></ha-icon></button>
        </div>`;
      }).join("")}`;
    this._list.querySelectorAll("[data-toggle]").forEach((box) =>
      box.addEventListener("change", () => this._toggle(box.dataset.toggle)));
    this._list.querySelectorAll("[data-up]").forEach((button) =>
      button.addEventListener("click", () => this._move(button.dataset.up, -1)));
    this._list.querySelectorAll("[data-down]").forEach((button) =>
      button.addEventListener("click", () => this._move(button.dataset.down, 1)));
  }
}
if (!customElements.get("perdis-card-editor")) {
  customElements.define("perdis-card-editor", PerdisMasterEditor);
}

// --- Registration --------------------------------------------------------------------------------

const CARDS = [
  ["perdis-card", PerdisMasterCard, null, "PERDIS · All-in-one",
    "Everything in one card: a tab bar switches between your next shift, the roster, your accounts "
    + "and the calendar. Mobile-first, like the app."],
  ["perdis-shift-card", PerdisShiftCard, SHIFT_EDITOR, "PERDIS · Next shift",
    "Your next shift with a countdown, reporting point, wake-up and leave-home time."],
  ["perdis-roster-card", PerdisRosterCard, ROSTER_EDITOR, "PERDIS · Roster list",
    "The coming days by week; tap a day to see its full shift breakdown."],
  ["perdis-accounts-card", PerdisAccountsCard, ACCOUNTS_EDITOR, "PERDIS · Time accounts",
    "Overtime, vacation, weekend points and free weekends at a glance."],
  ["perdis-shift-detail-card", PerdisShiftDetailCard, SHIFT_DETAIL_EDITOR, "PERDIS · Shift browser",
    "Page through the shifts with arrows; each one broken into its legs as a table."],
  ["perdis-calendar-card", PerdisCalendarCard, CALENDAR_EDITOR, "PERDIS · Calendar",
    "A month calendar of the roster; finds your calendar entity on its own, no id to type."],
  ["perdis-swap-card", PerdisSwapCard, SWAP_EDITOR, "PERDIS · Duty swaps",
    "The open shift swaps the portal lists, with the period new requests may cover."],
];

window.customCards = window.customCards || [];
for (const [type, cardClass, editorBuilder, name, description] of CARDS) {
  if (!customElements.get(type)) customElements.define(type, cardClass);
  if (!customElements.get(`${type}-editor`)) customElements.define(`${type}-editor`, editorFor(editorBuilder));
  if (!window.customCards.some((card) => card.type === type)) {
    window.customCards.push({
      type, name, description, preview: true,
      documentationURL: "https://github.com/seb5594/hass-perdis_roster-integration#-dashboard-cards",
    });
  }
}

console.info(`%c PERDIS-CARDS %c ${VERSION} `, "background:#1877A5;color:#fff;font-weight:600", "background:#ddd;color:#333");
