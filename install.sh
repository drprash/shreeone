#!/usr/bin/env bash
# =============================================================================
# ShreeOne — Automated Installation Script
# =============================================================================
set -euo pipefail

# ── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }
bold()    { echo -e "${BOLD}$*${RESET}"; }

# ── helpers ───────────────────────────────────────────────────────────────────
confirm() {
    # confirm "Question?" [default Y|N]  → returns 0 (yes) or 1 (no)
    local prompt="$1"
    local default="${2:-Y}"
    local choices
    [[ "$default" == "Y" ]] && choices="[Y/n]" || choices="[y/N]"
    read -r -p "$(echo -e "${BOLD}${prompt}${RESET} ${choices} ")" answer
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy]$ ]]
}

# Generate a random hex string of given byte-length (defaults to 32 → 64 hex chars)
gen_secret() {
    local bytes="${1:-32}"
    if command -v openssl &>/dev/null; then
        openssl rand -hex "$bytes"
    else
        # fallback: /dev/urandom  (|| true absorbs SIGPIPE from head closing the pipe)
        tr -dc 'a-f0-9' < /dev/urandom | head -c $(( bytes * 2 )) || true
    fi
}

# Detect the primary LAN IP (non-loopback)
detect_lan_ip() {
    # Try hostname -I first (Linux), then ip route, then ifconfig
    if command -v hostname &>/dev/null && hostname -I &>/dev/null 2>&1; then
        echo "$(hostname -I | awk '{print $1}')"
    elif command -v ip &>/dev/null; then
        ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}'
    elif command -v ifconfig &>/dev/null; then
        ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -1
    fi
}

# Prompt for a value with an optional default shown in brackets
ask() {
    local prompt="$1"
    local default="${2:-}"
    local secret="${3:-false}"   # if "true", hide input
    local value

    if [[ -n "$default" ]]; then
        local display_default="$default"
        [[ "$secret" == "true" ]] && display_default="****"
        prompt="${prompt} [${display_default}]"
    fi

    if [[ "$secret" == "true" ]]; then
        read -r -s -p "$(echo -e "${BOLD}${prompt}:${RESET} ")" value
        echo  # newline after silent input
    else
        read -r -p "$(echo -e "${BOLD}${prompt}:${RESET} ")" value
    fi

    echo "${value:-$default}"
}

# ── banner ────────────────────────────────────────────────────────────────────
echo ""
bold "============================================================"
bold "          ShreeOne — Family Finance  ·  Installer"
bold "============================================================"
echo ""
info "This script will:"
echo "  1. Check / install Docker and Docker Compose"
echo "  2. Configure environment variables"
echo "  3. Build and start all services"
echo ""
confirm "Continue?" Y || { echo "Aborted."; exit 0; }
echo ""

# ── 1. Dependency checks / installs ──────────────────────────────────────────
bold "── Step 1: Dependencies ─────────────────────────────────────"

check_or_install_docker() {
    if command -v docker &>/dev/null; then
        local ver
        ver=$(docker --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        success "Docker ${ver} is already installed."
        return
    fi

    warn "Docker is not installed."
    if ! confirm "Install Docker automatically (requires sudo)?" Y; then
        die "Docker is required. Install it from https://docs.docker.com/get-docker/ and re-run this script."
    fi

    local os
    os=$(uname -s)
    case "$os" in
        Linux)
            if [[ -f /etc/os-release ]]; then
                # shellcheck source=/dev/null
                source /etc/os-release
                case "${ID:-}" in
                    ubuntu|debian)
                        info "Installing Docker via apt..."
                        sudo apt-get update -qq
                        sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release
                        sudo install -m 0755 -d /etc/apt/keyrings
                        curl -fsSL https://download.docker.com/linux/${ID}/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                        sudo chmod a+r /etc/apt/keyrings/docker.gpg
                        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/${ID} $(lsb_release -cs) stable" | \
                            sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
                        sudo apt-get update -qq
                        sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
                        sudo systemctl enable --now docker
                        sudo usermod -aG docker "$USER"
                        success "Docker installed. You may need to log out and back in for group membership to take effect."
                        ;;
                    fedora|rhel|centos|rocky|almalinux)
                        info "Installing Docker via dnf/yum..."
                        sudo dnf -y install dnf-plugins-core 2>/dev/null || sudo yum -y install yum-utils
                        sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo 2>/dev/null || \
                            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
                        sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>/dev/null || \
                            sudo yum -y install docker-ce docker-ce-cli containerd.io
                        sudo systemctl enable --now docker
                        sudo usermod -aG docker "$USER"
                        success "Docker installed."
                        ;;
                    arch|manjaro)
                        info "Installing Docker via pacman..."
                        sudo pacman -Sy --noconfirm docker docker-compose
                        sudo systemctl enable --now docker
                        sudo usermod -aG docker "$USER"
                        success "Docker installed."
                        ;;
                    *)
                        die "Unsupported distro '${ID}'. Install Docker manually: https://docs.docker.com/get-docker/"
                        ;;
                esac
            else
                die "Cannot detect Linux distro. Install Docker manually: https://docs.docker.com/get-docker/"
            fi
            ;;
        Darwin)
            die "On macOS, install Docker Desktop from https://docs.docker.com/desktop/mac/ and re-run this script."
            ;;
        *)
            die "Unsupported OS '${os}'. Install Docker manually: https://docs.docker.com/get-docker/"
            ;;
    esac
}

