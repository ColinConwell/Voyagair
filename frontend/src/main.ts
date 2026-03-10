import {
  FlightOffer,
  SearchParams,
  VoyageConfig,
  getAirport,
  searchFlights,
  searchFlightsStream,
  searchVoyageInline,
  createVoyage,
  listVoyages,
  loadVoyage,
} from "./api";
import { createVoyageConfigPanel } from "./panels/voyage-config";
import { createVoyageResultsPanel } from "./panels/voyage-results";
import { createSummaryPanel } from "./panels/summary-panel";
import { createDebugPanel } from "./panels/debug-panel";

declare const L: typeof import("leaflet");

let map: ReturnType<typeof L.map>;
let routeLayer: ReturnType<typeof L.layerGroup>;

function initMap() {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;
  map = L.map("map").setView([0, 20], 2);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OpenStreetMap &copy; CARTO",
    maxZoom: 18,
  }).addTo(map);
  routeLayer = L.layerGroup().addTo(map);
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function computeOfferMeta(offer: FlightOffer) {
  const legs = offer.legs;
  const origin = legs.length > 0 ? legs[0].origin : "???";
  const destination = legs.length > 0 ? legs[legs.length - 1].destination : "???";
  const departure = legs.length > 0 ? legs[0].departure : "";
  const carriers = [...new Set(legs.map((l) => l.carrier).filter(Boolean))].join(", ");
  const numStops = Math.max(0, legs.length - 1);

  let totalMinutes = 0;
  for (const leg of legs) totalMinutes += leg.duration_minutes || 0;
  if (totalMinutes === 0 && legs.length >= 2) {
    const dep = new Date(legs[0].departure).getTime();
    const arr = new Date(legs[legs.length - 1].arrival).getTime();
    totalMinutes = Math.round((arr - dep) / 60000);
  }

  return { origin, destination, departure, carriers, numStops, totalMinutes };
}

