#!/bin/bash
set -e

DEFAULT_PORT=5050

# ── helpers ──────────────────────────────────────────────────────────────────
check_docker() {
  if ! command -v docker &>/dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
  fi
  if ! docker info &>/dev/null; then
    echo "Error: Docker daemon is not running. Please start Docker first."
    exit 1
  fi
}

port_in_use() {
  lsof -ti:"$1" &>/dev/null || ss -tlnp 2>/dev/null | grep -q ":$1 "
}

# ── main menu ─────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════╗"
echo "║        Claude Stats Runner       ║"
echo "╚══════════════════════════════════╝"
echo ""
echo "  1) Start (default port $DEFAULT_PORT)"
echo "  2) Start on custom port"
echo "  3) Stop"
echo "  4) Rebuild & Start"
echo "  5) Exit"
echo ""
read -rp "Choose an option [1-5, default 1]: " choice
choice="${choice:-1}"

case "$choice" in
  1|2)
    check_docker

    if [ "$choice" = "2" ]; then
      read -rp "Enter port number [$DEFAULT_PORT]: " PORT
      PORT="${PORT:-$DEFAULT_PORT}"
      # Validate numeric
      if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
        echo "Error: Invalid port number."
        exit 1
      fi
    else
      PORT=$DEFAULT_PORT
    fi

    if port_in_use "$PORT"; then
      echo "Warning: Port $PORT is already in use by:"
      lsof -i:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2 || ss -tlnp | grep ":$PORT "
      echo ""
      read -rp "Kill the existing process and continue? [y/N]: " yn
      [[ "$yn" =~ ^[Yy]$ ]] || exit 0
      lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
    fi

    BUILD_FLAG=""
    if ! docker image inspect claude-stats-claude-stats &>/dev/null; then
      echo "No image found — building for the first time..."
      BUILD_FLAG="--build"
    fi

    echo ""
    echo "Starting Claude Stats on http://localhost:$PORT ..."
    PORT=$PORT docker compose -f "$(dirname "$0")/docker-compose.yml" up $BUILD_FLAG -d

    echo ""
    echo "✓ Running at http://localhost:$PORT"
    echo "  To stop: ./run.sh  (choose option 3)"
    ;;

  3)
    check_docker
    echo "Stopping Claude Stats..."
    docker compose -f "$(dirname "$0")/docker-compose.yml" down
    echo "✓ Stopped."
    ;;

  4)
    check_docker

    read -rp "Enter port number [$DEFAULT_PORT]: " PORT
    PORT="${PORT:-$DEFAULT_PORT}"

    echo "Rebuilding and starting on http://localhost:$PORT ..."
    PORT=$PORT docker compose -f "$(dirname "$0")/docker-compose.yml" up --build -d

    echo ""
    echo "✓ Running at http://localhost:$PORT"
    ;;

  5)
    exit 0
    ;;

  *)
    echo "Invalid option."
    exit 1
    ;;
esac
