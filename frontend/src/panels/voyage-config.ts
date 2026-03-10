import { createLocationInput } from "../components/location-input";
import type { VoyageConfig, LocationSpec } from "../api";

interface VoyageConfigPanelOptions {
  container: HTMLElement;
  onSearch: (config: VoyageConfig) => void;
  onSave: (config: VoyageConfig) => void;
}

export function createVoyageConfigPanel(opts: VoyageConfigPanelOptions) {
  const { container, onSearch, onSave } = opts;

  container.innerHTML = `
    <div class="voyage-config">
      <div class="config-header">
        <input type="text" class="voyage-name-input" value="Untitled Voyage" placeholder="Voyage name" />
      </div>

      <div class="config-sections">
        <fieldset class="config-section">
          <legend>Starting Points</legend>
          <div id="vc-starting-points" class="location-field"></div>
        </fieldset>

        <fieldset class="config-section">
          <legend>End Points</legend>
          <div id="vc-end-points" class="location-field"></div>
        </fieldset>

        <fieldset class="config-section collapsible">
          <legend><button class="toggle-btn" data-target="vc-sites">Sites Along the Way</button></legend>
          <div id="vc-sites" class="section-body collapsed">
            <div id="vc-sites-input" class="location-field"></div>
          </div>
        </fieldset>

        <fieldset class="config-section">
          <legend>Travel Details</legend>
          <div class="config-row">
            <div class="config-field">
              <label for="vc-departure">Departure Date</label>
              <input type="date" id="vc-departure" />
            </div>
            <div class="config-field">
              <label for="vc-return">Return Date</label>
              <input type="date" id="vc-return" />
            </div>
            <div class="config-field config-field-sm">
              <label for="vc-adults">Passengers</label>
              <input type="number" id="vc-adults" value="1" min="1" max="9" />
            </div>
            <div class="config-field config-field-sm">
              <label for="vc-cabin">Cabin</label>
              <select id="vc-cabin">
                <option value="economy">Economy</option>
                <option value="premium_economy">Premium Economy</option>
                <option value="business">Business</option>
                <option value="first">First</option>
              </select>
            </div>
          </div>
        </fieldset>

        <fieldset class="config-section collapsible">
          <legend><button class="toggle-btn" data-target="vc-time">Time Budget</button></legend>
          <div id="vc-time" class="section-body collapsed">
            <div class="config-row">
              <div class="config-field">
                <label for="vc-total-days">Total Days</label>
                <input type="number" id="vc-total-days" value="14" min="1" />
              </div>
              <div class="config-field">
                <label for="vc-max-journey">Max Journey (hours)</label>
                <input type="number" id="vc-max-journey" placeholder="No limit" />
              </div>
              <div class="config-field">
                <label for="vc-max-multi">Max Multi-Ticket (hours)</label>
                <input type="number" id="vc-max-multi" placeholder="No limit" />
              </div>
            </div>
          </div>
        </fieldset>

        <fieldset class="config-section collapsible">
          <legend><button class="toggle-btn" data-target="vc-cost">Cost Budget</button></legend>
          <div id="vc-cost" class="section-body collapsed">
            <div class="config-row">
              <div class="config-field">
                <label for="vc-max-total">Max Total</label>
                <input type="number" id="vc-max-total" placeholder="No limit" />
              </div>
              <div class="config-field">
                <label for="vc-max-leg">Max Per Leg</label>
                <input type="number" id="vc-max-leg" placeholder="No limit" />
              </div>
              <div class="config-field config-field-sm">
                <label for="vc-currency">Currency</label>
                <select id="vc-currency">
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                  <option value="ZAR">ZAR</option>
                  <option value="JPY">JPY</option>
                </select>
              </div>
            </div>
          </div>
        </fieldset>

        <fieldset class="config-section collapsible">
          <legend><button class="toggle-btn" data-target="vc-agent">Travel Agent</button></legend>
          <div id="vc-agent" class="section-body collapsed">
            <div class="config-row">
              <label class="toggle-label">
                <input type="checkbox" id="vc-agent-enabled" />
                <span>Enable Travel Agent (AI-assisted search)</span>
              </label>
            </div>
            <div class="config-row">
              <label class="toggle-label">
                <input type="checkbox" id="vc-agent-builtin" checked />
                <span>Use built-in tools</span>
              </label>
            </div>
            <div class="config-row">
              <div class="config-field" style="flex:1">
                <label for="vc-agent-instructions">Custom Instructions</label>
                <textarea id="vc-agent-instructions" rows="2" placeholder="Optional instructions for the agent..."></textarea>
              </div>
            </div>
          </div>
        </fieldset>

        <fieldset class="config-section collapsible">
          <legend><button class="toggle-btn" data-target="vc-save">Save / Auto-Refresh</button></legend>
          <div id="vc-save" class="section-body collapsed">
            <div class="config-row">
              <label class="toggle-label">
                <input type="checkbox" id="vc-auto-save" checked />
                <span>Auto-save voyage</span>
              </label>
            </div>
            <div class="config-row">
              <label class="toggle-label">
                <input type="checkbox" id="vc-auto-refresh" />
                <span>Auto-refresh results</span>
              </label>
              <div class="config-field config-field-sm">
                <label for="vc-refresh-interval">Interval (min)</label>
                <input type="number" id="vc-refresh-interval" value="60" min="5" />
              </div>
            </div>
            <div class="config-row">
              <div class="config-field">
                <label>Notifications</label>
                <div class="notification-options">
                  <label class="toggle-label"><input type="checkbox" id="vc-notify-email" /><span>Email</span></label>
                  <label class="toggle-label"><input type="checkbox" id="vc-notify-sms" /><span>SMS</span></label>
                  <label class="toggle-label"><input type="checkbox" id="vc-notify-webapp" checked /><span>Web App</span></label>
                </div>
              </div>
              <div class="config-field">
                <label for="vc-notify-target">Notification Target</label>
                <input type="text" id="vc-notify-target" placeholder="email@example.com or +1234567890" />
              </div>
            </div>
          </div>
        </fieldset>
      </div>

      <div class="config-actions">
        <button class="btn btn-primary" id="vc-search-btn">Search Voyage</button>
        <button class="btn btn-secondary" id="vc-save-btn">Save</button>
      </div>
    </div>
  `;

  container.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = (btn as HTMLElement).dataset.target;
      if (!targetId) return;
      const target = container.querySelector(`#${targetId}`);
      target?.classList.toggle("collapsed");
    });
  });

  let startingPoints: LocationSpec[] = [];
  let endPoints: LocationSpec[] = [];
  let sitesAlongTheWay: LocationSpec[] = [];

  const startInput = createLocationInput({
    container: container.querySelector("#vc-starting-points")!,
    label: "From",
    placeholder: "Search airports, cities, countries, regions...",
    onChange: (specs) => { startingPoints = specs; },
  });

  const endInput = createLocationInput({
    container: container.querySelector("#vc-end-points")!,
    label: "To",
    placeholder: "Search airports, cities, countries, regions...",
    onChange: (specs) => { endPoints = specs; },
  });

  const sitesInput = createLocationInput({
    container: container.querySelector("#vc-sites-input")!,
    label: "Waypoints & Destinations",
    placeholder: "Add cities, airports, or tourist destinations...",
    onChange: (specs) => { sitesAlongTheWay = specs; },
  });

  function buildConfig(): VoyageConfig {
    const name = (container.querySelector(".voyage-name-input") as HTMLInputElement).value || "Untitled Voyage";
    const departure = (container.querySelector("#vc-departure") as HTMLInputElement).value || null;
    const returnDate = (container.querySelector("#vc-return") as HTMLInputElement).value || null;
    const adults = parseInt((container.querySelector("#vc-adults") as HTMLInputElement).value) || 1;
    const cabin = (container.querySelector("#vc-cabin") as HTMLSelectElement).value;

    const totalDays = parseInt((container.querySelector("#vc-total-days") as HTMLInputElement).value) || 14;
    const maxJourney = parseFloat((container.querySelector("#vc-max-journey") as HTMLInputElement).value) || null;
    const maxMulti = parseFloat((container.querySelector("#vc-max-multi") as HTMLInputElement).value) || null;

    const maxTotal = parseFloat((container.querySelector("#vc-max-total") as HTMLInputElement).value) || null;
    const maxLeg = parseFloat((container.querySelector("#vc-max-leg") as HTMLInputElement).value) || null;
    const currency = (container.querySelector("#vc-currency") as HTMLSelectElement).value;

    const agentEnabled = (container.querySelector("#vc-agent-enabled") as HTMLInputElement).checked;
    const agentBuiltin = (container.querySelector("#vc-agent-builtin") as HTMLInputElement).checked;
    const agentInstructions = (container.querySelector("#vc-agent-instructions") as HTMLTextAreaElement).value || null;

    const autoSave = (container.querySelector("#vc-auto-save") as HTMLInputElement).checked;
    const autoRefresh = (container.querySelector("#vc-auto-refresh") as HTMLInputElement).checked;
    const refreshInterval = parseInt((container.querySelector("#vc-refresh-interval") as HTMLInputElement).value) || 60;

    const notifications = [];
    if ((container.querySelector("#vc-notify-email") as HTMLInputElement).checked) {
      notifications.push({ type: "email" as const, target: (container.querySelector("#vc-notify-target") as HTMLInputElement).value, enabled: true });
    }
    if ((container.querySelector("#vc-notify-sms") as HTMLInputElement).checked) {
      notifications.push({ type: "sms" as const, target: (container.querySelector("#vc-notify-target") as HTMLInputElement).value, enabled: true });
    }
    if ((container.querySelector("#vc-notify-webapp") as HTMLInputElement).checked) {
      notifications.push({ type: "webapp" as const, target: "", enabled: true });
    }

    return {
      name,
      starting_points: startingPoints,
      end_points: endPoints,
      sites_along_the_way: sitesAlongTheWay,
      departure_date: departure,
      return_date: returnDate,
      adults,
      cabin_class: cabin,
      time_budget: { total_days: totalDays, max_journey_hours: maxJourney, max_multi_ticket_hours: maxMulti },
      cost_budget: { max_total: maxTotal, max_per_leg: maxLeg, max_single_ticket: null, max_multi_ticket_total: null, currency },
      travel_agent: { enabled: agentEnabled, use_builtin_tools: agentBuiltin, mcp_servers: [], custom_instructions: agentInstructions, model: null, provider: null },
      save_refresh: { auto_save: autoSave, save_path: null, notifications, auto_refresh_interval_minutes: autoRefresh ? refreshInterval : null, auto_refresh_enabled: autoRefresh },
      optimize_for: "price",
    };
  }

  container.querySelector("#vc-search-btn")!.addEventListener("click", () => {
    onSearch(buildConfig());
  });

  container.querySelector("#vc-save-btn")!.addEventListener("click", () => {
    onSave(buildConfig());
  });

  return {
    buildConfig,
    loadConfig: (config: VoyageConfig) => {
      (container.querySelector(".voyage-name-input") as HTMLInputElement).value = config.name;
      if (config.departure_date) (container.querySelector("#vc-departure") as HTMLInputElement).value = config.departure_date;
      if (config.return_date) (container.querySelector("#vc-return") as HTMLInputElement).value = config.return_date;
      (container.querySelector("#vc-adults") as HTMLInputElement).value = String(config.adults);
      (container.querySelector("#vc-cabin") as HTMLSelectElement).value = config.cabin_class;
      (container.querySelector("#vc-total-days") as HTMLInputElement).value = String(config.time_budget.total_days);
      if (config.time_budget.max_journey_hours) (container.querySelector("#vc-max-journey") as HTMLInputElement).value = String(config.time_budget.max_journey_hours);
      if (config.time_budget.max_multi_ticket_hours) (container.querySelector("#vc-max-multi") as HTMLInputElement).value = String(config.time_budget.max_multi_ticket_hours);
      if (config.cost_budget.max_total) (container.querySelector("#vc-max-total") as HTMLInputElement).value = String(config.cost_budget.max_total);
      if (config.cost_budget.max_per_leg) (container.querySelector("#vc-max-leg") as HTMLInputElement).value = String(config.cost_budget.max_per_leg);
      (container.querySelector("#vc-currency") as HTMLSelectElement).value = config.cost_budget.currency;
      (container.querySelector("#vc-agent-enabled") as HTMLInputElement).checked = config.travel_agent.enabled;
      (container.querySelector("#vc-agent-builtin") as HTMLInputElement).checked = config.travel_agent.use_builtin_tools;
      if (config.travel_agent.custom_instructions) (container.querySelector("#vc-agent-instructions") as HTMLTextAreaElement).value = config.travel_agent.custom_instructions;
      (container.querySelector("#vc-auto-save") as HTMLInputElement).checked = config.save_refresh.auto_save;
      (container.querySelector("#vc-auto-refresh") as HTMLInputElement).checked = config.save_refresh.auto_refresh_enabled;
      if (config.save_refresh.auto_refresh_interval_minutes) (container.querySelector("#vc-refresh-interval") as HTMLInputElement).value = String(config.save_refresh.auto_refresh_interval_minutes);

      startingPoints = config.starting_points;
      endPoints = config.end_points;
      sitesAlongTheWay = config.sites_along_the_way;
      startInput.setSelected(config.starting_points);
      endInput.setSelected(config.end_points);
      sitesInput.setSelected(config.sites_along_the_way);
    },
  };
}
