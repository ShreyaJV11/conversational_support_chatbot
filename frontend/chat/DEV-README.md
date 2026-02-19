Development notes — Chat widget

- Start backend (from project root):

```bash
# From repository root
uvicorn app.main:app --reload --port 8000
```

- Start frontend dev server (chat widget):

```bash
cd frontend/chat
npm install
npm run dev
```

Notes:
- Vite dev server proxies `/api` to `http://127.0.0.1:8000` so requests like `/api/chat` will be forwarded to the backend.
- The widget default `apiBaseUrl` is `http://127.0.0.1:8000/api` when initialized without config; when developing with Vite the proxy ensures these calls work without CORS issues.
- Backend already enables CORS for development (allows all origins). Adjust production CORS settings appropriately.
