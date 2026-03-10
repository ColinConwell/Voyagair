const API_BASE = "/api";

interface ProviderStatus {
  name: string;
  configured: boolean;
  enabled: boolean;
}

interface DebugInfo {
  python_version: string;
  uptime_seconds: number;
  env: Record<string, string>;
  providers: ProviderStatus[];
  llm: Record<string, string>;
  cache: Record<string, string | number>;
  data_dir: string;
  recent_logs: string[];
}

export function createDebugPanel(container: HTMLElement) {
  container.innerHTML = `
    <div class="debug-inner">
      <div class="debug-header">
        <h3>Backend Debug</h3>
        <div class="debug-header-actions">
          <button class="btn-icon debug-refresh-btn" title="Refresh">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M2 8a6 6 0 0 1 10.5-4M14 8a6 6 0 0 1-10.5 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M12 1v3.5h-3.5M4 15v-3.5h3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
          <button class="debug-close-btn btn-icon" title="Close">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
          </button>
        </div>
      </div>
      <div class="debug-body">
        <div class="debug-section">
          <div class="debug-section-title">System</div>
          <div id="dbg-system" class="debug-kv"></div>
        </div>
        <div class="debug-section">
          <div class="debug-section-title">Providers</div>
          <div id="dbg-providers" class="debug-provider-grid"></div>
        </div>
        <div class="debug-section">
          <div class="debug-section-title">LLM</div>
          <div id="dbg-llm" class="debug-kv"></div>
        </div>
        <div class="debug-section">
          <div class="debug-section-title">Environment</div>
          <div id="dbg-env" class="debug-kv debug-kv-compact"></div>
        </div>
        <div class="debug-section">
          <div class="debug-section-title">
            Logs
            <button class="debug-clear-logs btn-icon-sm" title="Clear logs">clear</button>
          </div>
          <div id="dbg-logs" class="debug-logs"></div>
        </div>
      </div>
    </div>
  `;

  const closeBtn = container.querySelector(".debug-close-btn") as HTMLButtonElement;
  const refreshBtn = container.querySelector(".debug-refresh-btn") as HTMLButtonElement;
  const clearLogsBtn = container.querySelector(".debug-clear-logs") as HTMLButtonElement;

  closeBtn.addEventListener("click", () => container.classList.remove("open"));
  refreshBtn.addEventListener("click", () => load());
  clearLogsBtn.addEventListener("click", async () => {
    await fetch(`${API_BASE}/debug/logs/clear`, { method: "POST" });
    load();
  });

  async function load() {
    try {
      const resp = await fetch(`${API_BASE}/debug/info`);
      if (!resp.ok) {
        renderError("Failed to load debug info");
        return;
      }
      const info: DebugInfo = await resp.json();
      render(info);
    } catch {
      renderError("Cannot reach backend");
    }
  }

  function renderError(msg: string) {
    const sys = container.querySelector("#dbg-system") as HTMLDivElement;
    sys.innerHTML = `<div class="debug-error">${msg}</div>`;
  }

  function kvRow(key: string, value: string, status?: "ok" | "warn" | "err"): string {
    const cls = status ? ` debug-status-${status}` : "";
    return `<div class="debug-kv-row"><span class="debug-key">${key}</span><span class="debug-val${cls}">${value}</span></div>`;
  }

  function render(info: DebugInfo) {
    const sysEl = container.querySelector("#dbg-system") as HTMLDivElement;
    const upMin = Math.floor(info.uptime_seconds / 60);
    const upSec = Math.round(info.uptime_seconds % 60);
    sysEl.innerHTML =
      kvRow("Python", info.python_version) +
      kvRow("Uptime", `${upMin}m ${upSec}s`) +
      kvRow("Data Dir", info.data_dir);

    const provEl = container.querySelector("#dbg-providers") as HTMLDivElement;
    provEl.innerHTML = info.providers
      .map((p) => {
        const status = p.configured && p.enabled ? "ok" : p.configured ? "warn" : "err";
        const label = p.configured && p.enabled ? "active" : p.configured ? "disabled" : "not configured";
        return `<div class="debug-provider debug-status-${status}"><span class="debug-provider-name">${p.name}</span><span class="debug-provider-label">${label}</span></div>`;
      })
      .join("");

    const llmEl = container.querySelector("#dbg-llm") as HTMLDivElement;
    llmEl.innerHTML =
      kvRow("Provider", info.llm.provider) +
      kvRow("Model", info.llm.model) +
      kvRow("API Key", info.llm.api_key, info.llm.api_key === "set" ? "ok" : "err");

    const envEl = container.querySelector("#dbg-env") as HTMLDivElement;
    envEl.innerHTML = Object.entries(info.env)
      .map(([k, v]) => kvRow(k, v, v.startsWith("***") || v === "set" ? "ok" : "warn"))
      .join("");

    renderLogs(info.recent_logs);
  }

  function renderLogs(logs: string[]) {
    const logsEl = container.querySelector("#dbg-logs") as HTMLDivElement;
    if (logs.length === 0) {
      logsEl.innerHTML = '<div class="debug-log-empty">No recent logs</div>';
      return;
    }
    logsEl.innerHTML = logs
      .map((line) => {
        const level = line.includes(" ERROR ") ? "error" : line.includes(" WARNING ") ? "warn" : "info";
        return `<div class="debug-log-line debug-log-${level}">${escapeHtml(line)}</div>`;
      })
      .join("");
    logsEl.scrollTop = logsEl.scrollHeight;
  }

  function escapeHtml(s: string): string {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  let pollTimer: ReturnType<typeof setInterval> | null = null;

  return {
    open: () => {
      container.classList.add("open");
      load();
      if (!pollTimer) pollTimer = setInterval(load, 10000);
    },
    close: () => {
      container.classList.remove("open");
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    },
    toggle: () => {
      if (container.classList.contains("open")) {
        container.classList.remove("open");
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      } else {
        container.classList.add("open");
        load();
        if (!pollTimer) pollTimer = setInterval(load, 10000);
      }
    },
    refresh: load,
  };
}
