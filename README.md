# WatchMySix

WatchMySix is a containerized toolkit tailored for subdomain enumeration and recon workflows. The image bundles ProjectDiscovery's reconnaissance utilities (via `pdtm`), additional Go-based helpers, DNS wordlists, and handy bash helper functions so that you can jump directly into asset discovery without manually stitching the tooling together. The container now also ships with a lightweight FastAPI backend and static frontend so you can interact with the toolkit through a browser as soon as the container starts.

## Features

- Preinstalled ProjectDiscovery CLI tools through `pdtm` (e.g., `subfinder`, `httpx`, `katana`).
- Extra reconnaissance tools such as `puredns`, `amass`, `gotator`, `gospider`, `anew`, and more.
- Curated DNS wordlists and resolver lists placed under `/opt/watchmysix` inside the container.
- Convenience bash functions (`source_scan`, `crtsh`) automatically loaded for quick searches against Sourcegraph and crt.sh.
- FastAPI backend that exposes selected toolkit metadata and runs environment checks/migrations on boot.
- Static frontend dashboard (built from the `frontend/` directory) that is served directly from the container alongside the API.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) 24.0+ (or any modern version capable of building images from Dockerfiles).
- Internet access during the image build (tooling and wordlists are pulled from upstream sources).

## Building the Image

Clone the repository and build the Docker image. You can optionally pin a specific Go version during build with `--build-arg GO_VERSION=1.22.5`.

During the build the `frontend/` project is compiled to static assets and the `backend/` project is installed inside a Python virtual environment. The Go-based tooling, wordlists, and resolver files remain part of the final runtime image.

```bash
# From the repository root
docker build -t watchmysix .

# Build with a custom Go version (optional)
docker build -t watchmysix --build-arg GO_VERSION=1.21.10 .
```

## Running the Toolkit

Launch the container and automatically start both the FastAPI backend (port `8000` inside the container) and the static frontend dashboard (served by NGINX on port `80`). The helper scripts apply migrations and validate tool availability before the services boot.

```bash
docker run --rm -p 8080:80 \
  -v "$(pwd)":/work \
  watchmysix
```

Once the container reports that startup checks are complete you can visit <http://localhost:8080> to load the dashboard. The UI proxies API requests to the backend at `/api/*`; the automatic proxy exposes the FastAPI docs at `/docs`.

If you prefer a shell inside the running container you can attach to it:

```bash
docker exec -it <container-id> /bin/bash
```

The backend continues to have access to the original reconnaissance binaries and datasets via `/opt/watchmysix`.

Inside the container you can still run any of the preinstalled binaries from `/work`, e.g.

```bash
# Fetch subdomains for example.com
subfinder -d example.com -o example-subdomains.txt

# Bruteforce subdomains using puredns with the curated resolvers list
puredns bruteforce /opt/watchmysix/wordlists/static-dns/best-dns-wordlist.txt example.com \
  -r /opt/watchmysix/resolvers/resolvers.txt
```

The helper functions added to `/etc/bash.bashrc` are ready to use:

```bash
# Search Sourcegraph for potential subdomains
source_scan example.com

# Query crt.sh for historical certificates
crtsh example.com
```

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

## License

This repository currently does not include an explicit license. Add one if you plan to distribute modified versions.