check_or_install_docker

# Verify Docker Compose (v2 plugin or standalone)
if docker compose version &>/dev/null 2>&1; then
    success "Docker Compose v2 (plugin) is available."
elif command -v docker-compose &>/dev/null; then
    # Standalone v1 — still works but warn
    warn "docker-compose v1 detected. Preferring it. Consider upgrading to Docker Compose v2."
    COMPOSE_CMD="docker-compose"
else
    warn "Docker Compose not found."
    if confirm "Install Docker Compose plugin automatically (requires sudo)?" Y; then
        os=$(uname -s)
        if [[ "$os" == "Linux" ]]; then
            sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || \
                sudo dnf -y install docker-compose-plugin 2>/dev/null || \
                die "Could not install Docker Compose automatically. Install from https://docs.docker.com/compose/install/"
            success "Docker Compose installed."
        else
            die "Install Docker Compose from https://docs.docker.com/compose/install/ and re-run."
        fi
    else
        die "Docker Compose is required."
    fi
fi

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

echo ""

# ── 2. Environment configuration ─────────────────────────────────────────────
bold "── Step 2: Environment Configuration ───────────────────────"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

if [[ ! -f "$ENV_EXAMPLE" ]]; then
    die ".env.example not found in ${SCRIPT_DIR}. Is this the ShreeOne project directory?"
fi

if [[ -f "$ENV_FILE" ]]; then
    warn ".env file already exists."
    if ! confirm "Overwrite it with new configuration?" N; then
        info "Keeping existing .env. Skipping configuration step."
        SKIP_ENV=true
    else
        SKIP_ENV=false
    fi
else
    SKIP_ENV=false
fi

