# Cloudflare + GitHub Auto Subscription Generator

> [中文文档 (Chinese README)](README_CN.md)

Auto-aggregates proxy nodes, tests latency, and serves multi-format subscriptions via GitHub Pages + Cloudflare Worker.

## Features

- **Auto-fetch** free nodes from GitHub sources every 6 hours
- **TCP latency testing** filters slow/dead nodes
- **Multi-format output**: Base64 (V2Ray), Clash Meta YAML, Sing-Box JSON
- **Region-classified**: US, Japan, Singapore, Hong Kong, etc.
- **Web dashboard** (`public/index.html`) — live node status, latency ranking, QR codes
- **Cloudflare Worker gateway** — token auth, preferred IP routing, Web UI for custom subs
- **Hysteria2 protocol** supported alongside vmess/vless/trojan/ss/ssr

## Quick Start

1. Fork this repo
2. Add `SUBSCRIPTION_TOKEN` secret in `Settings → Secrets and variables → Actions`
3. Enable GitHub Pages (`main` branch, `/ (root)`)
4. (Recommended) Point your Cloudflare domain to `<user>.github.io`

### Subscription URL

```
https://sub.yourdomain.com/sub.txt?token=YOUR_SUBSCRIPTION_TOKEN
```

### Health Check

```
https://sub.yourdomain.com/health
```

### Web Dashboard

```
https://sub.yourdomain.com/
```

## Output Files

| File | Format | Description |
|------|--------|-------------|
| `sub.txt` | Base64 | All protocols |
| `sub_v2ray.txt` | Base64 | V2Ray protocols only |
| `sub_hysteria.txt` | Base64 | Hysteria2 only |
| `sub_clash.yaml` | YAML | Clash Meta format |
| `sub_singbox.json` | JSON | Sing-Box format |
| `regions/sub_US.txt` | Base64 | US region nodes |
| `regions/sub_JP.txt` | Base64 | Japan region nodes |

## Compliance

For legal network access and security testing only. Comply with local laws and platform terms. Maintain 3-5 private exit nodes across different ASNs for reliability.

## License

MIT
