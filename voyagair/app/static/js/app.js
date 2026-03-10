const API = "/api";

function showView(name) {
  document.querySelectorAll(".view").forEach(el => {
    el.classList.toggle("active", el.dataset.view === name);
  });
  if (name === "landing") {
    document.getElementById("summary-sidebar").classList.remove("open");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  showView("landing");

  let resultsPanel = null;
  let summaryPanel = null;

  summaryPanel = createSummaryPanel(document.getElementById("summary-sidebar"));

  document.getElementById("btn-new").onclick = () => {
    showView("voyage");
    createVoyageConfig(document.getElementById("config-container"), handleSearch, handleSave);
    resultsPanel = createVoyageResults(document.getElementById("results-container"));
  };

  document.getElementById("btn-load").onclick = async () => {
    const list = document.getElementById("saved-list");
    try {
      const resp = await fetch(`${API}/voyage/list`);
      const data = await resp.json();
      const voyages = data.voyages || [];
      if (voyages.length === 0) {
        list.innerHTML = '<p style="text-align:center;color:var(--text-muted);padding:16px">No saved voyages.</p>';
        list.style.display = "block";
        return;
      }
      list.innerHTML = voyages.map(v =>
        `<div class="saved-item" data-id="${v.id}">${v.name}<span class="saved-date">${new Date(v.updated_at).toLocaleDateString()}</span></div>`
      ).join("");
      list.style.display = "block";
      list.querySelectorAll(".saved-item").forEach(item => {
        item.onclick = async () => {
          const id = item.dataset.id;
          const r = await fetch(`${API}/voyage/${id}`);
          const cfg = await r.json();
          if (cfg.error) return;
          showView("voyage");
          const panel = createVoyageConfig(document.getElementById("config-container"), handleSearch, handleSave);
          panel.load(cfg);
          resultsPanel = createVoyageResults(document.getElementById("results-container"));
          list.style.display = "none";
        };
      });
    } catch (_) {
      list.innerHTML = '<p style="color:var(--danger)">Failed to load voyages.</p>';
      list.style.display = "block";
    }
  };

  document.querySelectorAll(".btn-back").forEach(btn => {
    btn.onclick = () => showView("landing");
  });

  async function handleSearch(config) {
    if (!resultsPanel) return;
    resultsPanel.showLoading();
    summaryPanel.open();
    summaryPanel.clear();

    try {
      const resp = await fetch(`${API}/voyage/search-inline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!resp.ok) throw new Error(resp.statusText);
      const data = await resp.json();
      resultsPanel.showResults(data.results);
      summaryPanel.showSummary(data.results);
    } catch (err) {
      resultsPanel.showError("Search failed: " + err.message);
    }
  }

  async function handleSave(config) {
    try {
      const resp = await fetch(`${API}/voyage/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      const data = await resp.json();
      const status = document.getElementById("vr-status");
      if (status) {
        status.textContent = `Saved as "${data.name}" (${data.id.slice(0, 8)}...)`;
        status.className = "results-status";
      }
    } catch (err) {
      console.error("Save failed:", err);
    }
  }
});
