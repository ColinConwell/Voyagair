function createVoyageResults(container) {
  container.innerHTML = `
    <div class="results-panel">
      <div class="results-hdr">
        <h2>Results</h2>
        <span class="results-count" id="vr-count"></span>
      </div>
      <div id="vr-status" class="results-status"></div>
      <div class="results-export" id="vr-export" style="display:none">
        <button class="btn btn-sm" data-fmt="html">Export HTML</button>
        <button class="btn btn-sm" data-fmt="md">Export Markdown</button>
        <button class="btn btn-sm" data-fmt="pdf">Export PDF</button>
      </div>
      <div style="overflow-x:auto">
        <table class="results-table">
          <thead><tr><th>Route</th><th>Date</th><th>Carrier</th><th>Stops</th><th>Duration</th><th>Price</th><th>Source</th></tr></thead>
          <tbody id="vr-body"></tbody>
        </table>
      </div>
    </div>
  `;

  const tbody = document.getElementById("vr-body");
  const countEl = document.getElementById("vr-count");
  const statusEl = document.getElementById("vr-status");
  const exportEl = document.getElementById("vr-export");

  let _lastConfig = null;
  let _lastResults = null;

  exportEl.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-fmt]");
    if (!btn || !_lastConfig) return;
    const fmt = btn.dataset.fmt;
    btn.textContent = "Exporting...";
    btn.disabled = true;
    try {
      const resp = await fetch("/api/voyage/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: _lastConfig, results: _lastResults, format: fmt }),
      });
      if (!resp.ok) throw new Error(resp.statusText);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      if (fmt === "html") {
        window.open(url, "_blank");
      } else {
        const a = document.createElement("a");
        a.href = url;
        a.download = "voyage-report." + (fmt === "md" ? "md" : fmt);
        a.click();
      }
    } catch (err) {
      statusEl.textContent = "Export failed: " + err.message;
    }
    btn.textContent = "Export " + fmt.toUpperCase();
    btn.disabled = false;
  });

  function fmt(min) {
    const h = Math.floor(min / 60), m = min % 60;
    return h > 0 ? h + "h " + m + "m" : m + "m";
  }

  function addRow(offer) {
    const legs = offer.legs || [];
    const orig = legs.length ? legs[0].origin : "?";
    const dest = legs.length ? legs[legs.length - 1].destination : "?";
    const dep = legs.length ? legs[0].departure : "";
    const carriers = [...new Set(legs.map(l => l.carrier).filter(Boolean))].join(", ");
    const stops = Math.max(0, legs.length - 1);
    let dur = 0;
    legs.forEach(l => dur += l.duration_minutes || 0);
    const depStr = dep ? new Date(dep).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "N/A";
    const stopsClass = stops === 0 ? "stops-0" : stops === 1 ? "stops-1" : "stops-2";
    const stopsLabel = stops === 0 ? "Nonstop" : stops + " stop" + (stops > 1 ? "s" : "");

    const tr = document.createElement("tr");
    tr.innerHTML = `<td class="route">${orig} &rarr; ${dest}</td><td>${depStr}</td><td>${carriers||"N/A"}</td><td class="${stopsClass}">${stopsLabel}</td><td class="duration">${fmt(dur)}</td><td class="price">${offer.currency} ${offer.price.toLocaleString()}</td><td class="source">${offer.provider}</td>`;
    if (offer.deep_link) { tr.style.cursor = "pointer"; tr.onclick = () => window.open(offer.deep_link, "_blank"); }
    tbody.appendChild(tr);
  }

  return {
    showLoading() { statusEl.textContent = "Searching..."; statusEl.className = "results-status loading"; tbody.innerHTML = ""; countEl.textContent = ""; exportEl.style.display = "none"; },
    showResults(results, config) {
      _lastResults = results;
      _lastConfig = config || _lastConfig;
      tbody.innerHTML = "";
      (results.flight_options || []).forEach(addRow);
      countEl.textContent = (results.flight_options || []).length + " flights";
      statusEl.textContent = "Search complete.";
      statusEl.className = "results-status";
      if ((results.flight_options || []).length > 0) exportEl.style.display = "flex";
    },
    showError(msg) { statusEl.textContent = msg; statusEl.className = "results-status error"; },
    clear() { tbody.innerHTML = ""; countEl.textContent = ""; statusEl.textContent = ""; exportEl.style.display = "none"; },
    setConfig(config) { _lastConfig = config; },
  };
}
