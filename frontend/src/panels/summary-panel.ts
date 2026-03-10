import type { VoyageResults } from "../api";
import { streamVoyageSummary } from "../api";

export function createSummaryPanel(container: HTMLElement) {
  container.innerHTML = `
    <div class="summary-panel">
      <div class="summary-header">
        <h3>Voyage Summary</h3>
        <button class="summary-close-btn" title="Close">&times;</button>
      </div>
      <div class="summary-tabs">
        <button class="summary-tab active" data-tab="summary">Summary</button>
        <button class="summary-tab" data-tab="agent">Travel Agent</button>
      </div>
      <div class="summary-content">
        <div id="summary-text" class="summary-text">
          <p class="summary-placeholder">Run a voyage search to see the summary here.</p>
        </div>
        <div id="agent-text" class="summary-text" style="display:none">
          <p class="summary-placeholder">Enable the Travel Agent in your voyage config to see findings here.</p>
        </div>
      </div>
    </div>
  `;

  const summaryText = container.querySelector("#summary-text") as HTMLDivElement;
  const agentText = container.querySelector("#agent-text") as HTMLDivElement;
  const closeBtn = container.querySelector(".summary-close-btn") as HTMLButtonElement;
  const tabs = container.querySelectorAll(".summary-tab");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const target = (tab as HTMLElement).dataset.tab;
      summaryText.style.display = target === "summary" ? "block" : "none";
      agentText.style.display = target === "agent" ? "block" : "none";
    });
  });

  closeBtn.addEventListener("click", () => {
    container.classList.remove("open");
  });

  function renderMarkdown(text: string): string {
    return text
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
  }

  return {
    open: () => {
      container.classList.add("open");
    },
    close: () => {
      container.classList.remove("open");
    },
    showSummary: (results: VoyageResults) => {
      if (results.agent_summary) {
        summaryText.innerHTML = `<div class="markdown-body">${renderMarkdown(results.agent_summary)}</div>`;
      } else {
        summaryText.innerHTML = `<p class="summary-placeholder">No summary available.</p>`;
      }

      if (results.travel_agent_findings) {
        const findings = results.travel_agent_findings;
        const summaryStr = (findings as Record<string, unknown>).summary;
        if (typeof summaryStr === "string") {
          agentText.innerHTML = `<div class="markdown-body">${renderMarkdown(summaryStr)}</div>`;
        } else {
          agentText.innerHTML = `<pre class="agent-raw">${JSON.stringify(findings, null, 2)}</pre>`;
        }
      } else {
        agentText.innerHTML = `<p class="summary-placeholder">Travel Agent was not enabled for this search.</p>`;
      }

      container.classList.add("open");
    },
    streamSummary: (voyageId: string, results: VoyageResults) => {
      summaryText.innerHTML = '<div class="markdown-body streaming"></div>';
      const streamTarget = summaryText.querySelector(".markdown-body") as HTMLDivElement;
      let accumulated = "";

      container.classList.add("open");

      streamVoyageSummary(
        voyageId,
        results,
        (token) => {
          accumulated += token;
          streamTarget.innerHTML = renderMarkdown(accumulated);
          streamTarget.scrollTop = streamTarget.scrollHeight;
        },
        () => {
          streamTarget.classList.remove("streaming");
        },
        (error) => {
          streamTarget.innerHTML += `<p class="summary-error">Stream error: ${error}</p>`;
          streamTarget.classList.remove("streaming");
        }
      );
    },
    clear: () => {
      summaryText.innerHTML = `<p class="summary-placeholder">Run a voyage search to see the summary here.</p>`;
      agentText.innerHTML = `<p class="summary-placeholder">Enable the Travel Agent to see findings here.</p>`;
    },
  };
}
