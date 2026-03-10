# Voyagair UI Development

Use this skill when working on either frontend (TypeScript or vanilla JS).

## Architecture

### TypeScript Frontend (`frontend/`)
- Entry: `frontend/index.html` + `frontend/src/main.ts`
- API client: `frontend/src/api.ts` (typed fetch wrappers)
- Panels: `frontend/src/panels/` (voyage-config, voyage-results, summary-panel)
- Components: `frontend/src/components/` (location-input with autocomplete)
- Styles: `frontend/src/styles/main.css`
- Build: Vite (`npm run build` or `just build-frontend`)

### Vanilla App (`voyagair/app/`)
- Entry: `voyagair/app/templates/index.html`
- JS: `voyagair/app/static/js/` (app.js, voyage-config.js, etc.)
- CSS: `voyagair/app/static/css/app.css`
- Served by FastAPI at `/app/`

### Shared Resources (`shared/`)
- `shared/styles/variables.css` - CSS custom properties
- `shared/schema/` - JSON schema files (regions, cabin classes)

## Theming
- Dark theme is default (`:root` variables)
- Light theme via `[data-theme="light"]` on `<html>`
- Theme preference saved in localStorage as `voyagair-theme`
- Toggle button in header

## Key Patterns
- Location inputs use debounced autocomplete against `/api/airports/search?grouped=true`
- Results render in HTML tables with color-coded stops
- Summary panel uses WebSocket streaming for real-time AI output
- Collapsible sections via `.collapsed` class toggle
