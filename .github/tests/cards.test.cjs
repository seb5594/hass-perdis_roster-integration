// Tests of the dashboard cards that need neither a browser nor Home Assistant: the script is loaded
// into a tiny stand-in for the DOM, and the cards are asked what they would show.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");

const SOURCE = fs.readFileSync(
  path.join(__dirname, "../../custom_components/perdis_roster/frontend/perdis-cards.js"), "utf8");

/** A fresh world: custom elements that can be defined later, and elements that remember their HTML. */
function world() {
  const defined = {};
  const waiting = {};
  const customElements = {
    get: (name) => defined[name],
    define: (name, cls) => { defined[name] = cls; (waiting[name] || []).forEach((resolve) => resolve()); },
    whenDefined: (name) => (defined[name] ? Promise.resolve() : new Promise((resolve) => {
      (waiting[name] = waiting[name] || []).push(resolve);
    })),
  };
  const slot = { innerHTML: "", appended: [], appendChild(node) { this.appended.push(node); } };
  const noop = () => {};
  class HTMLElement {
    attachShadow() {
      let html = "";
      this.shadowRoot = {
        get innerHTML() { return html; },
        set innerHTML(value) { html = value; },
        querySelector: (selector) => (selector === ".trend" && html.includes('class="trend"') ? slot
          : { appendChild: noop, addEventListener: noop, dataset: {}, closest: () => null }),
        querySelectorAll: () => [],
        appendChild: noop,
      };
      return this.shadowRoot;
    }
  }
  const document = {
    createElement: (tag) => (defined[tag] ? new defined[tag]() : { tag, dataset: {}, style: {}, appendChild: noop,
      addEventListener: noop, setAttribute: noop, setConfig() { this.configured = arguments[0]; } }),
    body: { appendChild: noop },
  };
  const api = {};
  const window = {};
  const run = new Function("HTMLElement", "customElements", "document", "window", "console", "CustomEvent",
    `${SOURCE}\nreturn { findEntities, formatDuration, durationParts, unitLabel, hasExtra, OPTIONAL,
      PerdisAccountsCard, PerdisMasterCard, PerdisCalendarCard, texts, EMOJI, FACT_KEYS };`);
  Object.assign(api, run(HTMLElement, customElements, document, window, { info() {} }, class {}));
  return { ...api, defined, customElements, slot, document, window };
}

const state = (attributes, value = "1") => ({ attributes, last_updated: "1", state: value });
const hassWith = (extra = {}) => ({
  locale: { language: "de" }, config: { language: "de" }, entities: {},
  states: {
    "sensor.roster": state({ perdis_role: "roster", days: [], operator: "VGF", account: "VGF - 12345", online: true,
      portal: "WebComm", portal_url: "https://perdis.example.org/WebComm/" }),
    "sensor.hours": state({ perdis_role: "overtime_hours" }, "-10.28"),
    "sensor.overtime": state({ perdis_role: "overtime" }, "-10:17"),
    "button.refresh": state({ perdis_role: "refresh" }, "unknown"),
    ...extra,
  },
});

test("durations name each unit with the right singular and plural", () => {
  const { formatDuration, unitLabel } = world();
  const hass = { locale: { language: "de" }, config: { language: "de" } };
  assert.strictEqual(formatDuration(hass, 1), "1 Minute");
  assert.strictEqual(formatDuration(hass, 61), "1 Stunde 1 Minute");
  assert.strictEqual(formatDuration(hass, 2 * 1440 + 180), "2 Tage 3 Stunden");
  assert.strictEqual(formatDuration(hass, 255.8 * 60), "10 Tage 15 Stunden 48 Minuten");
  assert.strictEqual(formatDuration(hass, 2 * 1440, true), "2 Tagen");
  assert.strictEqual(unitLabel(hass, "day", 1), "Tag");
  assert.strictEqual(unitLabel(hass, "day", 12.5), "Tage");
});

test("the next-shift tiles come in the agreed order", () => {
  const { FACT_KEYS } = world();
  assert.deepStrictEqual(FACT_KEYS, ["wake_up", "leave_home", "duration", "breaks", "paid", "rest"]);
});

test("every extra is off by default and checked in the browser", () => {
  const w = world();
  assert.strictEqual(w.hasExtra("mini-graph-card"), false);
  w.customElements.define("mini-graph-card", class extends w.document.createElement("x").constructor {});
  assert.strictEqual(w.hasExtra("mini-graph-card"), true);
});

test("the accounts card draws no trend unless asked, and says what is missing when asked", () => {
  const w = world();
  const hass = hassWith();
  const plain = new w.PerdisAccountsCard();
  plain.setConfig({ type: "x" });
  plain.hass = hass;
  assert.ok(!plain.shadowRoot.innerHTML.includes('class="trend"'));

  const wanting = new w.PerdisAccountsCard();
  wanting.setConfig({ type: "x", show_trend: true });
  wanting.hass = hass;
  assert.ok(wanting.shadowRoot.innerHTML.includes('class="trend"'));
  assert.match(w.slot.innerHTML, /mini-graph-card/);
});

test("with the extra installed the trend graph is configured from the numeric sensor", () => {
  const w = world();
  w.customElements.define("mini-graph-card", class { setConfig(config) { this.config = config; } });
  const card = new w.PerdisAccountsCard();
  card.setConfig({ type: "x", show_trend: true, trend_days: 7 });
  card.hass = hassWith();
  const [graph] = w.slot.appended;
  assert.deepStrictEqual(graph.config.entities, ["sensor.hours"]);
  assert.strictEqual(graph.config.hours_to_show, 7 * 24);
});

test("the all-in-one header says PERDIS WebComm and offers refresh and open", () => {
  const w = world();
  const card = new w.PerdisMasterCard();
  card.setConfig({ type: "x" });
  card.hass = hassWith();
  const html = card.shadowRoot.innerHTML;
  assert.match(html, /PERDIS WebComm/);
  assert.match(html, /class="action open"/);
  assert.match(html, /mdi:open-in-app/);
  assert.match(html, /class="action refresh/);
  assert.match(html, />12345</);  // the personnel number, the operator is the badge
});

test("the open button can be switched off", () => {
  const w = world();
  const card = new w.PerdisMasterCard();
  card.setConfig({ type: "x", show_open: false });
  card.hass = hassWith();
  assert.doesNotMatch(card.shadowRoot.innerHTML, /action open/);
});
