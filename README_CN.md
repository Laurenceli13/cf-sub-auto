# Cloudflare + GitHub 自动优选订阅生成器

> 🇨🇳 为跨境电商从业者打造的免费节点订阅聚合工具

[English](README.md) | **中文**

---

## 📖 项目简介

`cf-sub-auto` 是一个全自动的代理订阅聚合与分发系统，专为中国跨境电商用户设计：

- 🔄 **每6小时自动抓取** GitHub 公开免费节点并去重
- ⚡ **TCP 延迟测速** 筛选高速节点，优先输出低延迟结果
- 🌍 **按国家/地区分类** 输出（美国、日本、新加坡、香港等）
- 📱 **多格式订阅输出**: V2Ray Base64、Clash Meta YAML、Sing-Box JSON
- 🛡️ **Cloudflare Worker 网关** Token 鉴权 + 优选 IP 加速
- 🎛️ **Web 控制台** 在线生成专属订阅、查看节点状态

### 适用场景

| 场景 | 说明 |
|------|------|
| 🛒 **Shopee / Lazada** 运营 | 需要东南亚节点（新加坡、马来、泰国等） |
| 📦 **Amazon 多站点** | 需要美国、欧洲、日本节点 |
| 📊 **TikTok / Instagram** 运营 | 需要全球多地区 IP |
| 💻 **跨境电商 ERP** | 稳定翻墙访问海外后台系统 |
| 🧪 **网络工具测试** | 合法的网络连通性与安全测试 |

---

## 🚀 快速部署（10分钟）

### 第一步：Fork 本仓库

点击右上角 Fork 按钮，将仓库复制到你的 GitHub 账号。

### 第二步：配置 Secrets

进入仓库 `Settings → Secrets and variables → Actions → Secrets`，添加：

| Secret 名称 | 说明 | 示例 |
|-------------|------|------|
| `SUBSCRIPTION_TOKEN` | 订阅地址鉴权密码（必填） | `MyStr0ng!Token2024` |
| `NOTIFY_URL` | Bark/Server酱告警地址（可选） | `https://api.day.app/xxx/节点告警` |

### 第三步：启用 GitHub Pages

1. 进入 `Settings → Pages`
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `main`，目录选择 `/ (root)`
4. 点击 Save

稍等片刻，你的节点订阅将自动生成。

### 第四步：绑定自定义域名（Cloudflare，强烈推荐）

GitHub Pages 默认域名在国内访问不稳定。建议绑定自己的域名并通过 Cloudflare 代理：

1. 在 Cloudflare DNS 添加 CNAME 记录：
   ```
   sub.yourdomain.com → <你的用户名>.github.io
   ```
2. **Proxy status 打开**（橙色云朵），启用 Cloudflare CDN 加速

### 第五步（可选）：部署 Cloudflare Worker 网关

如果你需要更高级的 Token 鉴权和优选 IP 功能：

```bash
# 安装 Wrangler CLI
npm install -g wrangler

# 登录 Cloudflare
wrangler login

# 配置 Secret
wrangler secret put SUB_TOKEN

# 部署
wrangler deploy
```

Worker 环境变量说明见 [wrangler.toml](wrangler.toml)。

---

## 📱 客户端配置教程

### Clash Verge (Windows / macOS) — 推荐

