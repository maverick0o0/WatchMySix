# WatchMySix Frontend

This project provides a lightweight React interface for launching WatchMySix reconnaissance jobs, monitoring their progress, and downloading generated artifacts such as `live-subs.txt` and `subs.txt`.

## Getting started

```bash
cd frontend
npm install
npm run dev
```

The development server defaults to `http://localhost:5173`. Set `VITE_API_BASE_URL` in a `.env` file (or via the shell) if your backend is not running on the same origin:

```
VITE_API_BASE_URL=http://localhost:8000
```

## Available scripts

- `npm run dev` – Start Vite in development mode with hot module replacement.
- `npm run build` – Produce a production build under `dist/`.
- `npm run lint` – Run ESLint using the configuration in `eslint.config.js`.

## Backend expectations

The UI expects the WatchMySix API to expose the following endpoints:

- `POST /api/jobs` – Starts a new recon job. The request body includes the `target` domain and the array of selected `tools`. The response must return a `jobId` (or `id`) that identifies the run.
- `GET /api/jobs/{jobId}/logs` – Provides a Server-Sent Events (SSE) stream with log messages. Optionally emit custom `complete` or `done` events to signal job completion and `artifact` events whenever new files are ready.
- `GET /api/jobs/{jobId}/artifacts` – Returns a JSON array of available artifacts. Each item should contain at least a `name` and `url` property.

## UI highlights

- Domain input with validation and a curated set of tool toggles (Certificate Search, WaybackURLs, Gau, Waymore, Subfinder, Chaos, GitHub, GitLab, Sourcegraph, GatherURLs, and static/dynamic brute force).
- Live log streaming panel that automatically switches to an idle message when no data is available.
- Artifact list that refreshes periodically while a job is running and exposes download links for generated files.
- Graceful error handling, status messaging, loading indicators, and disabled controls while a run is active.
