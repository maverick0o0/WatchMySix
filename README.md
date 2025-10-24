# WatchMySix

WatchMySix is a containerized toolkit tailored for subdomain enumeration and recon workflows. The image bundles ProjectDiscovery's reconnaissance utilities (via `pdtm`), additional Go-based helpers, DNS wordlists, and backend automations so that you can jump directly into asset discovery without manually stitching the tooling together.

## Features

- Preinstalled ProjectDiscovery CLI tools through `pdtm` (e.g., `subfinder`, `httpx`, `katana`).
- Extra reconnaissance tools such as `puredns`, `amass`, `gotator`, `gospider`, `anew`, and more.
- Curated DNS wordlists and resolver lists placed under `/opt/watchmysix` inside the container.
- Backend-powered integrations for crt.sh lookups and Sourcegraph enumeration without relying on custom shell helpers.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) 24.0+ (or any modern version capable of building images from Dockerfiles).
- Internet access during the image build (tooling and wordlists are pulled from upstream sources).

## Building the Image

Clone the repository and build the Docker image. You can optionally pin a specific Go version during build with `--build-arg GO_VERSION=1.22.5`.

```bash
# From the repository root
docker build -t watchmysix .

# Build with a custom Go version (optional)
docker build -t watchmysix --build-arg GO_VERSION=1.21.10 .
```

## Running the Toolkit

Launch an interactive container session so you can execute the bundled reconnaissance tools immediately.

```bash
docker run -it --rm \
  -v "$(pwd)":/work \
  watchmysix
```

Inside the container you will land in `/work`. From there you can run any of the preinstalled binaries, e.g.

```bash
# Fetch subdomains for example.com
subfinder -d example.com -o example-subdomains.txt

# Bruteforce subdomains using puredns with the curated resolvers list
puredns bruteforce /opt/watchmysix/wordlists/static-dns/best-dns-wordlist.txt example.com \
  -r /opt/watchmysix/resolvers/resolvers.txt
```

Sourcegraph lookups are orchestrated within the backend service using the `src` CLI, so you no longer need interactive shell helpers to collect matches. crt.sh collection is also handled programmatically; however, the CLI tools installed in the container remain available if you prefer to run ad-hoc commands manually.

## Updating Tools

The container uses `pdtm` to install many of the ProjectDiscovery tools. To refresh them within an already built container, run:

```bash
pdtm -update-all
```

For Go-based tools installed with `go install`, rebuild the image to ensure you get the latest versions.

## Troubleshooting

- **Missing tools:** Some upstream installations are best-effort. Review the build logs for any warnings (e.g., network interruptions) and rebuild if necessary.
- **Rate limiting / network errors:** Tools like `crtsh` and Sourcegraph queries depend on external services. If you experience rate limits, try again later or configure authentication tokens where supported.
- **Wordlist updates:** Replace the files inside `/opt/watchmysix/wordlists` with your own if you need customized lists.

## Running the Full Stack with Docker Compose

If you want the frontend and backend to run together without starting each service manually, use Docker Compose. The provided configuration builds both applications and links them so the frontend automatically points to the backend API.

```bash
docker compose up --build
```

- The backend API is available at [http://localhost:8000](http://localhost:8000).
- The Vite development server for the frontend is available at [http://localhost:5173](http://localhost:5173).
- Application data produced by the backend is stored in a Docker volume named `watchmysix_backend-data`.

To stop the stack, press `Ctrl+C` or run `docker compose down`. Re-run `docker compose up --build` whenever you need
to rebuild images after changing dependencies. You can inspect logs with `docker compose logs -f backend` or
`docker compose logs -f frontend`.

## Running the Backend API

The backend service powers workflows such as Sourcegraph and crt.sh lookups. To run it locally:

```bash
cd backend
poetry install
poetry run python -m app
```

By default the FastAPI application binds to `0.0.0.0:8000`. You can customize behavior with environment variables exposed via `AppSettings`, including:

- `WATCHMYSIX_DATA_DIR` — root directory where job artifacts and archives are written.
- `WATCHMYSIX_MAX_CONCURRENCY` — number of concurrent jobs the worker pool will process.
- `WATCHMYSIX_SOURCEGRAPH_TOKEN`, `WATCHMYSIX_CRTSH_API_KEY`, and other provider-specific keys — supply them through a `.env` file or shell environment.

Once running, the service exposes REST endpoints such as `/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/logs`, `/jobs/{job_id}/artifacts`, and `/jobs/{job_id}/archive`, plus the WebSocket endpoint `/ws/jobs/{job_id}/logs` for streaming log output.

## Running the Frontend UI

The React frontend consumes the backend API to orchestrate jobs and display results. Start it with:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server listens on `http://localhost:5173` by default. Point the UI to your backend by setting `VITE_API_BASE_URL` via an `.env` file or shell export before running `npm run dev`. The interface expects the backend endpoints listed above, including the `/jobs` REST routes and the `ws/jobs/.../logs` WebSocket.

To produce an optimized build for deployment, run `npm run build`. Bundled assets will be output to `frontend/dist`.

## License

This repository currently does not include an explicit license. Add one if you plan to distribute modified versions.
