const API_BASE = "/api";

export interface FlightOffer {
  id: string;
  provider: string;
  legs: Leg[];
  price: number;
  currency: string;
  deep_link: string;
  cabin_class: string;
}

export interface Leg {
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  carrier: string;
  carrier_name: string;
  flight_number: string;
  mode: string;
  duration_minutes: number;
  stops: number;
}

export interface SearchParams {
  origins: string[];
  destinations: string[];
  departure_dates: string[];
  adults?: number;
  cabin_class?: string;
  max_price?: number;
  max_stops?: number;
  sort_by?: string;
  limit?: number;
  currency?: string;
}

export interface AirportInfo {
  iata: string;
  name: string;
  city: string;
  country_code: string;
  latitude: number;
  longitude: number;
}

export async function searchFlights(
  params: SearchParams
): Promise<FlightOffer[]> {
  const resp = await fetch(`${API_BASE}/search/flights`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!resp.ok) throw new Error(`Search failed: ${resp.statusText}`);
  const data = await resp.json();
  return data.results;
}

export function searchFlightsStream(
  params: SearchParams,
  onResult: (offer: FlightOffer) => void,
  onComplete: (count: number) => void,
  onError: (error: string) => void
): WebSocket {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}${API_BASE}/ws/search`);

  ws.onopen = () => {
    ws.send(JSON.stringify(params));
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "result") {
      onResult(msg.data);
    } else if (msg.type === "complete") {
      onComplete(msg.count);
      ws.close();
    } else if (msg.type === "error") {
      onError(msg.message);
      ws.close();
    }
  };

  ws.onerror = () => {
    onError("WebSocket connection failed. Falling back to REST.");
    ws.close();
  };

  return ws;
}

export async function searchAirports(query: string): Promise<AirportInfo[]> {
  const resp = await fetch(
    `${API_BASE}/airports/search?q=${encodeURIComponent(query)}`
  );
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.results;
}

export async function getAirport(iata: string): Promise<AirportInfo | null> {
  const resp = await fetch(`${API_BASE}/airports/${iata.toUpperCase()}`);
  if (!resp.ok) return null;
  const data = await resp.json();
  if (data.error) return null;
  return data;
}