if [[ "$SKIP_ENV" == "false" ]]; then

    echo ""
    info "Configure environment variables."
    info "Press Enter to accept the [default] value shown in brackets."
    echo ""

    # ── DB_PASSWORD ──
    bold "  DB_PASSWORD — PostgreSQL database password"
    if confirm "  Auto-generate a strong password?" Y; then
        DB_PASSWORD=$(gen_secret 16)
        success "  Auto-generated DB_PASSWORD."
    else
        while true; do
            DB_PASSWORD=$(ask "  Enter DB_PASSWORD" "" "true")
            [[ ${#DB_PASSWORD} -ge 8 ]] && break
            warn "  Password must be at least 8 characters. Try again."
        done
    fi
    echo ""

    # ── SECRET_KEY ──
    bold "  SECRET_KEY — JWT signing secret (min 32 chars)"
    if confirm "  Auto-generate a cryptographically secure key?" Y; then
        SECRET_KEY=$(gen_secret 32)
        success "  Auto-generated SECRET_KEY."
    else
        while true; do
            SECRET_KEY=$(ask "  Enter SECRET_KEY" "" "true")
            [[ ${#SECRET_KEY} -ge 32 ]] && break
            warn "  SECRET_KEY must be at least 32 characters. Try again."
        done
    fi
    echo ""

    # ── FRONTEND_URL ──
    bold "  FRONTEND_URL — Base URL the browser uses to reach the app"
    LAN_IP=$(detect_lan_ip)
    DEFAULT_URL="http://localhost:5173"
    if [[ -n "$LAN_IP" ]]; then
        info "  Detected LAN IP: ${LAN_IP}"
        echo "  Options:"
        echo "    1) localhost only  →  http://localhost:5173  (default)"
        echo "    2) LAN access      →  http://${LAN_IP}:5173  (access from phones / other devices)"
        echo "    3) Custom URL      →  enter your own"
        read -r -p "$(echo -e "${BOLD}  Choose [1/2/3]:${RESET} ")" url_choice
        case "${url_choice:-1}" in
            2) FRONTEND_URL="http://${LAN_IP}:5173" ;;
            3) FRONTEND_URL=$(ask "  Enter custom FRONTEND_URL" "$DEFAULT_URL") ;;
            *) FRONTEND_URL="$DEFAULT_URL" ;;
        esac
    else
        FRONTEND_URL=$(ask "  Enter FRONTEND_URL" "$DEFAULT_URL")
    fi
    echo ""

    # ── Optional vars ──
    bold "  Optional settings (press Enter to keep defaults)"
    DB_HOST=$(ask "  DB_HOST" "db")
    DB_PORT=$(ask "  DB_PORT" "5432")
    DB_NAME=$(ask "  DB_NAME" "shreeone")
    DB_USER=$(ask "  DB_USER" "postgres")
    ACCESS_TOKEN_EXPIRE_MINUTES=$(ask "  ACCESS_TOKEN_EXPIRE_MINUTES" "30")
    REFRESH_TOKEN_EXPIRE_DAYS=$(ask "  REFRESH_TOKEN_EXPIRE_DAYS" "7")
    echo ""

    # ── Write .env ──
    cat > "$ENV_FILE" <<EOF
# Generated by install.sh on $(date -u '+%Y-%m-%dT%H:%M:%SZ')
# Do NOT commit this file to version control.

DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}

SECRET_KEY=${SECRET_KEY}

FRONTEND_URL=${FRONTEND_URL}
ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}
REFRESH_TOKEN_EXPIRE_DAYS=${REFRESH_TOKEN_EXPIRE_DAYS}
EOF

    success ".env written to ${ENV_FILE}"
fi
echo ""

# ── 3. Build and start ────────────────────────────────────────────────────────
bold "── Step 3: Build & Start Services ──────────────────────────"

cd "$SCRIPT_DIR"

info "Running: ${COMPOSE_CMD} up -d --build"
echo ""
$COMPOSE_CMD up -d --build
echo ""

# ── 4. Health check ───────────────────────────────────────────────────────────
bold "── Step 4: Health Check ─────────────────────────────────────"

HEALTH_URL="http://localhost:5173/api/health"
MAX_WAIT=90
INTERVAL=5
elapsed=0

info "Waiting for the API to become healthy (up to ${MAX_WAIT}s)..."
until curl -fsS "$HEALTH_URL" &>/dev/null; do
    if (( elapsed >= MAX_WAIT )); then
        warn "Health check timed out after ${MAX_WAIT}s."
        warn "Services may still be starting. Check logs with:"
        echo "    ${COMPOSE_CMD} logs -f"
        break
    fi
    echo -n "."
    sleep "$INTERVAL"
    elapsed=$(( elapsed + INTERVAL ))
done

if curl -fsS "$HEALTH_URL" &>/dev/null; then
    echo ""
    success "API is healthy!"
fi

# ── 5. Done ───────────────────────────────────────────────────────────────────
echo ""
bold "============================================================"
bold "  ShreeOne is up and running!"
bold "============================================================"
echo ""

# Read FRONTEND_URL from .env for display (covers the case where we skipped config)
DISPLAY_URL=$(grep '^FRONTEND_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "http://localhost:5173")

echo -e "  ${GREEN}App URL:${RESET}        ${BOLD}${DISPLAY_URL}${RESET}"
echo -e "  ${GREEN}API health:${RESET}     ${BOLD}${DISPLAY_URL}/api/health${RESET}"
echo ""
echo "  Useful commands:"
echo "    ${COMPOSE_CMD} logs -f          # stream logs from all services"
echo "    ${COMPOSE_CMD} ps               # check service status"
echo "    ${COMPOSE_CMD} down             # stop all services"
echo "    bash scripts/backup.sh         # manual database backup"
echo ""
info "Register the first admin account by opening the app URL in your browser."
echo ""
