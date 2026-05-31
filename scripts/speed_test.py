"""Node speed test: TCP handshake latency scoring for all fetched proxy nodes.

Reads public/sub_raw.txt, parses host:port from each proxy link, performs
concurrent TCP connect latency tests (2-pass verification), outputs
nodes_status.json for the dashboard, and keeps only the top 50 most
reliable alive nodes in the subscription files. Optionally sends alert
notification via Bark/ServerChan webhook when alive rate drops below
threshold.
"""

import base64
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

TOP_N = 50  # Keep top N most reliable alive nodes
PASSES = 2  # Node must pass N consecutive latency tests
TIMEOUT = 2.0  # TCP connect timeout in seconds (per pass)
PASS_DELAY = 1.0  # Seconds to wait between passes
MAX_WORKERS = 50  # Concurrent workers per pass

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


def run_single_pass(targets: list, max_workers: int = MAX_WORKERS) -> dict:
    """Run one pass of TCP latency testing against all targets."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(tcp_latency, h, p, TIMEOUT): (h, p) for h, p, _ in targets}
        for future in concurrent.futures.as_completed(futures):
            host, port = futures[future]
            key = f"{host}:{port}"
            try:
                latency = future.result()
                results[key] = latency
            except Exception:
                results[key] = None
    return results


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

    print(f"testing {len(targets)} unique endpoints (pass 1 of {PASSES})...")

    # ── Pass 1: initial TCP latency test on all targets ──
    results_pass1 = run_single_pass(targets, MAX_WORKERS)

    # Build pass 1 node list
    pass1_alive = 0
    for host, port, link in targets:
        key = f"{host}:{port}"
        latency = results_pass1.get(key)
        alive = latency is not None
        if alive:
            pass1_alive += 1

    print(f"pass 1 done: {pass1_alive}/{len(targets)} alive")

    # ── Pass 2: re-test only alive nodes (verify stability) ──
    pass2_targets = [
        (h, p, link) for h, p, link in targets
        if results_pass1.get(f"{h}:{p}") is not None
    ]

    if PASSES >= 2:
        print(f"pass 2 of {PASSES}: re-testing {len(pass2_targets)} survivors...")
        time.sleep(PASS_DELAY)
        results_pass2 = run_single_pass(pass2_targets, MAX_WORKERS)
    else:
        results_pass2 = {}

    # Combine results: node is alive ONLY if it passed ALL passes
    pass2_alive = 0
    nodes = []
    for host, port, link in pass2_targets:
        key = f"{host}:{port}"
        latency_pass1 = results_pass1.get(key)
        latency_pass2 = results_pass2.get(key)
        # Must pass BOTH rounds
        alive = latency_pass1 is not None and latency_pass2 is not None
        # Use average of both passes for latency score
        avg_latency = None
        if alive:
            avg_latency = (latency_pass1 + latency_pass2) / 2.0
            pass2_alive += 1
        elif latency_pass1 is not None:
            avg_latency = latency_pass1

        nodes.append({
            "link": link,
            "host": host,
            "port": port,
            "alive": alive,
            "latency_ms": round(avg_latency, 2) if avg_latency else None,
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

    # ── Filter top N most reliable alive nodes ──
    alive_nodes = [n for n in nodes if n["alive"]]
    top_nodes = alive_nodes[:TOP_N]
    top_links = [n["link"] for n in top_nodes]
    print(f"keeping top {len(top_links)} nodes (filtered from {len(alive_nodes)} survivors after 2-pass)")

    # Rewrite subscription files with filtered nodes
    rewrite_subscription_files(top_links)


def rewrite_subscription_files(links: list[str]) -> None:
    """Rewrite all subscription output files with the filtered node list."""
    raw_all = "\n".join(links)

    HY2_SCHEMES = {"hysteria2", "hy2", "hysteria"}
    v2ray_links = [x for x in links if x.split("://", 1)[0].lower() not in HY2_SCHEMES]
    hy2_links = [x for x in links if x.split("://", 1)[0].lower() in HY2_SCHEMES]

    raw_v2ray = "\n".join(v2ray_links) if v2ray_links else ""
    raw_hy2 = "\n".join(hy2_links) if hy2_links else ""

    files = {
        PUBLIC / "sub_raw.txt": raw_all,
        PUBLIC / "sub.txt": base64.b64encode(raw_all.encode("utf-8")).decode("utf-8") if raw_all else "",
        PUBLIC / "sub_v2ray_raw.txt": raw_v2ray,
        PUBLIC / "sub_v2ray.txt": base64.b64encode(raw_v2ray.encode("utf-8")).decode("utf-8") if raw_v2ray else "",
        PUBLIC / "sub_hysteria_raw.txt": raw_hy2,
        PUBLIC / "sub_hysteria.txt": base64.b64encode(raw_hy2.encode("utf-8")).decode("utf-8") if raw_hy2 else "",
    }

    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        print(f"rewrote {path.name} ({len(content)} bytes)")

    # Also update region files
    region_dir = PUBLIC / "regions"
    if region_dir.exists():
        regions: dict[str, list[str]] = {}
        for link in links:
            country = None
            if "#" in link:
                fragment = link.rsplit("#", 1)[-1]
                decoded = urllib.parse.unquote(fragment)
                text = fragment + " " + decoded
                m = re.search(r"(?:^|[|_\s])([A-Z]{2})(?:[|_\s]|$)", text.upper())
                if m:
                    country = m.group(1)
            region_key = country or "OTHER"
            regions.setdefault(region_key, []).append(link)

        for code, region_links in regions.items():
            region_raw = "\n".join(region_links)
            region_b64 = base64.b64encode(region_raw.encode("utf-8")).decode("utf-8")
            (region_dir / f"sub_{code}.txt").write_text(region_b64, encoding="utf-8")
            (region_dir / f"sub_{code}_raw.txt").write_text(region_raw, encoding="utf-8")

        # Update regions index
        index_path = PUBLIC / "sub_regions.json"
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            index["total_nodes"] = len(links)
            index["v2ray_nodes"] = len(v2ray_links)
            index["hysteria_nodes"] = len(hy2_links)
            for code in index.get("regions", {}):
                index["regions"][code]["count"] = len(regions.get(code, []))
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"updated regions index ({len(regions)} regions)")

    print(f"top {TOP_N} filter complete: {len(links)} nodes written")


if __name__ == "__main__":
    main()
