#!/usr/bin/env bash
set -Eeuo pipefail

require_internet=0
failures=0

usage() {
  cat <<'EOF'
Usage: verify-pi.sh [--require-internet]

Checks Raspberry Pi Wi-Fi, local network, Internet reachability, the Rosy
runtime, API, and dashboard. Internet failure is a warning unless
--require-internet is supplied.
EOF
}

while (($# > 0)); do
  case "$1" in
    --require-internet)
      require_internet=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

pass() {
  printf 'PASS  %-10s %s\n' "$1" "$2"
}

warn() {
  printf 'WARN  %-10s %s\n' "$1" "$2"
}

fail() {
  printf 'FAIL  %-10s %s\n' "$1" "$2"
  failures=$((failures + 1))
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

wifi_connection=""
wlan_ipv4=""

if ! has_command nmcli; then
  fail "WIFI" "nmcli is unavailable; NetworkManager is required"
elif [[ "$(nmcli radio wifi 2>/dev/null || true)" != "enabled" ]]; then
  fail "WIFI" "Wi-Fi radio is disabled"
else
  wifi_connection="$(nmcli -t -f GENERAL.CONNECTION device show wlan0 2>/dev/null | cut -d: -f2- || true)"
  if [[ -z "$wifi_connection" || "$wifi_connection" == "--" ]]; then
    fail "WIFI" "wlan0 is not associated with a Wi-Fi connection"
  else
    pass "WIFI" "wlan0 connection: $wifi_connection"
  fi
fi

if ! has_command ip; then
  fail "LAN" "iproute2 is unavailable"
else
  wlan_ipv4="$(ip -4 -o addr show dev wlan0 scope global 2>/dev/null | awk 'NR == 1 {split($4, address, "/"); print address[1]}' || true)"
  if [[ -z "$wlan_ipv4" ]]; then
    fail "LAN" "wlan0 has no IPv4 address"
  else
    pass "LAN" "wlan0 IPv4: $wlan_ipv4"
    if ip route show default 2>/dev/null | grep -q '^default '; then
      pass "ROUTE" "default route present"
    elif ((require_internet)); then
      fail "ROUTE" "no default route (--require-internet enabled)"
    else
      warn "ROUTE" "no default route; same-WLAN dashboard may still work"
    fi
  fi
fi

dns_ok=0
if has_command getent && getent ahosts www.raspberrypi.com >/dev/null 2>&1; then
  dns_ok=1
  pass "DNS" "public hostname resolution succeeded"
else
  warn "DNS" "public hostname resolution failed"
fi

internet_ok=0
if has_command curl && curl -fsSIL --max-time 8 https://www.raspberrypi.com/ >/dev/null 2>&1; then
  internet_ok=1
  pass "INTERNET" "outbound HTTPS succeeded"
elif ((require_internet)); then
  fail "INTERNET" "outbound HTTPS failed (--require-internet enabled)"
else
  warn "INTERNET" "outbound HTTPS failed; local dashboard may still work"
fi

install_root="${ROSY_INSTALL_ROOT:-/opt/rosy}"
compose_file="$install_root/deploy/robot/compose.yaml"
env_file="$install_root/deploy/robot/.env"

runtime_ok=1
if ! systemctl is-active --quiet rosy-runtime.service 2>/dev/null; then
  fail "RUNTIME" "rosy-runtime.service is not active"
  runtime_ok=0
elif ! docker compose --env-file "$env_file" -f "$compose_file" ps --status running rosy-core 2>/dev/null | grep -q 'rosy-core'; then
  fail "RUNTIME" "rosy-core container is not running"
  runtime_ok=0
fi
if ((runtime_ok)); then
  pass "RUNTIME" "systemd service and rosy-core container are active"
fi

if has_command curl && curl -fsS --max-time 5 http://127.0.0.1:8080/api/v1 >/dev/null 2>&1; then
  pass "API" "FastAPI root responds locally"
else
  fail "API" "http://127.0.0.1:8080/api/v1 did not respond"
fi

if has_command curl && curl -fsS --max-time 5 http://127.0.0.1:8080/dashboard >/dev/null 2>&1; then
  pass "DASHBOARD" "dashboard responds locally"
else
  fail "DASHBOARD" "http://127.0.0.1:8080/dashboard did not respond"
fi

hostname_short="$(hostname -s 2>/dev/null || hostname)"
echo
echo "Dashboard access (client must be on the same Wi-Fi and peer traffic must be allowed):"
echo "  http://${hostname_short}.local:8080/dashboard"
if [[ -n "$wlan_ipv4" ]]; then
  echo "  http://${wlan_ipv4}:8080/dashboard"
fi

if ((dns_ok == 0 && require_internet)); then
  fail "DNS" "DNS is required for Internet-ready acceptance"
fi

if ((internet_ok == 0)); then
  echo "Internet status does not change same-WLAN dashboard availability."
fi

if ((failures > 0)); then
  echo
  echo "Rosy Pi verification failed: $failures required check(s) failed." >&2
  exit 1
fi

echo
echo "Rosy Pi verification passed."
