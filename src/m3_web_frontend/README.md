# M3 Web Frontend — 试卷宝

Zero-build, zero-npm static frontend for the Exam Paper Tool.

## Structure

```
src/m3_web_frontend/
├── index.html          # Main page: upload + paper list
├── paper.html          # Paper detail: preview + crop mistakes
├── mistakes.html       # Mistake library: filter + batch operations
├── export.html         # PDF export configuration
├── static/
│   ├── style.css       # Mobile-first design system (982 lines)
│   ├── api.js          # API wrapper (10 functions, 331 lines)
│   ├── app.js          # Shared helpers (toast, formatters, 197 lines)
│   └── crop.js         # Canvas crop interaction (566 lines)
└── mock/
    └── mock-server.py  # Dev mock server (801 lines, stdlib-only)
```

## Tech Stack

- **Alpine.js 3.13** (CDN) — reactive state management
- **Canvas API** (native) — crop interaction
- **Fetch API** (native) — HTTP requests
- **CSS** (native, mobile-first 375px) — design system with tokens
- **Python 3.11+** (mock server only) — stdlib-only, no deps

## Quick Start

```bash
cd /tmp/exam-paper-tool-ph23/src/m3_web_frontend

# Start mock server
python3 mock/mock-server.py 8000

# Open in browser
open http://localhost:8000/index.html
```

The mock server serves:
- All 4 HTML pages
- Static assets (CSS/JS)
- 10 mock API endpoints (POST/GET/PATCH/DELETE)
- Dynamic placeholder images
- Mock PDF exports

## API Endpoints (Mock)

All endpoints defined in `docs/INTERFACE-CONTRACT.md` §4.3/§4.4:

```
POST   /api/papers/upload          # multipart file upload
GET    /api/papers                  # list papers (filters: child_id, subject, status)
GET    /api/papers/{id}             # paper detail
POST   /api/papers/{id}/process     # trigger processing (sleeps 2s)
POST   /api/mistakes                # create mistake (crop box)
GET    /api/mistakes                # list mistakes (filters: child_id, subject, status, paper_id)
DELETE /api/mistakes/{id}           # delete mistake
PATCH  /api/mistakes/{id}           # update mistake (status, note, error_type)
POST   /api/export/pdf              # export PDF (returns download URL)
GET    /api/export/history          # export history
```

## Design System

Mobile-first, token-based CSS:

- **Colors**: `--color-primary` (#3B82F6), semantic status badges
- **Spacing**: 4px grid (`--space-1` to `--space-16`)
- **Typography**: System font stack (PingFang SC + SF Pro)
- **Touch targets**: ≥44px minimum
- **Responsive**: 375px mobile → 768px tablet → 1100px desktop

## Canvas Crop Interaction

State machine: `idle → drawing → moving → resizing → idle`

- **Drawing**: drag on empty area to create new box
- **Moving**: drag box body to reposition
- **Resizing**: drag 8-way handles (corners + edges)
- **Selection**: click box to select (shows handles)
- **Deletion**: Delete/Backspace key or X button
- **Coordinates**: stored in ORIGINAL image pixels (not canvas pixels)
- **Touch**: single-finger only, prevents scroll with `touch-action: none`

## Verification

All endpoints tested:

```bash
# API smoke test
curl http://localhost:8000/api/papers
curl http://localhost:8000/api/mistakes?paper_id=1
curl -X POST -H 'Content-Type: application/json' \
  -d '{"paper_id":1,"crop_x":10,"crop_y":20,"crop_width":100,"crop_height":50}' \
  http://localhost:8000/api/mistakes

# Static files
curl http://localhost:8000/index.html
curl http://localhost:8000/static/style.css
curl http://localhost:8000/static/api.js
curl http://localhost:8000/static/crop.js
curl http://localhost:8000/static/app.js

# Placeholder images (dynamic generation)
curl http://localhost:8000/static/data/placeholder/600x400/test.png

# Mock PDF
curl http://localhost:8000/static/data/exports/mock.pdf
```

## Production Deployment

In production, M4 (FastAPI) serves these files:

```python
# M4 mounts this directory as static files
app.mount("/", StaticFiles(directory="src/m3_web_frontend", html=True), name="frontend")
```

Change `API_BASE` in `static/api.js` if needed (default: `/api`).

## Browser Support

- **Desktop**: Chrome 90+, Safari 14+, Firefox 88+
- **Mobile**: iOS Safari 14+, Chrome Android 90+
- **Features**: Canvas 2D, Fetch, Alpine.js 3, CSS Grid, CSS Variables

## File Sizes

- `style.css`: 982 lines (mobile-first design system)
- `api.js`: 331 lines (10 API functions + error handling)
- `crop.js`: 566 lines (canvas state machine + coordinate conversion)
- `app.js`: 197 lines (toast, formatters, loading hooks)
- `index.html`: 307 lines (upload + paper list)
- `paper.html`: 345 lines (preview + crop)
- `mistakes.html`: 280 lines (filter + batch ops)
- `export.html`: 236 lines (PDF config)
- `mock-server.py`: 801 lines (stdlib-only mock)

**Total**: 4,045 lines, zero build tools, zero npm dependencies.

## Notes

- **Zero build**: no webpack, vite, npm, node — just HTML/CSS/JS
- **Alpine.js CDN**: 30KB (gzip ~10KB), local fallback commented in HTML
- **CORS**: mock server sends `Access-Control-Allow-Origin: *`
- **Multipart**: mock server uses stdlib `email` parser (Python 3.13+ compatible)
- **Placeholders**: PNG generator uses pure-stdlib zlib + struct (no Pillow)
- **PDF mock**: minimal PDF 1.4 structure (no external libs)

## Contract Compliance

All API calls match `docs/INTERFACE-CONTRACT.md` v1.0-FINAL:
- Endpoint paths
- Request/response shapes
- Parameter names (snake_case: `child_id`, `paper_type`, `error_type`)
- Status enums (`pending`, `processing`, `processed`, `failed`)
- Mistake status (`new`, `printed`, `practiced`, `passed`, `retry`)
