# WatchMySix

WatchMySix is a containerized toolkit tailored for subdomain enumeration and recon workflows. The image bundles ProjectDiscovery's reconnaissance utilities (via `pdtm`), additional Go-based helpers, DNS wordlists, and handy bash helper functions so that you can jump directly into asset discovery without manually stitching the tooling together.

## Features

- Preinstalled ProjectDiscovery CLI tools through `pdtm` (e.g., `subfinder`, `httpx`, `katana`).
- Extra reconnaissance tools such as `puredns`, `amass`, `gotator`, `gospider`, `anew`, and more.
- Curated DNS wordlists and resolver lists placed under `/opt/watchmysix` inside the container.
- Convenience bash functions (`source_scan`, `crtsh`) automatically loaded for quick searches against Sourcegraph and crt.sh.

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
