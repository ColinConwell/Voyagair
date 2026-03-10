import type { FlightOffer, VoyageResults } from "../api";

export function createVoyageResultsPanel(container: HTMLElement) {
  container.innerHTML = `
    <div class="voyage-results">
      <div class="results-header">
        <h2>Results</h2>
        <span class="results-count" id="vr-count"></span>
        <span class="results-duration" id="vr-duration"></span>
      </div>
      <div id="vr-status" class="results-status"></div>
      <div class="results-table-container">
        <table class="results-table">
          <thead>
            <tr>
              <th>Route</th>
              <th>Date</th>
              <th>Carrier</th>
              <th>Stops</th>
              <th>Duration</th>
              <th>Price</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody id="vr-body"></tbody>
        </table>
      </div>
    </div>
  `;

  const tbody = container.querySelector("#vr-body") as HTMLTableSectionElement;
  const countEl = container.querySelector("#vr-count") as HTMLSpanElement;
  const durationEl = container.querySelector("#vr-duration") as HTMLSpanElement;
  const statusEl = container.querySelector("#vr-status") as HTMLDivElement;

  function formatDuration(minutes: number): string {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  function addRow(offer: FlightOffer) {
    const legs = offer.legs;
    const origin = legs.length > 0 ? legs[0].origin : "???";
    const dest = legs.length > 0 ? legs[legs.length - 1].destination : "???";
    const dep = legs.length > 0 ? legs[0].departure : "";
    const carriers = [...new Set(legs.map((l) => l.carrier).filter(Boolean))].join(", ");
    const numStops = Math.max(0, legs.length - 1);

    let totalMin = 0;
    for (const leg of legs) totalMin += leg.duration_minutes || 0;
    if (totalMin === 0 && legs.length >= 2) {
      const d0 = new Date(legs[0].departure).getTime();
      const d1 = new Date(legs[legs.length - 1].arrival).getTime();
      totalMin = Math.round((d1 - d0) / 60000);
    }

    const depStr = dep
      ? new Date(dep).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
      : "N/A";

    const tr = document.createElement("tr");
    const stopsClass = numStops === 0 ? "stops-0" : numStops === 1 ? "stops-1" : "stops-2";
    const stopsLabel = numStops === 0 ? "Nonstop" : `${numStops} stop${numStops > 1 ? "s" : ""}`;

    tr.innerHTML = `
      <td class="route">${origin} &rarr; ${dest}</td>
      <td>${depStr}</td>
      <td>${carriers || "N/A"}</td>
      <td class="${stopsClass}">${stopsLabel}</td>
      <td class="duration">${formatDuration(totalMin)}</td>
      <td class="price">${offer.currency} ${offer.price.toLocaleString()}</td>
      <td class="source">${offer.provider}</td>
    `;

    if (offer.deep_link) {
      tr.style.cursor = "pointer";
      tr.title = "Open booking link";
      tr.addEventListener("click", () => window.open(offer.deep_link, "_blank"));
    }

    tbody.appendChild(tr);
  }

  return {
    showLoading: () => {
      statusEl.textContent = "Searching...";
      statusEl.className = "results-status loading";
      tbody.innerHTML = "";
      countEl.textContent = "";
      durationEl.textContent = "";
    },
    showResults: (results: VoyageResults) => {
      tbody.innerHTML = "";
      for (const offer of results.flight_options) {
        addRow(offer);
      }
      countEl.textContent = `${results.flight_options.length} flights`;
      if (results.transport_options.length > 0) {
        countEl.textContent += ` + ${results.transport_options.length} transport`;
      }
      durationEl.textContent = `(${results.search_duration_seconds.toFixed(1)}s)`;
      statusEl.textContent = "Search complete.";
      statusEl.className = "results-status";
    },
    showError: (msg: string) => {
      statusEl.textContent = msg;
      statusEl.className = "results-status error";
    },
    clear: () => {
      tbody.innerHTML = "";
      countEl.textContent = "";
      durationEl.textContent = "";
      statusEl.textContent = "";
      statusEl.className = "results-status";
    },
  };
}
