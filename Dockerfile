# WatchMySix — Subdomain Toolchain (isolated)
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
# اگر نسخه‌ی Go ست نشه، از این استفاده می‌کنیم (قابل تغییر با --build-arg)
ARG GO_VERSION=1.22.5

SHELL ["/bin/bash","-lc"]

# 1) Basic libs & CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git jq make bash build-essential unzip \
    python3 python3-venv pipx postgresql-client \
  && rm -rf /var/lib/apt/lists/*

# PATHs
ENV PIPX_BIN_DIR=/root/.local/bin
ENV GOPATH=/root/go
ENV GOBIN=/usr/local/bin
ENV PATH=/usr/local/go/bin:/root/go/bin:${PIPX_BIN_DIR}:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# 2) Check/Install Go (detect arch; version configurable)
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

# 3) pdtm (ProjectDiscovery Tool Manager)
RUN go install -v github.com/projectdiscovery/pdtm/cmd/pdtm@latest && pdtm -version

# 4) ProjectDiscovery tools via pdtm (هرکدام مستقل نصب شود، خطا باعث توقف نشود)
RUN set -eux; \
  for t in alterx chaos-client dnsx httpx katana naabu shuffledns subfinder urlfinder; do \
    echo ">>> Installing $t via pdtm"; pdtm -install "$t" || echo "WARN: $t not installed via pdtm"; \
  done

# 5) Manual Go-based tools
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

# 6) Sourcegraph src-cli (binary)
RUN curl -fsSL https://sourcegraph.com/.api/src-cli/src_linux_amd64 -o /usr/local/bin/src \
 && chmod +x /usr/local/bin/src

# 7) waymore via pipx
RUN pipx install git+https://github.com/xnl-h4ck3r/waymore.git

# 8) Bash helper functions (source_scan, crtsh)
RUN cat <<'INNER_EOF' >> /etc/bash.bashrc
# ---- WatchMySix helper functions ----
source_scan(){
    DOMAIN=$1
    q=$(echo "$DOMAIN" | sed -e 's/\./\\\./g')
    src search -json "([a-z\-]+)?:?(\/\/)?([a-zA-Z0-9]+[.])+(${q}) count:5000 fork:yes archived:yes" \
      | jq -r '.Results[] | .lineMatches[].preview, .file.path' \
      | grep -oiE "([a-zA-Z0-9]+[.])+(${q})" \
      | awk '{ print tolower($0) }' \
      | sort -u
}

crtsh(){
    query=$(cat <<-END
        SELECT
            ci.NAME_VALUE
        FROM
            certificate_and_identities ci
        WHERE
            plainto_tsquery('certwatch', '$1') @@ identities(ci.CERTIFICATE)
END
)
    echo "$query" | psql -t -h crt.sh -p 5432 -U guest certwatch \
      | sed 's/ //g' | egrep ".*.\.$1" | sed 's/*\.//g' \
      | tr '[:upper:]' '[:lower:]' | sort -u
}
# -------------------------------------
INNER_EOF

# 9) Smoke check (presence only; اخطار می‌دهد ولی build را نمی‌خواباند)
RUN set -eux; \
  for bin in subfinder dnsx httpx katana naabu shuffledns alterx puredns gotator gospider anew unfurl waybackurls gau amass github-subdomains gitlab-subdomains src; do \
    command -v "$bin" >/dev/null 2>&1 || echo "WARN: $bin missing"; \
  done

WORKDIR /work
ENTRYPOINT ["/bin/bash"]
