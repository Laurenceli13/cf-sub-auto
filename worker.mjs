/**
 * cf-sub-auto Cloudflare Worker — 优选订阅网关
 *
 * Features:
 * - Token-protected subscription proxy (/sub.txt?token=xxx)
 * - Quick subscribe with preferred IPs (/auto, configurable paths)
 * - Web UI for custom subscription generation
 * - Clash / Sing-box format conversion via subconverter
 * - Preferred IP pool from multiple sources (static, API, CSV)
 * - Dynamic UUID rotation (KEY + TIME + UPTIME)
 * - Telegram notification on access
 * - SOCKS5 proxy pool for region-aware assignment
 * - Direct GitHub raw fetch (bypasses GitHub Pages DNS issues)
 * - Health check endpoint (/health)
 */

// ─── Defaults (overridable via env vars) ───────────────────────────
let quickAccessTokens = ['auto'];
let tlsAddresses = [];
let tlsAddressesApi = [];
let noTlsAddresses = [];
let noTlsAddressesApi = [];
let csvSources = [];
let minSpeed = 7;
let csvRemarkCol = 1;
let subConverter = 'SUBAPI.cmliussss.net';
let subConfig = 'https://raw.githubusercontent.com/cmliu/ACL4SSR/main/Clash/config/ACL4SSR_Online_Full_MultiMode.ini';
let subProtocol = 'https';
let noTLS = false;
let fileLabel = '优选订阅生成器';
let proxyIPs = ['proxyip.fxxk.dedyn.io'];
let cmProxyIPs = {};
let socks5Data = [];
let socks5DataUrl = '';
let botToken = '';
let chatID = '';
let endPS = '';
let protocolLabel = 'VLESS';  // default protocol
let subUpdateTime = 6;
let httpsPorts = ['2053', '2083', '2087', '2096', '8443'];
let validDays = 7;
let updateHour = 3;  // Beijing time
let blockedUAs = ['telegram', 'twitter', 'miaoko'];
let fetcherICPC = '萌ICP备-20240707号';
let extraId = '0';
let cipherMethod = 'auto';
let scvDefault = 'false';
let alpnDefault = '';
let siteIcon = '';
let siteAvatar = '';
let siteBackground = '';
let xhttp = '';
let fakeUserID = '';
let fakeHostName = '';

// ─── Helpers ───────────────────────────────────────────────────────

function parseList(text) {
    if (!text) return [];
    return [...new Set(
        text.split(/[,|\n]/).map(s => s.trim()).filter(Boolean)
    )];
}

async function fetchText(url, timeoutMs = 3000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        const r = await fetch(url, {
            headers: { 'User-Agent': `${fileLabel} (https://github.com/Laurenceli13/cf-sub-auto)` },
            signal: ctrl.signal
        });
        return r.ok ? await r.text() : '';
    } catch {
        return '';
    } finally {
        clearTimeout(t);
    }
}

function encodeBase64(str) {
    return btoa(String.fromCharCode(...new TextEncoder().encode(str)));
}

function decodeBase64(str) {
    return new TextDecoder().decode(Uint8Array.from(atob(str), c => c.charCodeAt(0)));
}

function isValidIPv4(ip) {
    return /^(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)\.(25[0-5]|2[0-4]\d|[01]?\d\d?)$/.test(ip);
}

