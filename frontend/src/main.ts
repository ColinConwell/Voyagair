import {
  FlightOffer,
  SearchParams,
  getAirport,
  searchFlights,
  searchFlightsStream,
} from "./api";

declare const L: typeof import("leaflet");

let map: ReturnType<typeof L.map>;
let routeLayer: ReturnType<typeof L.layerGroup>;

function initMap() {
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
  const carriers = [...new Set(legs.map((l) => l.carrier).filter(Boolean))].join(
    ", "
  );
  const numStops = Math.max(0, legs.length - 1);

  let totalMinutes = 0;
  for (const leg of legs) {
    totalMinutes += leg.duration_minutes || 0;
  }
  if (totalMinutes === 0 && legs.length >= 2) {
    const dep = new Date(legs[0].departure).getTime();
    const arr = new Date(legs[legs.length - 1].arrival).getTime();
    totalMinutes = Math.round((arr - dep) / 60000);
  }

  return { origin, destination, departure, carriers, numStops, totalMinutes };
}

function addResultRow(offer: FlightOffer, tbody: HTMLTableSectionElement) {
  const { origin, destination, departure, carriers, numStops, totalMinutes } =
    computeOfferMeta(offer);

  const depStr = departure
    ? new Date(departure).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "N/A";

  const tr = document.createElement("tr");
  const stopsClass =
    numStops === 0 ? "stops-0" : numStops === 1 ? "stops-1" : "stops-2";
  const stopsLabel =
    numStops === 0 ? "Nonstop" : `${numStops} stop${numStops > 1 ? "s" : ""}`;

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
        [
          [src.lat, src.lon],
          [dst.lat, dst.lon],
        ],
        {
          color: "#58a6ff",
          weight: 2,
          opacity: 0.6,
          dashArray: "6 4",
        }
      ).addTo(routeLayer);
    }
  }

  for (const [code, pos] of airportCache) {
    L.circleMarker([pos.lat, pos.lon], {
      radius: 5,
      color: "#58a6ff",
      fillColor: "#58a6ff",
      fillOpacity: 0.8,
      weight: 1,
    })
      .bindTooltip(code, {
        permanent: true,
        direction: "top",
        className: "airport-tooltip",
      })
      .addTo(routeLayer);
  }

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [40, 40] });
  }
}

function buildSearchParams(): SearchParams {
  const origins = (document.getElementById("origins") as HTMLInputElement).value
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  const destinations = (
    document.getElementById("destinations") as HTMLInputElement
  ).value
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
  const dateVal = (document.getElementById("dates") as HTMLInputElement).value;
  const adults = parseInt(
    (document.getElementById("adults") as HTMLInputElement).value
  );
  const cabin = (document.getElementById("cabin") as HTMLSelectElement).value;
  const maxStopsVal = (
    document.getElementById("max-stops") as HTMLSelectElement
  ).value;
  const sort = (document.getElementById("sort") as HTMLSelectElement).value;
  const maxPriceVal = (
    document.getElementById("max-price") as HTMLInputElement
  ).value;

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

document.addEventListener("DOMContentLoaded", () => {
  initMap();

  const form = document.getElementById("search-form") as HTMLFormElement;
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
        (offer) => {
          allOffers.push(offer);
          addResultRow(offer, tbody);
          count.textContent = `${allOffers.length} results`;
        },
        (total) => {
          status.textContent = `Search complete.`;
          status.className = "results-status";
          count.textContent = `${total} results`;
          searchBtn.disabled = false;
          drawRoute(allOffers);
        },
        (error) => {
          status.textContent = `Stream error: ${error}. Trying REST fallback...`;
          status.className = "results-status error";
          doRestSearch(params, tbody, status, count, searchBtn, allOffers);
        }
      );
    } else {
      doRestSearch(params, tbody, status, count, searchBtn, allOffers);
    }
  });
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
  } catch (err: any) {
    status.textContent = `Error: ${err.message}`;
    status.className = "results-status error";
  } finally {
    searchBtn.disabled = false;
  }
}