1. 下载安装 [Clash Verge](https://github.com/clash-verge-rev/clash-verge-rev/releases)
2. 打开应用 → **Profiles** → **New Profile**
3. 类型选择 `Remote`，URL 填入：
   ```
   https://sub.yourdomain.com/sub.txt?token=你的TOKEN
   ```
4. 点击 **Update**，等待拉取完成
5. 切换到 **Proxies** 标签，选择合适的节点
6. 开启 **System Proxy** 或使用 TUN 模式

### Shadowrocket (iOS)

1. App Store 外区账号下载 Shadowrocket（小火箭）
2. 打开应用 → 右上角 **+** → 类型选择 **Subscribe**
3. URL 填入：
   ```
   https://sub.yourdomain.com/sub.txt?token=你的TOKEN
   ```
4. 点击完成，下拉刷新即可看到节点列表
5. 点击顶部开关连接，首次使用需允许 VPN 配置

### v2rayNG (Android)

1. 下载 [v2rayNG](https://github.com/2dust/v2rayNG/releases)
2. 打开应用 → 左上角菜单 → **订阅设置**
3. 右上角 **+** → 填写备注和订阅地址：
   ```
   https://sub.yourdomain.com/sub.txt?token=你的TOKEN
   ```
4. 返回主界面，右上角菜单 → **更新订阅**
5. 选择一个节点，点击右下角按钮连接

### Quantumult X (iOS)

1. App Store 外区账号下载 Quantumult X
2. 打开应用 → 底部 **风车** 图标 → **节点** → **引用(订阅)**
3. 右上角 **+** → 填入订阅地址：
   ```
   https://sub.yourdomain.com/sub.txt?token=你的TOKEN
   ```
4. 保存并更新
5. 回到首页，选择合适的策略组，开启开关连接

---

## 📊 节点状态面板

部署 GitHub Pages 后，访问 `https://sub.yourdomain.com/` 即可看到实时状态面板：

- 节点总数 / 存活数 / 平均延迟
- 按地区分组筛选
- 节点延迟排序表格
- 各格式订阅快捷复制
- 自动刷新

---

## 📁 订阅文件说明

| 文件 | 格式 | 说明 |
|------|------|------|
| `sub.txt` | Base64 | 全部协议节点（vmess/vless/trojan/ss/ssr/hysteria2） |
| `sub_v2ray.txt` | Base64 | 仅 V2Ray 系列协议（不含 hysteria） |
| `sub_hysteria.txt` | Base64 | 仅 Hysteria2 协议节点 |
| `sub_clash.yaml` | YAML | Clash Meta 格式订阅 |
| `sub_singbox.json` | JSON | Sing-Box 格式订阅 |
| `sub_raw.txt` | 明文 | 所有节点明文链接（调试用） |
| `regions/sub_US.txt` | Base64 | 美国地区节点 |
| `regions/sub_JP.txt` | Base64 | 日本地区节点 |
| `regions/sub_SG.txt` | Base64 | 新加坡地区节点 |

---

## 🔧 工作原理

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  GitHub Actions  │    │  GitHub Pages     │    │  Cloudflare      │
│  每6小时运行      │    │  托管输出文件      │    │  Worker 网关      │
│                  │    │                   │    │                  │
│  1. 抓取免费节点   │───▶│  sub.txt          │───▶│  Token 鉴权       │
│  2. 去重清洗      │    │  sub_v2ray.txt    │    │  优选IP加速       │
│  3. TCP 测速      │    │  sub_clash.yaml   │    │  格式转换         │
│  4. 格式转换      │    │  index.html       │    │  Web 控制台       │
│  5. 提交回仓库    │    │                   │    │                  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## ⚠️ 合规与免责

- 本项目**仅用于合法的网络访问与安全加固测试**
- 请遵守**当地法律法规**及所使用平台的**服务条款**
- 不建议用于任何违反中国《网络安全法》及相关法规的活动
- 建议维持 **3-5 个不同 ASN 的私有出口节点**，配合本项目的公共节点作为备用
- "TikTok 可用性"受地区策略与平台风控动态影响，无法保证 100% 可用

---

## ❓ 常见问题

### 国内无法访问 GitHub Pages 怎么办？

1. **方案一**：使用 Cloudflare Worker 作为前置网关（推荐）
2. **方案二**：在 Cloudflare DNS 中开启 CDN 代理（橙色云朵）
3. **方案三**：使用国内 DNS（如 DNSPod）并将记录指向 Cloudflare 边缘 IP

### 订阅更新失败 / 节点全是离线？

1. 检查 GitHub Actions 是否正常运行（`Actions` 标签页查看）
2. 检查 `SUBSCRIPTION_TOKEN` Secret 是否配置正确
3. 手动触发一次 Workflow（在 Actions 页面点击 `Run workflow`）
4. 查看 `public/nodes_status.json` 了解节点测速详情

### 如何添加自己的私有节点？

1. Fork 仓库后，编辑 `nodes/nodes.json` 填入你的节点信息
2. 格式参考现有模板（VLESS over WebSocket + TLS）
3. Workflow 中取消注释 `select_best.py` 相关步骤
4. 私有节点 UUID 和地址**不要直接写在公开文件里** — 使用 GitHub Secrets

### 订阅地址提示 403 Forbidden？

- 确认 URL 包含正确的 `?token=你的SUBSCRIPTION_TOKEN`
- 检查 Cloudflare Worker 的环境变量 `SUB_TOKEN` 是否设置正确

---

## 📦 更新日志

- **v2.0** — 合并 WorkerVless2sub Web UI + 优选IP体系，新增 Clash/Sing-box 格式，地区分类输出
- **v1.0** — 初始版本，基础订阅聚合与分发

---

## 🙏 致谢

- [WorkerVless2sub](https://github.com/cmliu/WorkerVless2sub) — Cloudflare Worker 优选订阅生成器
- [CloudflareSpeedTest](https://github.com/XIU2/CloudflareSpeedTest) — Cloudflare IP 测速工具
- [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) — Clash 规则配置
- 免费节点来源：awesome-vpn, shaoyouvip, Pawdroid

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)
