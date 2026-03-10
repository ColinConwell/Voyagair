import { searchAirportsGrouped, type LocationSpec } from "../api";

interface LocationInputOptions {
  container: HTMLElement;
  label: string;
  placeholder?: string;
  multi?: boolean;
  onChange?: (specs: LocationSpec[]) => void;
}

let debounceTimer: ReturnType<typeof setTimeout>;

export function createLocationInput(opts: LocationInputOptions) {
  const { container, label, placeholder, multi = true, onChange } = opts;
  const selected: LocationSpec[] = [];

  container.innerHTML = `
    <label class="location-label">${label}</label>
    <div class="location-input-wrapper">
      <div class="location-chips"></div>
      <input type="text" class="location-search" placeholder="${placeholder || "Search airports, cities, countries..."}" autocomplete="off" />
      <div class="location-dropdown"></div>
    </div>
  `;

  const input = container.querySelector(".location-search") as HTMLInputElement;
  const dropdown = container.querySelector(".location-dropdown") as HTMLDivElement;
  const chipsEl = container.querySelector(".location-chips") as HTMLDivElement;

  function renderChips() {
    chipsEl.innerHTML = selected
      .map(
        (s, i) =>
          `<span class="location-chip" data-index="${i}">
            <span class="chip-type">${s.type}</span>
            <span class="chip-label">${s.label || s.value}</span>
            <button class="chip-remove" data-index="${i}">&times;</button>
          </span>`
      )
      .join("");

    chipsEl.querySelectorAll(".chip-remove").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = parseInt((btn as HTMLElement).dataset.index || "0");
        selected.splice(idx, 1);
        renderChips();
        onChange?.(selected);
      });
    });
  }

  function addSpec(spec: LocationSpec) {
    if (!multi) selected.length = 0;
    const exists = selected.some(
      (s) => s.type === spec.type && s.value === spec.value
    );
    if (!exists) {
      selected.push(spec);
      renderChips();
      onChange?.(selected);
    }
    input.value = "";
    dropdown.classList.remove("open");
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      dropdown.classList.remove("open");
      return;
    }
    debounceTimer = setTimeout(async () => {
      const groups = await searchAirportsGrouped(q);
      renderDropdown(groups);
    }, 300);
  });

  input.addEventListener("focus", () => {
    if (dropdown.children.length > 0) dropdown.classList.add("open");
  });

  document.addEventListener("click", (e) => {
    if (!container.contains(e.target as Node)) {
      dropdown.classList.remove("open");
    }
  });

  function renderDropdown(groups: Awaited<ReturnType<typeof searchAirportsGrouped>>) {
    dropdown.innerHTML = "";

    if (groups.regions.length > 0) {
      const section = makeSection("Regions");
      for (const r of groups.regions.slice(0, 5)) {
        section.appendChild(
          makeItem(`${r.region} (${r.country_count} countries)`, () =>
            addSpec({ type: "region", value: r.region, label: r.region })
          )
        );
      }
      dropdown.appendChild(section);
    }

    if (groups.countries.length > 0) {
      const section = makeSection("Countries");
      for (const c of groups.countries.slice(0, 5)) {
        section.appendChild(
          makeItem(`${c.country} [${c.country_code}] (${c.airport_count} airports)`, () =>
            addSpec({ type: "country", value: c.country_code, label: `${c.country} (${c.country_code})` })
          )
        );
      }
      dropdown.appendChild(section);
    }

    if (groups.cities.length > 0) {
      const section = makeSection("Cities");
      for (const c of groups.cities.slice(0, 5)) {
        section.appendChild(
          makeItem(`${c.city}, ${c.country_code} (${c.airport_count} airports)`, () =>
            addSpec({ type: "city", value: c.city, label: `${c.city} (${c.country_code})` })
          )
        );
      }
      dropdown.appendChild(section);
    }

    if (groups.airports.length > 0) {
      const section = makeSection("Airports");
      for (const a of groups.airports.slice(0, 10)) {
        section.appendChild(
          makeItem(`${a.iata} - ${a.name}, ${a.city}`, () =>
            addSpec({ type: "airport", value: a.iata, label: `${a.iata} - ${a.name}` })
          )
        );
      }
      dropdown.appendChild(section);
    }

    if (dropdown.children.length > 0) {
      dropdown.classList.add("open");
    } else {
      dropdown.classList.remove("open");
    }
  }

  function makeSection(title: string): HTMLDivElement {
    const div = document.createElement("div");
    div.className = "dropdown-section";
    div.innerHTML = `<div class="dropdown-section-title">${title}</div>`;
    return div;
  }

  function makeItem(text: string, onClick: () => void): HTMLDivElement {
    const div = document.createElement("div");
    div.className = "dropdown-item";
    div.textContent = text;
    div.addEventListener("click", (e) => {
      e.stopPropagation();
      onClick();
    });
    return div;
  }

  return {
    getSelected: () => [...selected],
    setSelected: (specs: LocationSpec[]) => {
      selected.length = 0;
      selected.push(...specs);
      renderChips();
    },
    clear: () => {
      selected.length = 0;
      renderChips();
      input.value = "";
    },
  };
}
