<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-09-02 | Updated: 2026-09-02 -->

# web

## Purpose

Embedded operator dashboard (D-23). Served by FastAPI from this folder. No Node/Vite build step in the current tree (D-7 is not implemented here).

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Package marker so setuptools includes the package |
| `index.html` | Dashboard shell |
| `styles.css` | Dashboard CSS (no inline styles in HTML) |
| `app.js` | Token login, state/events WS, e-stop, host cards |

## Subdirectories

None.

## For AI Agents

### Working In This Directory

- Assets are packaged via `setup.py` `package_data`. Keep filenames `index.html`, `styles.css`, `app.js`.
- CSP forbids inline script/style. Do not add `onclick=` handlers or `<style>` blocks.
- Talk only to `/api/v1` and `/ws/*` on the same origin.

### Testing Requirements

`src/rosy_core/test/test_dashboard.py`, `test_host_cards.py`; browser: `test/test_dashboard_browser.py`.

### Common Patterns

Vanilla JS. Viewer/operator/admin tokens from config. Teleop is hold-to-drive (~100 ms), not latched.

## Dependencies

### Internal

- `api/app.py` FileResponse + MIME map

### External

None (browser APIs only).

<!-- MANUAL: -->