function randomItem(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

// ─── Preferred IP Pool ─────────────────────────────────────────────

async function loadPreferredIPs() {
    let all = [...tlsAddresses];

    // Fetch remote TXT lists
    if (tlsAddressesApi.length) {
        const results = await Promise.allSettled(
            tlsAddressesApi.map(url => fetchText(url, 2000))
        );
        for (const r of results) {
            if (r.status === 'fulfilled' && r.value) {
                all = all.concat(parseList(r.value));
            }
        }
    }

    // Fetch and filter CSV speed test results
    if (csvSources.length) {
        for (const csvUrl of csvSources) {
            const csvText = await fetchText(csvUrl, 5000);
            if (!csvText) continue;
            const lines = csvText.split('\n').filter(l => l.trim());
            if (lines.length < 2) continue;
            const header = lines[0].split(',');
            const speedIdx = header.length - 1;
            // Simple: first col is IP, last col is speed
            for (let i = 1; i < lines.length; i++) {
                const cols = lines[i].split(',');
                const ip = cols[0]?.trim();
                const speed = parseFloat(cols[speedIdx]);
                if (ip && !isNaN(speed) && speed > minSpeed) {
                    const port = cols[1] || '443';
                    const remark = cols[csvRemarkCol + 1] || '';
                    all.push(`${ip}:${port}${remark ? '#' + remark : ''}`);
                    // Collect proxy IPs (non-standard ports)
                    if (csvUrl.includes('proxyip=true') && !httpsPorts.includes(port) && cols[1] === 'TRUE') {
                        proxyIPs.push(`${ip}:${port}`);
                    }
                }
            }
        }
    }

    // Also load noTLS addresses if not forcing noTLS only
    if (!noTLS) {
        all = all.concat(noTlsAddresses);
        if (noTlsAddressesApi.length) {
            const results = await Promise.allSettled(
                noTlsAddressesApi.map(url => fetchText(url, 2000))
            );
            for (const r of results) {
                if (r.status === 'fulfilled' && r.value) {
                    all = all.concat(parseList(r.value));
                }
            }
        }
    }

    // Deduplicate
    all = [...new Set(all.filter(Boolean))];

    // Separate into entries with and without port
    return all.map(entry => {
        const m = entry.match(/^([\w.:[\]]+):?(\d+)?#?(.*)?$/);
        if (!m) return null;
        let ip = m[1], port = m[2], remark = m[3] || '';
        if (!port) port = (noTLS && noTlsAddresses.includes(entry)) ? '80' : '443';
        return { ip, port, remark };
    }).filter(Boolean);
}

// ─── SOCKS5 Proxy Pool ─────────────────────────────────────────────

async function loadSocks5() {
    if (!socks5DataUrl) return;
    try {
        const text = await fetchText(socks5DataUrl, 5000);
        if (text) socks5Data = text.split('\n').filter(l => l.trim());
    } catch {}
}

function getSocks5ByRegion(cc) {
    if (!socks5Data.length) return '';
    const lower = cc?.toLowerCase() || '';
    let filtered = socks5Data.filter(p => p.toLowerCase().endsWith(`#${lower}`));
    if (!filtered.length) filtered = socks5Data.filter(p => p.toLowerCase().endsWith('#us'));
    if (!filtered.length) return randomItem(socks5Data);
    return randomItem(filtered);
}

// ─── Dynamic UUID ──────────────────────────────────────────────────

async function md5Twice(text) {
    const enc = new TextEncoder();
    const h1 = await crypto.subtle.digest('MD5', enc.encode(text));
    const h1hex = [...new Uint8Array(h1)].map(b => b.toString(16).padStart(2, '0')).join('');
    const h2 = await crypto.subtle.digest('MD5', enc.encode(h1hex.slice(7, 27)));
    return [...new Uint8Array(h2)].map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generateDynamicUUIDs(key) {
    const offsetMs = 8 * 60 * 60 * 1000; // UTC+8
    const startDate = new Date(2007, 6, 7, updateHour, 0, 0);
    const weekMs = 1000 * 60 * 60 * 24 * validDays;
    const now = new Date();
    const adjusted = new Date(now.getTime() + offsetMs);
    const weekNum = Math.ceil((adjusted - startDate) / weekMs);

    async function makeUUID(base) {
        const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(base));
        const hex = [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0,8)}-${hex.slice(8,12)}-4${hex.slice(13,16)}-${((parseInt(hex.slice(16,18),16) & 0x3f) | 0x80).toString(16)}${hex.slice(18,20)}-${hex.slice(20,32)}`;
    }

    const endDate = new Date(startDate.getTime() + weekNum * weekMs);
    const expiryUTC = new Date(endDate.getTime() - offsetMs).toISOString().slice(0,19).replace('T',' ');
    const expiryStr = `到期时间(UTC): ${expiryUTC} (UTC+8): ${endDate.toISOString().slice(0,19).replace('T',' ')}`;

    const [currentUUID, previousUUID] = await Promise.all([
        makeUUID(key + weekNum),
        makeUUID(key + (weekNum - 1))
    ]);
    return { currentUUID, previousUUID, expiryStr };
}

// ─── Fake Info ─────────────────────────────────────────────────────

async function generateFakeInfo() {
    const now = new Date();
    const hash = await md5Twice(Math.ceil(now.getTime()).toString());
    fakeUserID = `${hash.slice(0,8)}-${hash.slice(8,12)}-${hash.slice(12,16)}-${hash.slice(16,20)}-${hash.slice(20,32)}`;
    fakeHostName = `${hash.slice(6,9)}.${hash.slice(13,19)}.xyz`;
}

function maskFake(content, userID, hostName) {
    return content.replace(new RegExp(userID, 'g'), fakeUserID).replace(new RegExp(hostName, 'g'), fakeHostName);
}

function unmaskFake(content, userID, hostName) {
    return content.replace(new RegExp(fakeUserID, 'g'), userID).replace(new RegExp(fakeHostName, 'g'), hostName);
}

// ─── Node Link Generation ──────────────────────────────────────────

function buildVlessLink(addr, uuid, host, path, sni, type, scv, alpn, flow) {
    const q = new URLSearchParams();
    q.set('type', type || 'ws');
    q.set('security', 'tls');
    q.set('path', path || '/?ed=2560');
    q.set('host', host);
    q.set('sni', sni || host);
    q.set('fp', 'chrome');
    q.set('encryption', 'none');
    if (alpn) q.set('alpn', alpn);
    if (flow) q.set('flow', flow);
    if (scv === 'true') q.set('allowInsecure', '1');
    const name = encodeURIComponent(addr.remark || addr.ip);
    return `vless://${uuid}@${addr.ip}:${addr.port}?${q.toString()}#${name}`;
}

function buildTrojanLink(addr, password, host, path, sni, type, scv, alpn) {
    const q = new URLSearchParams();
    q.set('type', type || 'ws');
    q.set('security', 'tls');
    q.set('path', path || '/?ed=2560');
    q.set('host', host);
    q.set('sni', sni || host);
    if (alpn) q.set('alpn', alpn);
    if (scv === 'true') q.set('allowInsecure', '1');
    const name = encodeURIComponent(addr.remark || addr.ip);
    return `trojan://${encodeURIComponent(password)}@${addr.ip}:${addr.port}?${q.toString()}#${name}`;
}

// ─── Subscription Generation ───────────────────────────────────────

async function generateSubscription(host, uuid, path, sni, type, scv, alpn, edgeTunnel, useProxyIP, extraParams) {
    const addrs = await loadPreferredIPs();
    if (!addrs.length) return '# 没有可用优选IP，请检查ADD/ADDAPI/ADDCSV配置';

    let links = [];
    const isTrojan = !!extraParams?.password;

    for (const addr of addrs) {
        let link;
        if (isTrojan) {
            link = buildTrojanLink(addr, extraParams.password, host, path, sni, type, scv, alpn);
        } else {
            link = buildVlessLink(addr, uuid, host, path, sni, type, scv, alpn, extraParams?.flow);
        }
        links.push(link);
    }

    // Apply proxy IP for CDN-fronting if enabled
    if (useProxyIP === 'true' && proxyIPs.length) {
        const proxyIP = randomItem(proxyIPs);
        links = links.map(l => l.replace(/(\d+\.\d+\.\d+\.\d+)/, proxyIP.split(':')[0]));
    }

    return btoa(links.join('\n'));
}

// ─── Telegram Notification ─────────────────────────────────────────

async function tgNotify(msg, clientIP, detail) {
    if (!botToken || !chatID) return;
    const text = encodeURIComponent(`#获取订阅 ${fileLabel}\nIP: ${clientIP}\n${detail}`);
    try {
        await fetch(`https://api.telegram.org/bot${botToken}/sendMessage?chat_id=${chatID}&parse_mode=HTML&text=${text}`);
    } catch {}
}

// ─── Subscription Conversion (Clash/Sing-box) ──────────────────────

async function convertFormat(plainB64, format, scv) {
    const subUrl = `https://${new URL(request.url).host}/sub?dummy=1`; // placeholder
    // Encode the plain subscription as a data URL for the converter
    const encodedUrl = encodeURIComponent(`data:text/plain;base64,${plainB64}`);
    const finalScv = scv || scvDefault;

    const targets = {
        clash: `target=clash&insert=false&emoji=true&list=false&tfo=false&scv=${finalScv}&fdn=false&sort=false&new_name=true`,
        singbox: `target=singbox&insert=false&emoji=true&list=false&tfo=false&scv=${finalScv}&fdn=false&sort=false&new_name=true`,
    };

    const query = targets[format] || targets.clash;
    const url = `${subProtocol}://${subConverter}/sub?${query}&url=${encodedUrl}&config=${encodeURIComponent(subConfig)}`;

    try {
        const r = await fetch(url, { headers: { 'User-Agent': `${fileLabel}/1.0` } });
        return r.ok ? await r.text() : `# Converter error: ${r.status}`;
    } catch (e) {
        return `# Converter error: ${e.message}`;
    }
}

// ─── Web UI HTML ───────────────────────────────────────────────────

function renderUI() {
    const bgStyle = siteBackground ? `background-image: url('${siteBackground}'); background-size: cover;` : '';
    const iconTag = siteIcon ? `<link rel="icon" href="${siteIcon}">` : '';
    const avatarTag = siteAvatar ? `<div class="logo"><img src="${siteAvatar}" alt="logo"></div>` : '';

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${fileLabel}</title>
${iconTag}
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
  min-height: 100vh; ${bgStyle}
  background-color: #0f172a; color: #e2e8f0;
  display: flex; flex-direction: column; align-items: center;
}
.container { width: 100%; max-width: 600px; padding: 20px; }
.header { text-align: center; padding: 40px 0 20px; }
.header h1 { font-size: 1.8rem; color: #38bdf8; margin-bottom: 8px; }
.header p { color: #94a3b8; font-size: 0.9rem; }
${avatarTag ? `.logo { margin-bottom: 12px; } .logo img { width: 72px; height: 72px; border-radius: 50%; border: 2px solid #38bdf8; }` : ''}
.card {
  background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 16px;
  border: 1px solid #334155;
}
.card h2 { font-size: 1.1rem; color: #e2e8f0; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.card h2 .dot { width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 0.85rem; color: #94a3b8; margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 10px 12px; border-radius: 8px;
  background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
  font-size: 0.9rem; outline: none; transition: border-color 0.2s;
}
.form-group input:focus, .form-group select:focus { border-color: #38bdf8; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.btn {
  width: 100%; padding: 12px; border: none; border-radius: 8px;
  background: #38bdf8; color: #0f172a; font-size: 1rem; font-weight: 600;
  cursor: pointer; transition: opacity 0.2s;
}
.btn:hover { opacity: 0.9; }
.btn-secondary {
  background: #334155; color: #e2e8f0; margin-top: 8px;
}
.result { margin-top: 16px; }
.result textarea {
  width: 100%; height: 80px; padding: 10px; border-radius: 8px;
  background: #0f172a; border: 1px solid #334155; color: #38bdf8;
  font-size: 0.8rem; resize: vertical; font-family: monospace;
}
.result-actions { display: flex; gap: 8px; margin-top: 8px; }
.result-actions .btn { font-size: 0.85rem; padding: 8px; }
.qrcode-wrapper { text-align: center; margin-top: 16px; }
.qrcode-wrapper canvas { border-radius: 8px; background: #fff; padding: 8px; }
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tab {
  padding: 6px 16px; border-radius: 6px; font-size: 0.85rem;
  cursor: pointer; border: 1px solid #334155; background: transparent; color: #94a3b8;
  transition: all 0.2s;
}
.tab.active { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }
.links-section { margin-top: 20px; padding-top: 16px; border-top: 1px solid #334155; }
.links-section h3 { font-size: 0.9rem; color: #94a3b8; margin-bottom: 10px; }
.link-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
  padding: 8px 12px; background: #0f172a; border-radius: 8px;
}
.link-row code { flex: 1; font-size: 0.8rem; color: #38bdf8; word-break: break-all; }
.link-row .btn { width: auto; font-size: 0.75rem; padding: 4px 12px; }
.footer { text-align: center; padding: 20px; color: #475569; font-size: 0.8rem; }
.footer a { color: #38bdf8; text-decoration: none; }
.toast {
  position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
  background: #22c55e; color: #fff; padding: 10px 24px; border-radius: 8px;
  font-size: 0.9rem; z-index: 1000; opacity: 0; transition: opacity 0.3s;
}
.toast.show { opacity: 1; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    ${avatarTag}
    <h1>🌐 ${fileLabel}</h1>
    <p>跨境电商网络工具箱 · Cloudflare 优选订阅生成</p>
  </div>

  <div class="card">
    <h2><span class="dot"></span>生成专属订阅</h2>
    <div class="tabs">
      <button class="tab active" onclick="switchTab('vless')">VLESS</button>
      <button class="tab" onclick="switchTab('trojan')">Trojan</button>
    </div>
    <form id="subForm" onsubmit="generateSub(event)">
      <div class="form-row">
        <div class="form-group">
          <label>伪装域名 (HOST)</label>
          <input type="text" id="host" placeholder="cdn.example.com" required>
        </div>
        <div class="form-group">
          <label id="authLabel">UUID</label>
          <input type="text" id="uuid" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>WS 路径 (PATH)</label>
          <input type="text" id="path" value="/?ed=2560">
        </div>
        <div class="form-group">
          <label>SNI</label>
          <input type="text" id="sni" placeholder="与HOST相同">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>传输类型</label>
          <select id="type"><option value="ws">WebSocket</option><option value="splithttp">SplitHTTP</option></select>
        </div>
        <div class="form-group">
          <label>跳过证书验证</label>
          <select id="scv"><option value="false">否</option><option value="true">是</option></select>
        </div>
      </div>
      <button type="submit" class="btn">🔗 生成订阅链接</button>
    </form>
    <div class="result" id="result" style="display:none;">
      <textarea id="subLink" readonly></textarea>
      <div class="result-actions">
        <button class="btn" onclick="copyLink()">📋 复制链接</button>
        <button class="btn" onclick="copyBase64()">📋 复制Base64</button>
      </div>
      <div class="qrcode-wrapper" id="qrcode"></div>
    </div>
  </div>

  <div class="card" id="quickLinks">
    <h2><span class="dot"></span>快速订阅入口</h2>
    <div class="links-section">
      <h3>你的专属订阅地址（在客户端中导入）</h3>
      <div class="link-row">
        <code>https://${new URL(request.url).host}/sub.txt?token=你的TOKEN</code>
        <button class="btn" onclick="copyText('https://${new URL(request.url).host}/sub.txt?token=你的TOKEN')">复制</button>
      </div>
      <div class="link-row">
        <code>https://${new URL(request.url).host}/sub.txt?token=TOKEN&format=clash</code>
        <button class="btn" onclick="copyText('https://${new URL(request.url).host}/sub.txt?token=TOKEN&format=clash')">复制</button>
      </div>
      <div class="link-row">
        <code>https://${new URL(request.url).host}/health</code>
        <button class="btn" onclick="copyText('https://${new URL(request.url).host}/health')">复制</button>
      </div>
    </div>
  </div>

  <div class="footer">
    <p>${fetcherICPC} · Powered by <a href="https://github.com/Laurenceli13/cf-sub-auto" target="_blank">cf-sub-auto</a></p>
    <p style="margin-top:4px;">本项目仅用于合法网络访问与安全测试，请遵守当地法律法规</p>
  </div>
</div>

<div class="toast" id="toast"></div>

<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
let currentTab = 'vless';
let currentB64 = '';

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('authLabel').textContent = tab === 'trojan' ? '密码 (Password)' : 'UUID';
  document.getElementById('uuid').placeholder = tab === 'trojan' ? 'your-password' : 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx';
}

async function generateSub(e) {
  e.preventDefault();
  const host = document.getElementById('host').value.trim();
  const uuid = document.getElementById('uuid').value.trim();
  const path = document.getElementById('path').value.trim();
  const sni = document.getElementById('sni').value.trim() || host;
  const type = document.getElementById('type').value;
  const scv = document.getElementById('scv').value;

  const params = new URLSearchParams({ host, path, sni, type, scv });
  if (currentTab === 'trojan') {
    params.set('password', uuid);
  } else {
    params.set('uuid', uuid);
  }

  const url = '/sub?' + params.toString();
  const resp = await fetch(url);
  currentB64 = await resp.text();

  document.getElementById('subLink').value = 'https://' + location.host + url;
  document.getElementById('result').style.display = 'block';
  showQR('https://' + location.host + url);
}

function showQR(text) {
  const qrDiv = document.getElementById('qrcode');
  qrDiv.innerHTML = '';
  new QRCode(qrDiv, { text, width: 180, height: 180, colorDark: '#0f172a', colorLight: '#ffffff' });
}

function copyLink() {
  const ta = document.getElementById('subLink');
  ta.select(); document.execCommand('copy');
  showToast('链接已复制！');
}

function copyBase64() {
  navigator.clipboard.writeText(currentB64).then(() => showToast('Base64 已复制！'));
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => showToast('已复制！'));
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

// Quick access links: fill in the user's domain
document.addEventListener('DOMContentLoaded', () => {
  const host = location.host;
  document.querySelectorAll('.link-row code').forEach(el => {
    el.textContent = el.textContent.replace('你的TOKEN', 'YOUR_TOKEN');
  });
});
</script>
</body>
</html>`;
}

// ─── Main Request Handler ──────────────────────────────────────────

export default {
    async fetch(request, env) {
        // ── Load env vars ──
        if (env.TOKEN) quickAccessTokens = parseList(env.TOKEN);
        botToken = env.TGTOKEN || botToken;
        chatID = env.TGID || chatID;
        if (env.SUBAPI) {
            subConverter = env.SUBAPI.replace(/^https?:\/\//, '');
            subProtocol = env.SUBAPI.startsWith('http://') ? 'http' : 'https';
        }
        subConfig = env.SUBCONFIG || subConfig;
        fileLabel = env.SUBNAME || fileLabel;
        socks5DataUrl = env.SOCKS5DATA || socks5DataUrl;
        if (env.CMPROXYIPS) {
            const pairs = parseList(env.CMPROXYIPS);
            for (const p of pairs) {
                const [region, ip] = p.split('=');
                if (region && ip) cmProxyIPs[region.trim()] = ip.trim();
            }
        }
        if (env.CFPORTS) httpsPorts = parseList(env.CFPORTS);
        endPS = env.PS || endPS;
        siteIcon = env.ICO ? `<link rel="icon" sizes="32x32" href="${env.ICO}">` : '';
        siteAvatar = env.PNG ? env.PNG : '';
        if (env.IMG) siteBackground = randomItem(parseList(env.IMG));
        fetcherICPC = env.BEIAN || fetcherICPC;

        if (env.ADD) tlsAddresses = parseList(env.ADD);
        if (env.ADDAPI) tlsAddressesApi = parseList(env.ADDAPI);
        if (env.ADDNOTLS) noTlsAddresses = parseList(env.ADDNOTLS);
        if (env.ADDNOTLSAPI) noTlsAddressesApi = parseList(env.ADDNOTLSAPI);
        if (env.ADDCSV) csvSources = parseList(env.ADDCSV);
        minSpeed = Number(env.DLS) || minSpeed;
        csvRemarkCol = Number(env.CSVREMARK) || csvRemarkCol;
        scvDefault = env.SCV || scvDefault;
        alpnDefault = env.ALPN || alpnDefault;
        if (env.PROXYIP) proxyIPs = parseList(env.PROXYIP);
        if (env.UA) blockedUAs = blockedUAs.concat(parseList(env.UA));
        if (env.EDGE) scvDefault = 'true';

        await generateFakeInfo();
        if (socks5DataUrl) await loadSocks5();

        const ua = (request.headers.get('User-Agent') || '').toLowerCase();
        const url = new URL(request.url);
        const format = (url.searchParams.get('format') || '').toLowerCase();

        // ── /health ──
        if (url.pathname === '/health') {
            const origin = (env.ORIGIN_BASE || '').replace(/\/$/, '');
            let upstreamOk = false, upstreamStatus = 0;
            if (origin) {
                try {
                    const check = await fetch(`${origin}/sub_v2ray.txt`, {
                        headers: { 'User-Agent': 'sub-gateway/2.0' },
                        cf: { cacheTtl: 30 }
                    });
                    upstreamStatus = check.status;
                    upstreamOk = check.ok;
                } catch {}
            }
            return new Response(JSON.stringify({
                ok: !!origin && upstreamOk,
                service: 'sub-gateway',
                time: new Date().toISOString(),
                configured: !!(env.ORIGIN_BASE || env.SUB_TOKEN),
                upstreamOk,
                upstreamStatus
            }, null, 2), {
                status: upstreamOk ? 200 : 503,
                headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' }
            });
        }

        // ── /sub.txt (token-protected subscription proxy) ──
        if (url.pathname === '/sub.txt') {
            const token = url.searchParams.get('token');
            if (!token || token !== env.SUB_TOKEN) {
                return new Response('Forbidden', { status: 403 });
            }

            const origin = (env.ORIGIN_BASE || '').replace(/\/$/, '');
            if (!origin) {
                return new Response('Worker not configured (ORIGIN_BASE missing)', { status: 500 });
            }

            // Check if requesting Clash/Sing-box format
            if (format === 'clash' || format === 'singbox') {
                // Fetch plain subscription first
                const upstream = `${origin}/sub_v2ray.txt`;
                const res = await fetch(upstream, {
                    headers: { 'User-Agent': 'sub-gateway/2.0' },
                    cf: { cacheTtl: 60, cacheEverything: true }
                });
                if (!res.ok) return new Response(`Upstream error: ${res.status}`, { status: 502 });
                const plainB64 = await res.text();
                const converted = await convertFormat(plainB64, format, scvDefault);
                return new Response(converted, {
                    status: 200,
                    headers: {
                        'content-type': format === 'clash' ? 'text/yaml; charset=utf-8' : 'application/json; charset=utf-8',
                        'cache-control': 'public, max-age=60'
                    }
                });
            }

            // Default: return plain subscription (direct GitHub raw fetch)
            const upstream = `${origin}/sub_v2ray.txt`;
            const res = await fetch(upstream, {
                headers: { 'User-Agent': 'sub-gateway/2.0' },
                cf: { cacheTtl: 60, cacheEverything: true }
            });
            if (!res.ok) return new Response(`Upstream error: ${res.status}`, { status: 502 });

            return new Response(await res.text(), {
                status: 200,
                headers: {
                    'content-type': 'text/plain; charset=utf-8',
                    'cache-control': 'public, max-age=60'
                }
            });
        }

        // ── /sub (parametric subscription generation) ──
        if (url.pathname === '/sub') {
            let host, uuid, password, path, sni, type, scv, alpn, edgeTunnel, proxyIP, flow;

            host = url.searchParams.get('host');
            uuid = url.searchParams.get('uuid');
            password = url.searchParams.get('password') || url.searchParams.get('pw');
            path = url.searchParams.get('path') || '/?ed=2560';
            sni = url.searchParams.get('sni') || host;
            type = url.searchParams.get('type') || 'ws';
            scv = url.searchParams.get('allowInsecure') === '1' ? 'true' : (url.searchParams.get('scv') || scvDefault);
            alpn = url.searchParams.get('alpn') || alpnDefault;
            edgeTunnel = url.searchParams.get('edgetunnel') || url.searchParams.get('epeius') || '';
            proxyIP = url.searchParams.get('proxyip') || 'false';
            flow = url.searchParams.get('flow') || '';

            if (!host) {
                return new Response('Missing host parameter', { status: 400 });
            }

            const extraParams = { password, flow };

            if (password && !uuid) {
                protocolLabel = 'Trojan';
                uuid = password; // reuse variable for the subscription generator logic
            }

            if (!uuid && !password) {
                return new Response('Missing uuid or password parameter', { status: 400 });
            }

            const subB64 = await generateSubscription(
                host, uuid || password, path, sni, type, scv, alpn, edgeTunnel, proxyIP, extraParams
            );

            // Clash/Sing-box conversion
            if (format === 'clash' || format === 'singbox') {
                const converted = await convertFormat(subB64, format, scv);
                return new Response(converted, {
                    status: 200,
                    headers: {
                        'content-type': format === 'clash' ? 'text/yaml; charset=utf-8' : 'application/json; charset=utf-8',
                        'cache-control': 'public, max-age=120'
                    }
                });
            }

            return new Response(subB64, {
                status: 200,
                headers: {
                    'content-type': 'text/plain; charset=utf-8',
                    'cache-control': 'public, max-age=120'
                }
            });
        }

        // ── Quick access tokens (/auto, etc.) ──
        if (quickAccessTokens.length > 0 && quickAccessTokens.some(t => url.pathname === `/${t}`)) {
            let host = 'null', uuid = 'null';

            if (env.HOST) {
                const hosts = parseList(env.HOST);
                host = randomItem(hosts);
            }

            if (env.PASSWORD) {
                protocolLabel = 'Trojan';
                uuid = env.PASSWORD;
            } else {
                protocolLabel = 'VLESS';
                if (env.KEY) {
                    validDays = Number(env.TIME) || validDays;
                    updateHour = Number(env.UPTIME) || updateHour;
                    const uuids = await generateDynamicUUIDs(env.KEY);
                    uuid = uuids.currentUUID;
                } else {
                    uuid = env.UUID || 'null';
                }
            }

            path = env.PATH || '/?ed=2560';
            sni = env.SNI || host;
            type = env.TYPE || type;
            scv = env.EDGE ? 'true' : scvDefault;

            if (host === 'null' || uuid === 'null') {
                const missing = host === 'null' && uuid === 'null' ? 'HOST/UUID' : (host === 'null' ? 'HOST' : 'UUID');
                endPS += ` 订阅器内置节点 ${missing} 未设置！`;
            }

            const isTrojan = !!env.PASSWORD;
            const extraParams = { password: isTrojan ? uuid : undefined, flow: undefined };

            const subB64 = await generateSubscription(
                host, uuid, path, sni, type, scv, alpnDefault, '', 'false', extraParams
            );

            await tgNotify(`#获取订阅 ${fileLabel}`,
                request.headers.get('CF-Connecting-IP'),
                `UA: ${ua}\n域名: ${url.hostname}\n入口: ${url.pathname}${url.search}`
            );

            if (format === 'clash' || format === 'singbox') {
                const converted = await convertFormat(subB64, format, scv);
                return new Response(converted, {
                    headers: {
                        'content-type': format === 'clash' ? 'text/yaml' : 'application/json',
                        'content-disposition': `attachment; filename="${fileLabel}${format === 'clash' ? '.yaml' : '.json'}"`,
                    }
                });
            }

            return new Response(subB64, {
                headers: {
                    'content-type': 'text/plain; charset=utf-8',
                    'content-disposition': `attachment; filename="${fileLabel}.txt"`,
                }
            });
        }

        // ── Homepage: Web UI or 302 redirect ──
        if (url.pathname === '/') {
            // 302 redirect if configured
            if (env.URL302) {
                const urls = parseList(env.URL302);
                if (urls.length) {
                    if (urls[0] === 'nginx') {
                        return new Response(nginxPage(), {
                            headers: { 'Content-Type': 'text/html; charset=UTF-8' }
                        });
                    }
                    return Response.redirect(randomItem(urls), 302);
                }
            }
            // Reverse proxy if configured
            if (env.URL) {
                const urls = parseList(env.URL);
                if (urls.length) {
                    if (urls[0] === 'nginx') {
                        return new Response(nginxPage(), {
                            headers: { 'Content-Type': 'text/html; charset=UTF-8' }
                        });
                    }
                    return fetch(new Request(randomItem(urls), request));
                }
            }
            return new Response(renderUI(), {
                headers: { 'Content-Type': 'text/html; charset=UTF-8' }
            });
        }

        // ── 404 ──
        return new Response('Not Found', { status: 404 });
    }
};

function nginxPage() {
    return `<!DOCTYPE html><html><head><title>Welcome to nginx!</title>
<style>body{width:35em;margin:0 auto;font-family:Tahoma,Verdana,Arial,sans-serif}</style>
</head><body><h1>Welcome to nginx!</h1>
<p>If you see this page, the nginx web server is successfully installed and working.</p>
</body></html>`;
}
