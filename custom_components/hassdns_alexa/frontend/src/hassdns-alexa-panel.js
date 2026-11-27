/* HassDNS Alexa panel — visual entity exposure manager. */
import { LitElement, html, css } from "lit";

const WS = "hassdns_alexa";

const DOMAIN_ICONS = {
  light: "mdi:lightbulb", switch: "mdi:toggle-switch", fan: "mdi:fan",
  cover: "mdi:blinds", climate: "mdi:thermostat", lock: "mdi:lock",
  media_player: "mdi:cast", scene: "mdi:palette", script: "mdi:script-text",
  vacuum: "mdi:robot-vacuum", camera: "mdi:cctv", humidifier: "mdi:air-humidifier",
  water_heater: "mdi:water-boiler", sensor: "mdi:eye", binary_sensor: "mdi:eye-check",
  automation: "mdi:robot", group: "mdi:home-group", input_boolean: "mdi:toggle-switch-variant",
  input_button: "mdi:gesture-tap-button", button: "mdi:gesture-tap-button", alert: "mdi:alert",
};

const DOMAIN_LABELS = {
  light: "Lights", switch: "Switches", climate: "Climate", cover: "Covers",
  lock: "Locks", fan: "Fans", media_player: "Media players", scene: "Scenes",
  script: "Scripts", automation: "Automations", vacuum: "Vacuums",
  camera: "Cameras", humidifier: "Humidifiers", water_heater: "Water heaters",
  sensor: "Sensors", binary_sensor: "Binary sensors", input_boolean: "Helpers",
  button: "Buttons", input_button: "Buttons", group: "Groups", alert: "Alerts",
};

const DOMAIN_ORDER = ["light", "switch", "climate", "cover", "lock", "fan",
  "media_player", "scene", "script", "automation", "vacuum", "humidifier",
  "water_heater", "camera", "sensor", "binary_sensor", "input_boolean",
  "button", "input_button", "group", "alert"];

class HassdnsAlexaPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    _entities: { state: true },
    _link: { state: true },
    _q: { state: true },
    _showHelp: { state: true },
    _busy: { state: true },
  };

  constructor() {
    super();
    this._entities = [];
    this._link = null;
    this._q = "";
    this._showHelp = false;
  }

  connectedCallback() {
    super.connectedCallback();
    this._load();
  }

  async _load() {
    const [ents, link] = await Promise.all([
      this.hass.callWS({ type: `${WS}/entities` }),
      this.hass.callWS({ type: `${WS}/link` }),
    ]);
    this._entities = ents.entities;
    this._link = link;
  }

  async _toggle(e) {
    const entity_id = e.currentTarget.dataset.eid;
    const ent = this._entities.find((x) => x.entity_id === entity_id);
    if (!ent) return;
    const expose = !ent.exposed;
    try {
      await this.hass.callWS({ type: `${WS}/set_expose`, entity_id, expose });
      ent.exposed = expose;
      this.requestUpdate();
    } catch (err) {
      this._toast(err.message || err.code || "Error");
    }
  }

  async _genToken() {
    this._busy = true;
    try {
      const res = await this.hass.callWS({ type: `${WS}/generate_token` });
      const token = res.token ?? res;
      this._link = { ...this._link, link_token: token };
      this._toast("Link token created");
    } catch (err) {
      this._toast(err.message || err.code || "Token error");
    }
    this._busy = false;
  }

  _copy(e) {
    const text = e.currentTarget.dataset.text;
    navigator.clipboard.writeText(text);
    this._toast(this.hass.localize("ui.common.copied") || "Copied");
  }

  _toast(text) {
    const el = this.shadowRoot.querySelector(".toast");
    el.textContent = text;
    el.classList.add("show");
    clearTimeout(this._tt);
    this._tt = setTimeout(() => el.classList.remove("show"), 2200);
  }

  get _filtered() {
    const q = this._q.toLowerCase();
    const list = q
      ? this._entities.filter(
          (e) => e.name.toLowerCase().includes(q) || e.entity_id.includes(q)
        )
      : this._entities;
    const groups = new Map();
    for (const e of list) {
      const g = e.domain;
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(e);
    }
    return new Map(
      [...groups.entries()].sort(
        (a, b) =>
          (DOMAIN_ORDER.indexOf(a[0]) + 1 || 99) -
          (DOMAIN_ORDER.indexOf(b[0]) + 1 || 99)
      )
    );
  }

  render() {
    const exposed = this._entities.filter((e) => e.exposed).length;
    return html`
      <div class="page">
        <header>
          <img class="brand-logo" src="/api/hassdns_alexa/static/logo.png" alt="HassDNS" />
          <div class="h-text">
            <h1>HassDNS Alexa</h1>
            <p class="sub">${exposed} / ${this._entities.length} entities exposed</p>
          </div>
          <ha-textfield
            class="search" icon="mdi:magnify" .value=${this._q}
            placeholder="Search entities"
            @input=${(e) => (this._q = e.target.value)}
          ></ha-textfield>
          <ha-icon-button class="help" label="Link help" path="mdi:link-variant"
            @click=${() => (this._showHelp = !this._showHelp)}></ha-icon-button>
        </header>

        ${this._showHelp && this._link
          ? html`<div class="linkbox card">
              <h2>Link this Home Assistant with Alexa</h2>
              <ol>
                <li>In the Alexa app, enable the <b>HassDNS Alexa</b> skill and sign in.</li>
                <li>On the <a href="${this._link.cloud_url}" target="_blank">${this._link.cloud_url}</a>
                    linking page, paste:</li>
              </ol>
              <div class="row">
                <span class="lbl">URL</span>
                <code>${this._link.ha_url}</code>
                <ha-icon-button label="Copy" path="mdi:content-copy"
                  data-text=${this._link.ha_url} @click=${this._copy}></ha-icon-button>
              </div>
              ${this._link.link_token
                ? html`<div class="row">
                    <span class="lbl">Token</span>
                    <code class="tok">${this._link.link_token}</code>
                    <ha-icon-button label="Copy" path="mdi:content-copy"
                      data-text=${this._link.link_token} @click=${this._copy}></ha-icon-button>
                  </div>`
                : html`<button class="gen" ?disabled=${this._busy}
                    @click=${this._genToken}>${this._busy ? "Generating…" : "Generate link token"}</button>`}
            </div>`
          : ""}

        ${[...this._filtered.entries()].map(
          ([domain, ents]) => html`
            <section>
              <h3>${DOMAIN_LABELS[domain] || domain} <span>${ents.length}</span></h3>
              <div class="grid">
                ${ents.map(
                  (e) => html`
                    <button class="ent ${e.exposed ? "on" : ""}" data-eid=${e.entity_id}
                      @click=${this._toggle}>
                      <ha-icon icon=${e.icon || DOMAIN_ICONS[e.domain] || "mdi:eye"}></ha-icon>
                      <span class="n">${e.name}</span>
                      <span class="d">${e.entity_id}</span>
                      <span class="sw ${e.exposed ? "on" : ""}"></span>
                    </button>`
                )}
              </div>
            </section>`
        )}
        <div class="toast"></div>
      </div>
    `;
  }

  static styles = css`
    :host { display: block; height: 100%; overflow-y: auto;
      background: var(--primary-background-color); color: var(--primary-text-color); }
    .page { max-width: 1100px; margin: 0 auto; padding: 16px 20px 80px; }
    header { display: flex; align-items: center; gap: 14px; padding: 6px 0 18px; flex-wrap: wrap; }
    header > ha-icon { --mdc-icon-size: 34px; color: var(--primary-color); }
    .brand-logo { width: 40px; height: 40px; border-radius: 9px; flex: none; }
    h1 { font-size: 1.4rem; margin: 0; }
    .sub { margin: 0; font-size: .85rem; color: var(--secondary-text-color); }
    .search { flex: 1; min-width: 200px; }
    .card { background: var(--card-background-color); border-radius: 12px;
      padding: 16px 18px; margin-bottom: 18px; box-shadow: var(--ha-card-box-shadow, none); }
    .linkbox h2 { margin: 0 0 8px; font-size: 1.05rem; }
    .linkbox ol { margin: 0 0 10px; padding-left: 20px; font-size: .9rem; }
    .linkbox .row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
    .linkbox .lbl { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em;
      color: var(--secondary-text-color); width: 48px; }
    .linkbox code { flex: 1; overflow-x: auto; white-space: nowrap; font-size: .82rem;
      background: var(--secondary-background-color); padding: 8px 10px; border-radius: 8px; }
    section h3 { font-size: .8rem; text-transform: uppercase; letter-spacing: .08em;
      color: var(--secondary-text-color); margin: 18px 4px 8px; font-weight: 600; }
    section h3 span { opacity: .6; font-weight: 400; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 8px; }
    .ent { position: relative; text-align: left; border: 1px solid var(--divider-color);
      background: var(--card-background-color); border-radius: 12px; padding: 12px 12px 12px 40px;
      cursor: pointer; color: inherit; font: inherit; display: block; width: 100%;
      transition: border-color .15s, box-shadow .15s; }
    .ent:hover { border-color: var(--primary-color); }
    .ent:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }
    .ent.on { border-color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 8%, var(--card-background-color)); }
    .ent > ha-icon { position: absolute; left: 12px; top: 14px; color: var(--secondary-text-color); }
    .ent.on > ha-icon { color: var(--primary-color); }
    .ent .n { display: block; font-size: .9rem; font-weight: 500; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap; padding-right: 30px; }
    .ent .d { display: block; font-size: .72rem; color: var(--secondary-text-color);
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sw { position: absolute; right: 10px; top: 10px; width: 28px; height: 16px; border-radius: 8px;
      background: var(--divider-color); transition: background .15s; }
    .sw::after { content: ""; position: absolute; top: 2px; left: 2px; width: 12px; height: 12px;
      border-radius: 50%; background: var(--card-background-color); transition: transform .15s; }
    .sw.on { background: var(--primary-color); }
    .sw.on::after { transform: translateX(12px); }
    .gen { background: var(--primary-color); color: var(--text-primary-color, #fff);
      border: 0; border-radius: 8px; padding: 10px 18px; font: inherit; font-weight: 500;
      cursor: pointer; margin-top: 6px; }
    .gen:disabled { opacity: .6; cursor: default; }
    .toast { position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%);
      background: var(--card-background-color); color: var(--primary-text-color);
      border: 1px solid var(--divider-color); border-radius: 10px; padding: 8px 16px;
      font-size: .85rem; opacity: 0; pointer-events: none; transition: opacity .2s; }
    .toast.show { opacity: 1; }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  `;
}

customElements.define("hassdns-alexa-panel", HassdnsAlexaPanel);
