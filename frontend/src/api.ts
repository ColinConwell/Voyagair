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

export interface LocationSpec {
  type: "region" | "country" | "city" | "airport";
  value: string;
  label?: string;
  resolved_airports?: string[];
}

export interface TimeBudget {
  total_days: number;
  max_journey_hours: number | null;
  max_multi_ticket_hours: number | null;
}

export interface CostBudget {
  max_total: number | null;
  max_per_leg: number | null;
  max_single_ticket: number | null;
  max_multi_ticket_total: number | null;
  currency: string;
}

export interface NotificationConfig {
  type: "sms" | "email" | "webapp";
  target: string;
  enabled: boolean;
}

export interface SaveRefreshConfig {
  auto_save: boolean;
  save_path: string | null;
  notifications: NotificationConfig[];
  auto_refresh_interval_minutes: number | null;
  auto_refresh_enabled: boolean;
}

export interface MCPServerConfig {
  name: string;
  url: string;
  auth_token: string;
  tools: string[];
  enabled: boolean;
}

export interface TravelAgentConfig {
  enabled: boolean;
  use_builtin_tools: boolean;
  mcp_servers: MCPServerConfig[];
  custom_instructions: string | null;
  model: string | null;
  provider: string | null;
}

export interface VoyageConfig {
  id?: string;
  name: string;
  starting_points: LocationSpec[];
  end_points: LocationSpec[];
  sites_along_the_way: LocationSpec[];
  departure_date: string | null;
  return_date: string | null;
  adults: number;
  cabin_class: string;
  time_budget: TimeBudget;
  cost_budget: CostBudget;
  travel_agent: TravelAgentConfig;
  save_refresh: SaveRefreshConfig;
  optimize_for: string;
}

export interface TransportOption {
  origin: string;
  destination: string;
  mode: string;
  carrier: string;
  price_min: number | null;
  price_max: number | null;
  currency: string;
}

export interface VoyageResults {
  voyage_id: string;
  flight_options: FlightOffer[];
  transport_options: TransportOption[];
  agent_summary: string | null;
  travel_agent_findings: Record<string, unknown> | null;
  search_duration_seconds: number;
}

export interface VoyageSearchResponse {
  voyage_id: string;
  flight_count: number;
  transport_count: number;
  search_duration_seconds: number;
  results: VoyageResults;
}

export interface VoyageSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface AutocompleteGroups {
  airports: AirportInfo[];
  cities: Array<{ city: string; country_code: string; airport_count: number }>;
  countries: Array<{
    country_code: string;
    country: string;
    airport_count: number;
  }>;
  regions: Array<{ region: string; country_count: number }>;
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

export async function searchAirportsGrouped(
  query: string
): Promise<AutocompleteGroups> {
  const resp = await fetch(
    `${API_BASE}/airports/search?q=${encodeURIComponent(query)}&grouped=true`
  );
  if (!resp.ok)
    return { airports: [], cities: [], countries: [], regions: [] };
  const data = await resp.json();
  return data.groups;
}

export async function getAirport(iata: string): Promise<AirportInfo | null> {
  const resp = await fetch(`${API_BASE}/airports/${iata.toUpperCase()}`);
  if (!resp.ok) return null;
  const data = await resp.json();
  if (data.error) return null;
  return data;
}

export async function createVoyage(
  config: VoyageConfig
): Promise<{ id: string; name: string }> {
  const resp = await fetch(`${API_BASE}/voyage/new`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!resp.ok) throw new Error(`Create voyage failed: ${resp.statusText}`);
  return resp.json();
}

export async function listVoyages(): Promise<VoyageSummary[]> {
  const resp = await fetch(`${API_BASE}/voyage/list`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.voyages;
}

export async function loadVoyage(
  id: string
): Promise<VoyageConfig | null> {
  const resp = await fetch(`${API_BASE}/voyage/${id}`);
  if (!resp.ok) return null;
  const data = await resp.json();
  if (data.error) return null;
  return data;
}

export async function deleteVoyage(id: string): Promise<boolean> {
  const resp = await fetch(`${API_BASE}/voyage/${id}`, { method: "DELETE" });
  if (!resp.ok) return false;
  const data = await resp.json();
  return data.deleted;
}

export async function searchVoyage(
  id: string
): Promise<VoyageSearchResponse | null> {
  const resp = await fetch(`${API_BASE}/voyage/${id}/search`, {
    method: "POST",
  });
  if (!resp.ok) return null;
  return resp.json();
}

export async function searchVoyageInline(
  config: VoyageConfig
): Promise<VoyageSearchResponse | null> {
  const resp = await fetch(`${API_BASE}/voyage/search-inline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!resp.ok) return null;
  return resp.json();
}

export function streamVoyageSummary(
  voyageId: string,
  results: VoyageResults,
  onToken: (token: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): WebSocket {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(
    `${protocol}//${location.host}${API_BASE}/voyage/ws/summary/${voyageId}`
  );

  ws.onopen = () => {
    ws.send(JSON.stringify(results));
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "token") {
      onToken(msg.content);
    } else if (msg.type === "complete") {
      onComplete();
      ws.close();
    } else if (msg.type === "error") {
      onError(msg.message);
      ws.close();
    }
  };

  ws.onerror = () => {
    onError("Summary WebSocket connection failed.");
    ws.close();
  };

  return ws;
}
