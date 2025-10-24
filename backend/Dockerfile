# syntax=docker/dockerfile:1
FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive
ARG GO_VERSION=1.22.5

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VERSION=1.8.3 \
    PIPX_BIN_DIR=/root/.local/bin \
    GOPATH=/root/go \
    GOBIN=/usr/local/bin \
    PATH=/usr/local/go/bin:/root/go/bin:${PIPX_BIN_DIR}:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SHELL ["/bin/bash", "-lc"]

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl wget git jq make bash build-essential unzip \
        python3-venv pipx postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python - --version $POETRY_VERSION \
    && ln -s "$POETRY_HOME/bin/poetry" /usr/local/bin/poetry

# Install Go toolchain (matching root image)
RUN set -eux; \
    if ! command -v go >/dev/null 2>&1; then \
      arch="$(dpkg --print-architecture)"; \
      case "$arch" in \
        amd64) goarch=amd64 ;; \
        arm64) goarch=arm64 ;; \
        *) echo "unsupported arch: $arch"; exit 1 ;; \
      esac; \
      curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${goarch}.tar.gz" -o /tmp/go.tgz; \
      rm -rf /usr/local/go && tar -C /usr/local -xzf /tmp/go.tgz; \
      rm /tmp/go.tgz; \
    fi; \
    go version

# ProjectDiscovery tooling via pdtm
RUN go install -v github.com/projectdiscovery/pdtm/cmd/pdtm@latest && pdtm -version

RUN set -eux; \
  for t in alterx chaos-client dnsx httpx katana naabu shuffledns subfinder urlfinder; do \
    echo ">>> Installing $t via pdtm"; pdtm -install "$t" || echo "WARN: $t not installed via pdtm"; \
  done

# Additional Go tooling
RUN go install github.com/Josue87/gotator@latest \
 && go install github.com/d3mondev/puredns/v2@latest \
 && GO111MODULE=on go install github.com/jaeles-project/gospider@latest \
 && go install -v github.com/tomnomnom/anew@latest \
 && go install github.com/tomnomnom/unfurl@latest \
 && go install github.com/tomnomnom/waybackurls@latest \
 && go install github.com/lc/gau/v2/cmd/gau@latest \
 && CGO_ENABLED=0 go install -v github.com/owasp-amass/amass/v5/cmd/amass@main \
 && go install github.com/gwen001/github-subdomains@latest \
 && go install github.com/gwen001/gitlab-subdomains@latest

# Sourcegraph CLI and Python tooling parity
RUN curl -fsSL https://sourcegraph.com/.api/src-cli/src_linux_amd64 -o /usr/local/bin/src \
 && chmod +x /usr/local/bin/src

RUN pipx install git+https://github.com/xnl-h4ck3r/waymore.git

# DNS wordlists & resolvers (mirror root image layout)
RUN set -eux; \
  mkdir -p /opt/watchmysix/wordlists/static-dns /opt/watchmysix/wordlists/dynamic-dns/subdomains; \
  curl -fsSL https://wordlists-cdn.assetnote.io/data/manual/best-dns-wordlist.txt \
    -o /opt/watchmysix/wordlists/static-dns/best-dns-wordlist.txt; \
  curl -fsSL https://raw.githubusercontent.com/n0kovo/n0kovo_subdomains/main/n0kovo_subdomains_huge.txt \
    -o /opt/watchmysix/wordlists/static-dns/n0kovo_subdomains_huge.txt; \
  curl -fsSL https://raw.githubusercontent.com/infosec-au/altdns/master/words.txt \
    -o /opt/watchmysix/wordlists/dynamic-dns/subdomains/altdns-words.txt; \
  curl -fsSL https://raw.githubusercontent.com/ProjectAnte/dnsgen/master/dnsgen/words.txt \
    -o /opt/watchmysix/wordlists/dynamic-dns/subdomains/dnsgen-words.txt; \
  curl -fsSL https://gist.githubusercontent.com/six2dez/ffc2b14d283e8f8eff6ac83e20a3c4b4/raw \
    -o /opt/watchmysix/wordlists/dynamic-dns/other.txt; \
  cat /opt/watchmysix/wordlists/dynamic-dns/subdomains/altdns-words.txt \
      /opt/watchmysix/wordlists/dynamic-dns/subdomains/dnsgen-words.txt \
      /opt/watchmysix/wordlists/dynamic-dns/other.txt \
    | sort -u > /opt/watchmysix/wordlists/dynamic-dns/words-merged.txt

RUN mkdir -p /opt/watchmysix/resolvers \
  && printf '%s\n' \
    8.8.4.4 \
    129.250.35.251 \
    208.67.222.222 \
  > /opt/watchmysix/resolvers/resolvers.txt

# Presence smoke-check similar to root image
RUN set -eux; \
  for bin in subfinder dnsx httpx katana naabu shuffledns alterx puredns gotator gospider anew unfurl waybackurls gau amass github-subdomains gitlab-subdomains src; do \
    command -v "$bin" >/dev/null 2>&1 || echo "WARN: $bin missing"; \
  done

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
