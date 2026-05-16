"""Node speed test: TCP handshake latency scoring for all fetched proxy nodes.

Reads public/sub_raw.txt, parses host:port from each proxy link, performs
concurrent TCP connect latency tests, and outputs nodes_status.json for the
dashboard. Optionally sends alert notification via Bark/ServerChan webhook
when alive rate drops below threshold.
"""

import concurrent.futures
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
RAW_FILE = PUBLIC / "sub_raw.txt"
STATUS_FILE = PUBLIC / "nodes_status.json"
CF_CSV_FILE = PUBLIC / "cf_ip_result.csv"

TIMEOUT = 2.5  # TCP connect timeout in seconds
MAX_WORKERS = 50  # Concurrent workers

NOTIFY_URL = os.getenv("NOTIFY_URL", "")
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", "30"))  # percentage

URL_RE = re.compile(r"^(\w+)://(.*)")
HOST_PORT_RE = re.compile(r"@([\w.-]+|\[[\w:]+\]):(\d+)")


def parse_host_port(link: str) -> tuple[str, int] | None:
    """Extract host and port from a proxy link."""
    m = HOST_PORT_RE.search(link)
    if not m:
        return None
    host = m.group(1).strip("[]")
    try:
        port = int(m.group(2))
    except ValueError:
        return None
    return host, port


def tcp_latency(host: str, port: int, timeout: float = TIMEOUT) -> float | None:
    """Measure TCP connect latency in ms. Returns None on failure."""
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return None


def parse_country(link: str) -> str | None:
    """Quick country extraction from node name fragment."""
    if "#" not in link:
        return None
    fragment = link.rsplit("#", 1)[-1]
    # Extract two-letter codes like JP, US, SG etc.
    m = re.search(r"(?:^|[|_\s])([A-Z]{2})(?:[|_\s]|$)", fragment.upper())
    if m:
        return m.group(1)
    return None


def send_notification(alive: int, total: int, rate: float) -> None:
    """Send alert via Bark or ServerChan webhook."""
    if not NOTIFY_URL:
        return
    msg = f"⚠️ 节点存活率告警\n存活: {alive}/{total} ({rate:.1f}%)\n阈值: {ALERT_THRESHOLD}%\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    try:
        data = json.dumps({"title": "节点告警", "body": msg}).encode("utf-8")
        req = urllib.request.Request(NOTIFY_URL, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        print(f"notification sent: alive_rate={rate:.1f}%")
    except Exception as e:
        print(f"notification failed: {e}")


def load_cf_ips() -> list[dict]:
    """Load Cloudflare preferred IPs from CSV if available."""
    if not CF_CSV_FILE.exists():
        return []
    ips = []
    for line in CF_CSV_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0].strip():
            ips.append({
                "ip": parts[0].strip(),
                "port": parts[1].strip() if len(parts) > 1 else "443",
                "speed": float(parts[-1].strip()) if len(parts) > 2 and parts[-1].strip().replace(".", "").isdigit() else 0,
            })
    return ips


def main() -> None:
    if not RAW_FILE.exists():
        print(f"error: {RAW_FILE} not found")
        return

    links = [l for l in RAW_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"loaded {len(links)} links")

    # Parse hosts — deduplicate by host:port to avoid testing same endpoint
    seen = set()
    targets: list[tuple[str, int, str]] = []  # (host, port, link)
    for link in links:
        hp = parse_host_port(link)
        if not hp:
            continue
        host, port = hp
        key = f"{host}:{port}"
        if key not in seen:
            seen.add(key)
            targets.append((host, port, link))

    print(f"testing {len(targets)} unique endpoints...")

    # Concurrent TCP latency testing
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(tcp_latency, h, p): (h, p) for h, p, _ in targets}
        for future in concurrent.futures.as_completed(futures):
            host, port = futures[future]
            key = f"{host}:{port}"
            try:
                latency = future.result()
                results[key] = latency
            except Exception:
                results[key] = None

    # Build scored node list
    nodes = []
    for host, port, link in targets:
        key = f"{host}:{port}"
        latency = results.get(key)
        alive = latency is not None
        nodes.append({
            "link": link,
            "host": host,
            "port": port,
            "alive": alive,
            "latency_ms": round(latency, 2) if latency else None,
            "country": parse_country(link),
            "protocol": link.split("://", 1)[0] if "://" in link else "unknown",
        })

    nodes.sort(key=lambda x: (not x["alive"], x["latency_ms"] or 9999))

    alive_count = sum(1 for n in nodes if n["alive"])
    alive_rate = (alive_count / len(nodes) * 100) if nodes else 0

    # Load CF preferred IPs
    cf_ips = load_cf_ips()

    status = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(nodes),
        "alive": alive_count,
        "alive_rate": round(alive_rate, 1),
        "avg_latency_ms": round(
            sum(n["latency_ms"] for n in nodes if n["alive"] and n["latency_ms"]) / max(alive_count, 1), 2
        ),
        "cf_ips_count": len(cf_ips),
        "nodes": nodes,
    }

    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: alive={alive_count}/{len(nodes)} rate={alive_rate:.1f}% avg_latency={status['avg_latency_ms']}ms")

    # Alert if below threshold
    if NOTIFY_URL and alive_rate < ALERT_THRESHOLD:
        send_notification(alive_count, len(nodes), alive_rate)


if __name__ == "__main__":
    main()
