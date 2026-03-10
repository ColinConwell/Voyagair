function createVoyageResults(container) {
  container.innerHTML = `
    <div class="results-panel">
      <div class="results-hdr">
        <h2>Results</h2>
        <span class="results-count" id="vr-count"></span>
      </div>
      <div id="vr-status" class="results-status"></div>
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
    showLoading() { statusEl.textContent = "Searching..."; statusEl.className = "results-status loading"; tbody.innerHTML = ""; countEl.textContent = ""; },
    showResults(results) {
      tbody.innerHTML = "";
      (results.flight_options || []).forEach(addRow);
      countEl.textContent = (results.flight_options || []).length + " flights";
      statusEl.textContent = "Search complete.";
      statusEl.className = "results-status";
    },
    showError(msg) { statusEl.textContent = msg; statusEl.className = "results-status error"; },
    clear() { tbody.innerHTML = ""; countEl.textContent = ""; statusEl.textContent = ""; },
  };
}
