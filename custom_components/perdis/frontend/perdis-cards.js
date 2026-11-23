/**
 * Dashboard cards of the Perdis Duty Roster integration.
 *
 *   perdis-shift-card     the next shift: times, place, countdown, wake-up and leave-home time
 *   perdis-roster-card    the coming days, grouped by week, with days off and changes marked
 *   perdis-accounts-card  overtime, vacation, weekend points and free weekends at a glance
 *
 * The integration loads this file on every dashboard, so the cards appear in the card picker
 * without adding a resource. They need no configuration: without a `device_id` they show the
 * first Perdis account. The entities of an account are found by their `perdis_role` attribute,
 * so renaming an entity never breaks a card.
 *
 * Plain web components without any library keep the file small and independent of the
 * frontend version of Home Assistant.
 */

const VERSION = "2026.11.23";
const DOMAIN = "perdis";

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
    week: "Week",
    changed: "changed",
    split: "split",
    hours: "h",
    days: "days",
    points: "pts",
    overtime: "Overtime balance",
    vacation: "Vacation left",
    planned: "planned",
    weekendPoints: "Weekend points",
    average: "average",
    freeWeekends: "Free weekends",
    nextFreeWeekend: "next",
    plannedWeek: "Planned this week",
    offline: "Portal offline – showing the saved roster",
    types: {
      work: "Duty", reserve: "Reserve", training: "Training", free: "Day off", vacation: "Vacation",
      compensation: "Time off", sick: "Sick", unknown: "Unknown",
    },
    categories: { early: "Early", day: "Day", late: "Late", night: "Night", split: "Split" },
    editor: {
      device_id: "Perdis account (empty: the first one)",
      title: "Title (empty: default)",
      days: "Days to show",
      show_days_off: "Show days off",
      compact: "Compact rows",
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
    week: "KW",
    changed: "geändert",
    split: "geteilt",
    hours: "Std.",
    days: "Tage",
    points: "Pkt.",
    overtime: "Zeitkonto",
    vacation: "Resturlaub",
    planned: "verplant",
    weekendPoints: "WE-Punkte",
    average: "Schnitt",
    freeWeekends: "Freie Wochenenden",
    nextFreeWeekend: "nächstes",
    plannedWeek: "Geplant diese Woche",
    offline: "Portal nicht erreichbar – gespeicherter Dienstplan",
    types: {
      work: "Dienst", reserve: "Bereitschaft", training: "Schulung", free: "Frei", vacation: "Urlaub",
      compensation: "Ausgleich", sick: "Krank", unknown: "Unbekannt",
    },
    categories: { early: "Früh", day: "Mittel", late: "Spät", night: "Nacht", split: "Geteilt" },
    editor: {
      device_id: "Perdis-Konto (leer: das erste)",
      title: "Titel (leer: Standard)",
      days: "Angezeigte Tage",
      show_days_off: "Freie Tage anzeigen",
      compact: "Kompakte Zeilen",
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

function formatCountdown(minutes) {
  if (minutes === null || minutes === undefined) return "";
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const rest = minutes % 60;
  if (days > 0) return `${days} d ${hours} h`;
  if (hours > 0) return `${hours} h ${String(rest).padStart(2, "0")} min`;
  return `${rest} min`;
}

function formatNumber(hass, value, digits = 1) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "–";
  return new Intl.NumberFormat(hass?.locale?.language || "en", {
    maximumFractionDigits: digits, minimumFractionDigits: 0,
  }).format(Number(value));
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
  .header { display: flex; align-items: center; gap: 10px; padding: 16px 16px 4px; }
  .header .title { font-size: 1.15rem; font-weight: 500; flex: 1; }
  .content { padding: 8px 16px 16px; }
  .muted { color: var(--secondary-text-color); }
  .empty { padding: 16px; color: var(--secondary-text-color); }
  .pill { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 2px 10px;
          font-size: 0.8rem; font-weight: 500; white-space: nowrap; }
  .banner { margin: 0 16px 8px; padding: 6px 10px; border-radius: 8px; font-size: 0.85rem;
            background: rgba(var(--rgb-warning-color, 255, 166, 0), 0.15); color: var(--warning-color, #ffa600); }
  ha-icon { --mdc-icon-size: 20px; }
  .clickable { cursor: pointer; }
`;

class PerdisCardBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._signature = "";
  }

  setConfig(config) {
    this._config = { ...config };
    this._signature = "";
    if (this._hass) this._render();
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

  moreInfo(role) {
    const entityId = this._entities?.[role];
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  frame(title, body, extraStyle = "") {
    const roster = this.attributes("roster");
    const offline = roster && roster.online === false ? `<div class="banner">${escapeHtml(texts(this._hass).offline)}</div>` : "";
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${extraStyle}</style>
      <ha-card>
        <div class="header"><ha-icon icon="mdi:bus-clock"></ha-icon><span class="title">${escapeHtml(title)}</span></div>
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

function editorFor(fields) {
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
          for (const key of Object.keys(config)) if (config[key] === "" || config[key] === undefined) delete config[key];
          this._config = config;
          this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
        });
        this.appendChild(this._form);
      }
      const labels = texts(this._hass).editor;
      this._form.hass = this._hass;
      this._form.data = this._config;
      this._form.schema = [
        { name: "device_id", selector: { device: { integration: DOMAIN } } },
        { name: "title", selector: { text: {} } },
        ...fields,
      ];
      this._form.computeLabel = (schema) => labels[schema.name] || schema.name;
    }
  };
}

// --- Next shift ----------------------------------------------------------------------------------

const SHIFT_STYLE = `
  .duty { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  .duty .code { font-size: 2rem; font-weight: 600; line-height: 1.1; }
  .when { margin-top: 2px; font-size: 1rem; }
  .times { font-size: 1.6rem; font-weight: 500; margin: 10px 0 2px; letter-spacing: 0.5px; }
  .place { display: flex; align-items: center; gap: 6px; margin-top: 6px; }
  .lines { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .line { background: var(--secondary-background-color); border-radius: 6px; padding: 1px 8px; font-weight: 600; font-size: 0.85rem; }
  .progress { height: 6px; border-radius: 3px; background: var(--divider-color); margin-top: 12px; overflow: hidden; }
  .progress > div { height: 100%; background: var(--accent); }
  .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; margin-top: 14px; }
  .fact { background: var(--secondary-background-color); border-radius: 10px; padding: 8px 10px; }
  .fact .label { font-size: 0.75rem; color: var(--secondary-text-color); display: flex; align-items: center; gap: 4px; }
  .fact .value { font-size: 1.05rem; font-weight: 500; margin-top: 2px; }
  .fact.warning { background: rgba(var(--rgb-error-color, 219, 68, 55), 0.15); }
  .fact.warning .value { color: var(--error-color, #db4437); }
`;

class PerdisShiftCard extends PerdisCardBase {
  static getConfigElement() {
    return document.createElement("perdis-shift-card-editor");
  }

  _render() {
    const t = texts(this._hass);
    const title = this._config?.title || t.nextShift;
    const shift = this.attributes("next_shift");
    if (shift === null) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);
    if (!shift.date) return this.frame(title, `<div class="empty">${escapeHtml(t.noShift)}</div>`);

    const category = shift.category || "day";
    const accent = TYPE_COLORS[shift.duty_type] || TYPE_COLORS.work;
    const countdown = shift.running
      ? `<span class="pill" style="background:${accent};color:var(--text-primary-color,#fff)">${escapeHtml(t.running)} · ${escapeHtml(t.endsIn)} ${formatCountdown(shift.minutes_until_end)}</span>`
      : `<span class="pill" style="background:var(--secondary-background-color)">${escapeHtml(t.startsIn)} ${formatCountdown(shift.minutes_until_start)}</span>`;
    const progress = shift.running && shift.start && shift.end
      ? Math.min(100, Math.max(0, ((Date.now() - new Date(shift.start)) / (new Date(shift.end) - new Date(shift.start))) * 100))
      : null;
    const lines = (shift.lines || []).map((line) => `<span class="line">${escapeHtml(line)}</span>`).join("");
    const rest = shift.rest_before_hours;
    const facts = [
      !shift.running && shift.wake_up ? [t.wakeUp, "mdi:alarm", formatTime(this._hass, shift.wake_up), false] : null,
      !shift.running && shift.leave_home ? [t.leaveHome, "mdi:home-export-outline", formatTime(this._hass, shift.leave_home), false] : null,
      shift.hours ? [t.paidHours, "mdi:timer-outline", `${formatNumber(this._hass, shift.hours, 2)} ${t.hours}`, false] : null,
      !shift.running && rest !== null && rest !== undefined
        ? [shift.short_rest ? t.shortRest : t.rest, "mdi:bed-clock", `${formatNumber(this._hass, rest)} ${t.hours}`, shift.short_rest]
        : null,
    ].filter(Boolean).map(([label, icon, value, warning]) => `
      <div class="fact${warning ? " warning" : ""}">
        <div class="label"><ha-icon icon="${icon}" style="--mdc-icon-size:14px"></ha-icon>${escapeHtml(label)}</div>
        <div class="value">${escapeHtml(value)}</div>
      </div>`).join("");

    this.frame(title, `
      <div class="content clickable" style="--accent:${accent}">
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
        ${shift.start_location ? `<div class="place"><ha-icon icon="mdi:map-marker"></ha-icon>${escapeHtml(shift.start_location)}${shift.end_location && shift.end_location !== shift.start_location ? ` → ${escapeHtml(shift.end_location)}` : ""}</div>` : ""}
        ${lines ? `<div class="lines">${lines}</div>` : ""}
        ${progress !== null ? `<div class="progress"><div style="width:${progress.toFixed(1)}%"></div></div>` : ""}
        ${facts ? `<div class="facts">${facts}</div>` : ""}
      </div>`, SHIFT_STYLE);
    this.shadowRoot.querySelector(".content")?.addEventListener("click", () => this.moreInfo("next_shift"));
  }

  getGridOptions() {
    return { columns: 12, rows: 4, min_rows: 3 };
  }
}

// --- Roster --------------------------------------------------------------------------------------

const ROSTER_STYLE = `
  .week { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px;
          color: var(--secondary-text-color); margin: 12px 0 4px; }
  .week:first-child { margin-top: 0; }
  .day { display: grid; grid-template-columns: 58px 6px 1fr auto; gap: 10px; align-items: center;
         padding: 7px 8px; border-radius: 10px; }
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
  static getConfigElement() {
    return document.createElement("perdis-roster-card-editor");
  }

  static getStubConfig(hass) {
    return { ...PerdisCardBase.getStubConfig(hass), days: 14 };
  }

  _render() {
    const t = texts(this._hass);
    const title = this._config?.title || t.roster;
    const roster = this.attributes("roster");
    if (roster === null) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);
    const showOff = this._config?.show_days_off !== false;
    const limit = Number(this._config?.days || 14);
    const days = (roster.days || []).slice(0, limit).filter((day) => showOff || !["free", "vacation", "compensation"].includes(day.duty_type));
    if (!days.length) return this.frame(title, `<div class="empty">${escapeHtml(t.noDays)}</div>`);

    const todayIso = new Date().toLocaleDateString("sv-SE");
    let currentWeek = null;
    const rows = days.map((day) => {
      const week = isoWeek(parseDay(day.date));
      const header = week !== currentWeek ? `<div class="week">${escapeHtml(t.week)} ${week}</div>` : "";
      currentWeek = week;
      const color = TYPE_COLORS[day.duty_type] || TYPE_COLORS.unknown;
      const typeName = t.types[day.duty_type] || day.duty_type;
      const hasTimes = day.start && day.end;
      const heading = hasTimes
        ? `${escapeHtml(day.duty || typeName)} · ${formatTime(this._hass, day.start)}–${formatTime(this._hass, day.end)}`
        : escapeHtml(day.duty && day.duty.toUpperCase() !== typeName.toUpperCase() ? `${typeName} (${day.duty})` : typeName);
      const sub = [day.start_location, (day.lines || []).join(", "), day.remark].filter(Boolean).join(" · ");
      const tags = [
        day.changed ? `<span class="tag changed">${escapeHtml(t.changed)}</span>` : "",
        day.split_shift ? `<span class="tag">${escapeHtml(t.split)}</span>` : "",
        day.category && hasTimes ? `<span class="tag">${escapeHtml(t.categories[day.category] || "")}</span>` : "",
      ].join("");
      const [weekday, ...rest] = formatDay(this._hass, day.date).split(/,?\s+/);
      return `${header}
        <div class="day${day.date === todayIso ? " today" : ""}">
          <div class="date"><b>${escapeHtml(weekday)}</b>${escapeHtml(rest.join(" "))}</div>
          <div class="bar" style="background:${color}"></div>
          <div class="main"><div class="title">${heading}</div>${sub ? `<div class="sub">${escapeHtml(sub)}</div>` : ""}</div>
          <div class="tags">${tags}</div>
        </div>`;
    }).join("");
    this.frame(title, `<div class="content clickable${this._config?.compact ? " compact" : ""}">${rows}</div>`, ROSTER_STYLE);
    this.shadowRoot.querySelector(".content")?.addEventListener("click", () => this.moreInfo("roster"));
  }

  getCardSize() {
    return Math.min(2 + Number(this._config?.days || 14), 16);
  }

  getGridOptions() {
    return { columns: 12, rows: 8, min_rows: 4 };
  }
}

// --- Accounts ------------------------------------------------------------------------------------

const ACCOUNTS_STYLE = `
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  .tile { background: var(--secondary-background-color); border-radius: 12px; padding: 10px 12px; cursor: pointer; }
  .tile .label { font-size: 0.78rem; color: var(--secondary-text-color); display: flex; align-items: center; gap: 6px; }
  .tile .value { font-size: 1.5rem; font-weight: 600; margin-top: 4px; }
  .tile .value small { font-size: 0.85rem; font-weight: 400; color: var(--secondary-text-color); margin-left: 3px; }
  .tile .hint { font-size: 0.78rem; color: var(--secondary-text-color); margin-top: 2px; }
  .positive { color: var(--success-color, #43a047); }
  .negative { color: var(--error-color, #db4437); }
  .meter { position: relative; height: 6px; border-radius: 3px; background: var(--divider-color); margin-top: 8px; }
  .meter .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--primary-color); }
  .meter .mark { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--primary-text-color); }
`;

class PerdisAccountsCard extends PerdisCardBase {
  static getConfigElement() {
    return document.createElement("perdis-accounts-card-editor");
  }

  _render() {
    const t = texts(this._hass);
    const hass = this._hass;
    const title = this._config?.title || t.accounts;
    if (!this._entities?.roster) return this.frame(title, `<div class="empty">${escapeHtml(t.noAccount)}</div>`);

    const overtime = numericState(hass, this._entities.overtime);
    const vacation = numericState(hass, this._entities.vacation);
    const vacationInfo = this.attributes("vacation") || {};
    const points = numericState(hass, this._entities.weekend_points);
    const pointsInfo = this.attributes("weekend_points") || {};
    const freeWeekends = numericState(hass, this._entities.free_weekends);
    const nextFree = hass.states[this._entities.next_free_weekend]?.state;
    const plannedWeek = numericState(hass, this._entities.planned_week);

    const tile = (role, icon, label, value, unit, hint = "", extra = "", tone = "") => `
      <div class="tile" data-role="${role}">
        <div class="label"><ha-icon icon="${icon}" style="--mdc-icon-size:16px"></ha-icon>${escapeHtml(label)}</div>
        <div class="value ${tone}">${value}<small>${escapeHtml(unit)}</small></div>
        ${hint ? `<div class="hint">${hint}</div>` : ""}${extra}
      </div>`;

    const average = pointsInfo.group_average;
    let meter = "";
    if (points !== null && average !== null && average !== undefined) {
      const scale = Math.max(points, average) * 1.25 || 1;
      meter = `<div class="meter"><div class="fill" style="width:${(points / scale) * 100}%"></div>
        <div class="mark" style="left:${(average / scale) * 100}%"></div></div>`;
    }
    const nextFreeText = nextFree && !["unknown", "unavailable"].includes(nextFree)
      ? `${escapeHtml(t.nextFreeWeekend)}: ${escapeHtml(formatDay(hass, nextFree))}` : "";

    const tiles = [
      tile("overtime", "mdi:timer-sand", t.overtime,
        overtime === null ? "–" : `${overtime > 0 ? "+" : ""}${formatNumber(hass, overtime)}`, t.hours, "", "",
        overtime === null ? "" : overtime >= 0 ? "positive" : "negative"),
      tile("vacation", "mdi:island", t.vacation, formatNumber(hass, vacation), t.days,
        vacationInfo.planned_days ? `${formatNumber(hass, vacationInfo.planned_days)} ${escapeHtml(t.planned)}` : ""),
      tile("weekend_points", "mdi:scale-balance", t.weekendPoints, formatNumber(hass, points), t.points,
        average !== null && average !== undefined ? `${escapeHtml(t.average)} ${formatNumber(hass, average)}` : "", meter),
      tile("free_weekends", "mdi:calendar-weekend", t.freeWeekends, formatNumber(hass, freeWeekends, 0), "", nextFreeText),
      tile("planned_week", "mdi:calendar-week", t.plannedWeek, formatNumber(hass, plannedWeek), t.hours),
    ].join("");

    this.frame(title, `<div class="content"><div class="tiles">${tiles}</div></div>`, ACCOUNTS_STYLE);
    this.shadowRoot.querySelectorAll(".tile").forEach((element) => {
      element.addEventListener("click", () => this.moreInfo(element.dataset.role));
    });
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 12, rows: 3, min_rows: 2 };
  }
}

// --- Registration --------------------------------------------------------------------------------

const CARDS = [
  ["perdis-shift-card", PerdisShiftCard, [], "Perdis: next shift",
    "Your next shift with countdown, place, wake-up and leave-home time."],
  ["perdis-roster-card", PerdisRosterCard, [
    { name: "days", selector: { number: { min: 3, max: 42, mode: "box" } } },
    { name: "show_days_off", selector: { boolean: {} } },
    { name: "compact", selector: { boolean: {} } },
  ], "Perdis: roster", "The coming days by week, with days off and roster changes marked."],
  ["perdis-accounts-card", PerdisAccountsCard, [], "Perdis: accounts",
    "Overtime, vacation, weekend points and free weekends at a glance."],
];

window.customCards = window.customCards || [];
for (const [type, cardClass, editorFields, name, description] of CARDS) {
  if (!customElements.get(type)) customElements.define(type, cardClass);
  if (!customElements.get(`${type}-editor`)) customElements.define(`${type}-editor`, editorFor(editorFields));
  if (!window.customCards.some((card) => card.type === type)) {
    window.customCards.push({
      type, name, description, preview: true,
      documentationURL: "https://github.com/seb5594/hass-init_perdis-integration#-dashboard-cards",
    });
  }
}

console.info(`%c PERDIS-CARDS %c ${VERSION} `, "background:#1877A5;color:#fff;font-weight:600", "background:#ddd;color:#333");
