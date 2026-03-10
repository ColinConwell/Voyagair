function createVoyageConfig(container, onSearch, onSave) {
  container.innerHTML = `
    <div class="config-panel">
      <input type="text" class="voyage-name" value="Untitled Voyage" placeholder="Voyage name" />

      <div class="section">
        <div class="section-title">Starting Points</div>
        <div id="va-start"></div>
      </div>

      <div class="section">
        <div class="section-title">End Points</div>
        <div id="va-end"></div>
      </div>

      <div class="section">
        <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">Sites Along the Way</div>
        <div class="section-body collapsed">
          <div id="va-sites"></div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Travel Details</div>
        <div class="field-row">
          <div class="field"><label>Departure</label><input type="date" id="va-dep" /></div>
          <div class="field"><label>Return</label><input type="date" id="va-ret" /></div>
          <div class="field field-sm"><label>Passengers</label><input type="number" id="va-adults" value="1" min="1" max="9" /></div>
          <div class="field field-sm"><label>Cabin</label>
            <select id="va-cabin"><option value="economy">Economy</option><option value="premium_economy">Premium Economy</option><option value="business">Business</option><option value="first">First</option></select>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">Time Budget</div>
        <div class="section-body collapsed">
          <div class="field-row">
            <div class="field"><label>Total Days</label><input type="number" id="va-days" value="14" min="1" /></div>
            <div class="field"><label>Max Journey (hrs)</label><input type="number" id="va-maxj" placeholder="No limit" /></div>
            <div class="field"><label>Max Multi-Ticket (hrs)</label><input type="number" id="va-maxm" placeholder="No limit" /></div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">Cost Budget</div>
        <div class="section-body collapsed">
          <div class="field-row">
            <div class="field"><label>Max Total</label><input type="number" id="va-cmax" placeholder="No limit" /></div>
            <div class="field"><label>Max Per Leg</label><input type="number" id="va-cleg" placeholder="No limit" /></div>
            <div class="field field-sm"><label>Currency</label>
              <select id="va-curr"><option>USD</option><option>EUR</option><option>GBP</option><option>ZAR</option><option>JPY</option></select>
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">Travel Agent</div>
        <div class="section-body collapsed">
          <div class="field-row"><label class="check-label"><input type="checkbox" id="va-agent" /><span>Enable Travel Agent</span></label></div>
          <div class="field-row"><label class="check-label"><input type="checkbox" id="va-builtin" checked /><span>Use built-in tools</span></label></div>
          <div class="field-row"><div class="field" style="flex:1"><label>Custom Instructions</label><textarea id="va-instr" rows="2" placeholder="Optional..."></textarea></div></div>
        </div>
      </div>

      <div class="section">
        <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">Save / Auto-Refresh</div>
        <div class="section-body collapsed">
          <div class="field-row"><label class="check-label"><input type="checkbox" id="va-autosave" checked /><span>Auto-save</span></label></div>
          <div class="field-row">
            <label class="check-label"><input type="checkbox" id="va-autoref" /><span>Auto-refresh</span></label>
            <div class="field field-sm"><label>Interval (min)</label><input type="number" id="va-refint" value="60" min="5" /></div>
          </div>
          <div class="field-row">
            <label class="check-label"><input type="checkbox" id="va-nemail" /><span>Email</span></label>
            <label class="check-label"><input type="checkbox" id="va-nsms" /><span>SMS</span></label>
            <label class="check-label"><input type="checkbox" id="va-nweb" checked /><span>Web App</span></label>
          </div>
          <div class="field-row"><div class="field"><label>Notification Target</label><input type="text" id="va-ntarget" placeholder="email@example.com" /></div></div>
        </div>
      </div>

      <div class="config-actions">
        <button class="btn btn-primary" id="va-search">Search Voyage</button>
        <button class="btn btn-secondary" id="va-save">Save</button>
      </div>
    </div>
  `;

  let startPts = [], endPts = [], sitesPts = [];

  const startInput = createLocationInput(document.getElementById("va-start"), "From", "Search...", s => startPts = s);
  const endInput = createLocationInput(document.getElementById("va-end"), "To", "Search...", s => endPts = s);
  const sitesInput = createLocationInput(document.getElementById("va-sites"), "Waypoints", "Add cities, airports...", s => sitesPts = s);

  function build() {
    const g = id => document.getElementById(id);
    const notifications = [];
    if (g("va-nemail").checked) notifications.push({ type: "email", target: g("va-ntarget").value, enabled: true });
    if (g("va-nsms").checked) notifications.push({ type: "sms", target: g("va-ntarget").value, enabled: true });
    if (g("va-nweb").checked) notifications.push({ type: "webapp", target: "", enabled: true });

    return {
      name: container.querySelector(".voyage-name").value || "Untitled Voyage",
      starting_points: startPts,
      end_points: endPts,
      sites_along_the_way: sitesPts,
      departure_date: g("va-dep").value || null,
      return_date: g("va-ret").value || null,
      adults: parseInt(g("va-adults").value) || 1,
      cabin_class: g("va-cabin").value,
      time_budget: {
        total_days: parseInt(g("va-days").value) || 14,
        max_journey_hours: parseFloat(g("va-maxj").value) || null,
        max_multi_ticket_hours: parseFloat(g("va-maxm").value) || null,
      },
      cost_budget: {
        max_total: parseFloat(g("va-cmax").value) || null,
        max_per_leg: parseFloat(g("va-cleg").value) || null,
        max_single_ticket: null,
        max_multi_ticket_total: null,
        currency: g("va-curr").value,
      },
      travel_agent: {
        enabled: g("va-agent").checked,
        use_builtin_tools: g("va-builtin").checked,
        mcp_servers: [],
        custom_instructions: g("va-instr").value || null,
        model: null,
        provider: null,
      },
      save_refresh: {
        auto_save: g("va-autosave").checked,
        save_path: null,
        notifications: notifications,
        auto_refresh_interval_minutes: g("va-autoref").checked ? parseInt(g("va-refint").value) : null,
        auto_refresh_enabled: g("va-autoref").checked,
      },
      optimize_for: "price",
    };
  }

  document.getElementById("va-search").onclick = () => onSearch(build());
  document.getElementById("va-save").onclick = () => onSave(build());

  return {
    build,
    load(config) {
      container.querySelector(".voyage-name").value = config.name;
      if (config.departure_date) document.getElementById("va-dep").value = config.departure_date;
      if (config.return_date) document.getElementById("va-ret").value = config.return_date;
      document.getElementById("va-adults").value = config.adults;
      document.getElementById("va-cabin").value = config.cabin_class;
      startInput.setSelected(config.starting_points || []);
      endInput.setSelected(config.end_points || []);
      sitesInput.setSelected(config.sites_along_the_way || []);
      startPts = config.starting_points || [];
      endPts = config.end_points || [];
      sitesPts = config.sites_along_the_way || [];
    },
  };
}