function addResultRow(offer: FlightOffer, tbody: HTMLTableSectionElement) {
  const { origin, destination, departure, carriers, numStops, totalMinutes } = computeOfferMeta(offer);

  const depStr = departure
    ? new Date(departure).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : "N/A";

  const tr = document.createElement("tr");
  const stopsClass = numStops === 0 ? "stops-0" : numStops === 1 ? "stops-1" : "stops-2";
  const stopsLabel = numStops === 0 ? "Nonstop" : `${numStops} stop${numStops > 1 ? "s" : ""}`;

  tr.innerHTML = `
    <td class="route">${origin} &rarr; ${destination}</td>
    <td>${depStr}</td>
    <td>${carriers || "N/A"}</td>
    <td class="${stopsClass}">${stopsLabel}</td>
    <td class="duration">${formatDuration(totalMinutes)}</td>
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

async function drawRoute(offers: FlightOffer[]) {
  if (!routeLayer) return;
  routeLayer.clearLayers();
  const airportCache = new Map<string, { lat: number; lon: number }>();

  const codes = new Set<string>();
  for (const offer of offers.slice(0, 5)) {
    for (const leg of offer.legs) {
      codes.add(leg.origin);
      codes.add(leg.destination);
    }
  }

  for (const code of codes) {
    if (airportCache.has(code)) continue;
    const info = await getAirport(code);
    if (info && info.latitude && info.longitude) {
      airportCache.set(code, { lat: info.latitude, lon: info.longitude });
    }
  }

  const bounds: [number, number][] = [];

  for (const offer of offers.slice(0, 5)) {
    for (const leg of offer.legs) {
      const src = airportCache.get(leg.origin);
      const dst = airportCache.get(leg.destination);
      if (!src || !dst) continue;

      bounds.push([src.lat, src.lon], [dst.lat, dst.lon]);

      L.polyline(
        [[src.lat, src.lon], [dst.lat, dst.lon]],
        { color: "#58a6ff", weight: 2, opacity: 0.6, dashArray: "6 4" }
      ).addTo(routeLayer);
    }
  }

  for (const [code, pos] of airportCache) {
    L.circleMarker([pos.lat, pos.lon], {
      radius: 5, color: "#58a6ff", fillColor: "#58a6ff", fillOpacity: 0.8, weight: 1,
    })
      .bindTooltip(code, { permanent: true, direction: "top", className: "airport-tooltip" })
      .addTo(routeLayer);
  }

  if (bounds.length > 0) map.fitBounds(bounds, { padding: [40, 40] });
}

function buildSearchParams(): SearchParams {
  const origins = (document.getElementById("origins") as HTMLInputElement).value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  const destinations = (document.getElementById("destinations") as HTMLInputElement).value.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  const dateVal = (document.getElementById("dates") as HTMLInputElement).value;
  const adults = parseInt((document.getElementById("adults") as HTMLInputElement).value);
  const cabin = (document.getElementById("cabin") as HTMLSelectElement).value;
  const maxStopsVal = (document.getElementById("max-stops") as HTMLSelectElement).value;
  const sort = (document.getElementById("sort") as HTMLSelectElement).value;
  const maxPriceVal = (document.getElementById("max-price") as HTMLInputElement).value;

  return {
    origins,
    destinations,
    departure_dates: [dateVal],
    adults,
    cabin_class: cabin,
    max_stops: maxStopsVal ? parseInt(maxStopsVal) : undefined,
    sort_by: sort,
    max_price: maxPriceVal ? parseFloat(maxPriceVal) : undefined,
    limit: 50,
    currency: "USD",
  };
}

type AppView = "landing" | "search" | "voyage";

function showView(view: AppView) {
  document.querySelectorAll("[data-view]").forEach((el) => {
    (el as HTMLElement).style.display = (el as HTMLElement).dataset.view === view ? "" : "none";
  });
  if (view === "landing") {
    document.getElementById("summary-container")?.classList.remove("open");
  }
}

type VoyageLayout = "split" | "stacked";

function setVoyageLayout(layout: VoyageLayout) {
  const el = document.getElementById("voyage-layout");
  if (!el) return;
  el.dataset.layout = layout;
  localStorage.setItem("voyagair-layout", layout);
}

function initTheme() {
  const saved = localStorage.getItem("voyagair-theme");
  if (saved === "light" || saved === "dark") {
    document.documentElement.dataset.theme = saved;
  }
  updateMapTiles();
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  const next = current === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("voyagair-theme", next);
  updateMapTiles();
}

function updateMapTiles() {
  if (!map) return;
  const theme = document.documentElement.dataset.theme;
  const tileUrl = theme === "light"
    ? "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
  map.eachLayer((layer: unknown) => {
    if (layer && typeof layer === "object" && "_url" in (layer as Record<string, unknown>)) {
      map.removeLayer(layer as L.Layer);
    }
  });
  L.tileLayer(tileUrl, {
    attribution: "&copy; OpenStreetMap &copy; CARTO",
    maxZoom: 18,
  }).addTo(map);
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initMap();
  showView("landing");

  const savedLayout = (localStorage.getItem("voyagair-layout") || "split") as VoyageLayout;
  setVoyageLayout(savedLayout);

  const voyageConfigContainer = document.getElementById("voyage-config-container");
  const voyageResultsContainer = document.getElementById("voyage-results-container");
  const summaryContainer = document.getElementById("summary-container");
  const debugContainer = document.getElementById("debug-panel");
  const savedVoyagesList = document.getElementById("saved-voyages-list");

  let voyageResultsPanel: ReturnType<typeof createVoyageResultsPanel> | null = null;
  let summaryPanel: ReturnType<typeof createSummaryPanel> | null = null;
  let debugPanel: ReturnType<typeof createDebugPanel> | null = null;

  if (summaryContainer) {
    summaryPanel = createSummaryPanel(summaryContainer);
  }

  if (debugContainer) {
    debugPanel = createDebugPanel(debugContainer);
  }

  document.getElementById("btn-theme-toggle")?.addEventListener("click", toggleTheme);

  document.getElementById("btn-layout-toggle")?.addEventListener("click", () => {
    const current = (localStorage.getItem("voyagair-layout") || "split") as VoyageLayout;
    setVoyageLayout(current === "split" ? "stacked" : "split");
  });

  document.getElementById("btn-debug-toggle")?.addEventListener("click", () => {
    debugPanel?.toggle();
  });

  document.getElementById("btn-new-voyage")?.addEventListener("click", () => {
    showView("voyage");
    if (voyageConfigContainer) {
      createVoyageConfigPanel({
        container: voyageConfigContainer,
        onSearch: handleVoyageSearch,
        onSave: handleVoyageSave,
      });
    }
    if (voyageResultsContainer) {
      voyageResultsPanel = createVoyageResultsPanel(voyageResultsContainer);
    }
  });

  document.getElementById("btn-load-voyage")?.addEventListener("click", async () => {
    if (!savedVoyagesList) return;
    const voyages = await listVoyages();
    if (voyages.length === 0) {
      savedVoyagesList.innerHTML = '<p class="empty-list">No saved voyages.</p>';
      savedVoyagesList.style.display = "block";
      return;
    }
    savedVoyagesList.innerHTML = voyages
      .map((v) => `<button class="saved-voyage-item" data-id="${v.id}">${v.name}<span class="voyage-date">${new Date(v.updated_at).toLocaleDateString()}</span></button>`)
      .join("");
    savedVoyagesList.style.display = "block";

    savedVoyagesList.querySelectorAll(".saved-voyage-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = (btn as HTMLElement).dataset.id;
        if (!id) return;
        const config = await loadVoyage(id);
        if (!config) return;
        showView("voyage");
        if (voyageConfigContainer) {
          const panel = createVoyageConfigPanel({
            container: voyageConfigContainer,
            onSearch: handleVoyageSearch,
            onSave: handleVoyageSave,
          });
          panel.loadConfig(config);
        }
        if (voyageResultsContainer) {
          voyageResultsPanel = createVoyageResultsPanel(voyageResultsContainer);
        }
        savedVoyagesList.style.display = "none";
      });
    });
  });

  document.getElementById("btn-quick-search")?.addEventListener("click", () => {
    showView("search");
  });

  document.querySelectorAll(".btn-back-landing").forEach((btn) => {
    btn.addEventListener("click", () => showView("landing"));
  });

  async function handleVoyageSearch(config: VoyageConfig) {
    if (!voyageResultsPanel) return;
    voyageResultsPanel.showLoading();
    summaryPanel?.open();
    summaryPanel?.clear();

    try {
      const response = await searchVoyageInline(config);
      if (!response) {
        voyageResultsPanel.showError("Search returned no response.");
        return;
      }

      voyageResultsPanel.showResults(response.results);
      drawRoute(response.results.flight_options);

      if (response.results.agent_summary || response.results.travel_agent_findings) {
        summaryPanel?.showSummary(response.results);
      } else if (response.voyage_id) {
        summaryPanel?.streamSummary(response.voyage_id, response.results);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      voyageResultsPanel.showError(`Search failed: ${msg}`);
    }
  }

  async function handleVoyageSave(config: VoyageConfig) {
    try {
      const result = await createVoyage(config);
      const statusEl = document.getElementById("vr-status");
      if (statusEl) {
        statusEl.textContent = `Saved as "${result.name}" (${result.id.slice(0, 8)}...)`;
        statusEl.className = "results-status";
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("Save failed:", msg);
    }
  }

  const form = document.getElementById("search-form") as HTMLFormElement | null;
  if (form) {
    const tbody = document.getElementById("results-body") as HTMLTableSectionElement;
    const status = document.getElementById("results-status") as HTMLDivElement;
    const count = document.getElementById("results-count") as HTMLSpanElement;
    const searchBtn = document.getElementById("search-btn") as HTMLButtonElement;
    const streamMode = document.getElementById("stream-mode") as HTMLInputElement;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const params = buildSearchParams();

      if (params.origins.length === 0 || params.destinations.length === 0) {
        status.textContent = "Please enter origin and destination airports.";
        status.className = "results-status error";
        return;
      }

      tbody.innerHTML = "";
      count.textContent = "";
      searchBtn.disabled = true;

      const allOffers: FlightOffer[] = [];

      if (streamMode.checked) {
        status.textContent = "Searching... results will appear as they arrive.";
        status.className = "results-status loading";

        searchFlightsStream(
          params,
          (offer) => { allOffers.push(offer); addResultRow(offer, tbody); count.textContent = `${allOffers.length} results`; },
          (total) => { status.textContent = "Search complete."; status.className = "results-status"; count.textContent = `${total} results`; searchBtn.disabled = false; drawRoute(allOffers); },
          (error) => { status.textContent = `Stream error: ${error}. Trying REST fallback...`; status.className = "results-status error"; doRestSearch(params, tbody, status, count, searchBtn, allOffers); }
        );
      } else {
        doRestSearch(params, tbody, status, count, searchBtn, allOffers);
      }
    });
  }
});

async function doRestSearch(
  params: SearchParams,
  tbody: HTMLTableSectionElement,
  status: HTMLDivElement,
  countEl: HTMLSpanElement,
  searchBtn: HTMLButtonElement,
  allOffers: FlightOffer[]
) {
  status.textContent = "Searching...";
  status.className = "results-status loading";

  try {
    const results = await searchFlights(params);
    tbody.innerHTML = "";
    allOffers.length = 0;
    for (const offer of results) {
      allOffers.push(offer);
      addResultRow(offer, tbody);
    }
    countEl.textContent = `${results.length} results`;
    status.textContent = "Search complete.";
    status.className = "results-status";
    drawRoute(allOffers);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    status.textContent = `Error: ${msg}`;
    status.className = "results-status error";
  } finally {
    searchBtn.disabled = false;
  }
}
