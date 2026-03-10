function createSummaryPanel(container) {
  container.innerHTML = `
    <div class="summary-inner">
      <div class="summary-hdr">
        <h3>Voyage Summary</h3>
        <button class="summary-close">&times;</button>
      </div>
      <div class="summary-tabs">
        <button class="summary-tab active" data-tab="sum">Summary</button>
        <button class="summary-tab" data-tab="agent">Travel Agent</button>
      </div>
      <div class="summary-body">
        <div id="sp-sum"><p class="summary-placeholder">Run a search to see the summary.</p></div>
        <div id="sp-agent" style="display:none"><p class="summary-placeholder">Enable Travel Agent to see findings.</p></div>
      </div>
    </div>
  `;

  const sumEl = document.getElementById("sp-sum");
  const agentEl = document.getElementById("sp-agent");
  const closeBtn = container.querySelector(".summary-close");
  const tabs = container.querySelectorAll(".summary-tab");

  tabs.forEach(tab => {
    tab.onclick = () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const t = tab.dataset.tab;
      sumEl.style.display = t === "sum" ? "block" : "none";
      agentEl.style.display = t === "agent" ? "block" : "none";
    };
  });

  closeBtn.onclick = () => container.classList.remove("open");

  function md(text) {
    return text
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
  }

  return {
    open() { container.classList.add("open"); },
    close() { container.classList.remove("open"); },
    showSummary(results) {
      sumEl.innerHTML = results.agent_summary
        ? md(results.agent_summary)
        : '<p class="summary-placeholder">No summary available.</p>';
      if (results.travel_agent_findings) {
        const f = results.travel_agent_findings;
        agentEl.innerHTML = typeof f.summary === "string"
          ? md(f.summary)
          : `<pre style="white-space:pre-wrap;word-break:break-word;font-size:12px">${JSON.stringify(f, null, 2)}</pre>`;
      } else {
        agentEl.innerHTML = '<p class="summary-placeholder">Travel Agent was not enabled.</p>';
      }
      container.classList.add("open");
    },
    clear() {
      sumEl.innerHTML = '<p class="summary-placeholder">Run a search to see the summary.</p>';
      agentEl.innerHTML = '<p class="summary-placeholder">Enable Travel Agent to see findings.</p>';
    },
  };
}
