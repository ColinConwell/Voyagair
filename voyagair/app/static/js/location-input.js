const API_BASE = "/api";

function createLocationInput(container, label, placeholder, onChange) {
  const selected = [];

  container.innerHTML = `
    <label class="field label" style="font-size:12px;font-weight:500;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;display:block">${label}</label>
    <div class="loc-wrapper">
      <div class="loc-chips"></div>
      <input type="text" class="loc-input" placeholder="${placeholder || "Search airports, cities, countries..."}" autocomplete="off" />
      <div class="loc-dropdown"></div>
    </div>
  `;

  const input = container.querySelector(".loc-input");
  const dropdown = container.querySelector(".loc-dropdown");
  const chipsEl = container.querySelector(".loc-chips");
  let timer;

  function renderChips() {
    chipsEl.innerHTML = selected.map((s, i) =>
      `<span class="loc-chip">
        <span class="loc-chip-type">${s.type}</span>
        <span>${s.label || s.value}</span>
        <button class="loc-chip-rm" data-idx="${i}">&times;</button>
      </span>`
    ).join("");
    chipsEl.querySelectorAll(".loc-chip-rm").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        selected.splice(parseInt(btn.dataset.idx), 1);
        renderChips();
        if (onChange) onChange(selected);
      };
    });
  }

  function addSpec(spec) {
    if (selected.some(s => s.type === spec.type && s.value === spec.value)) return;
    selected.push(spec);
    renderChips();
    input.value = "";
    dropdown.classList.remove("open");
    if (onChange) onChange(selected);
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { dropdown.classList.remove("open"); return; }
    timer = setTimeout(async () => {
      try {
        const resp = await fetch(`${API_BASE}/airports/search?q=${encodeURIComponent(q)}&grouped=true`);
        if (!resp.ok) return;
        const data = await resp.json();
        renderDropdown(data.groups);
      } catch (_) {}
    }, 300);
  });

  input.addEventListener("focus", () => {
    if (dropdown.children.length > 0) dropdown.classList.add("open");
  });

  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) dropdown.classList.remove("open");
  });

  function renderDropdown(groups) {
    dropdown.innerHTML = "";
    if (groups.regions && groups.regions.length > 0) {
      const sec = makeSection("Regions");
      groups.regions.slice(0, 5).forEach(r => {
        sec.appendChild(makeItem(`${r.region} (${r.country_count} countries)`, () => addSpec({ type: "region", value: r.region, label: r.region })));
      });
      dropdown.appendChild(sec);
    }
    if (groups.countries && groups.countries.length > 0) {
      const sec = makeSection("Countries");
      groups.countries.slice(0, 5).forEach(c => {
        sec.appendChild(makeItem(`${c.country} [${c.country_code}]`, () => addSpec({ type: "country", value: c.country_code, label: `${c.country} (${c.country_code})` })));
      });
      dropdown.appendChild(sec);
    }
    if (groups.cities && groups.cities.length > 0) {
      const sec = makeSection("Cities");
      groups.cities.slice(0, 5).forEach(c => {
        sec.appendChild(makeItem(`${c.city}, ${c.country_code}`, () => addSpec({ type: "city", value: c.city, label: `${c.city} (${c.country_code})` })));
      });
      dropdown.appendChild(sec);
    }
    if (groups.airports && groups.airports.length > 0) {
      const sec = makeSection("Airports");
      groups.airports.slice(0, 10).forEach(a => {
        sec.appendChild(makeItem(`${a.iata} - ${a.name}, ${a.city}`, () => addSpec({ type: "airport", value: a.iata, label: `${a.iata} - ${a.name}` })));
      });
      dropdown.appendChild(sec);
    }
    dropdown.classList.toggle("open", dropdown.children.length > 0);
  }

  function makeSection(title) {
    const d = document.createElement("div");
    d.className = "dd-section";
    d.innerHTML = `<div class="dd-title">${title}</div>`;
    return d;
  }

  function makeItem(text, onClick) {
    const d = document.createElement("div");
    d.className = "dd-item";
    d.textContent = text;
    d.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
    return d;
  }

  return {
    getSelected: () => [...selected],
    setSelected: (specs) => { selected.length = 0; selected.push(...specs); renderChips(); },
    clear: () => { selected.length = 0; renderChips(); input.value = ""; },
  };
}
