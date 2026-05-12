# Cloudflare + GitHub 自动优选订阅（V2Ray）

该项目用于：
- 维护多节点池（你自己的 VPS 出口）
- 定时健康检测并打分
- 自动生成手机端可导入的 V2Ray 订阅
- 通过 GitHub Pages + Cloudflare 自定义域名分发订阅

## 合规说明
仅用于你本人合法网络访问与安全加固测试。请遵守当地法律法规与平台条款。

## 目录
- `nodes/nodes.json`：节点池（手动维护）
- `scripts/select_best.py`：自动优选
- `scripts/build_subscription.py`：生成订阅
- `public/sub.txt`：最终订阅输出（Base64）
- `.github/workflows/update-subscription.yml`：定时自动更新

## 1) 准备
1. 创建 GitHub 仓库并上传本项目。
2. 在仓库 `Settings -> Secrets and variables -> Actions` 添加：
   - `SUBSCRIPTION_TOKEN`：任意强随机字符串（用于保护订阅地址）。
3. 开启 GitHub Pages（Deploy from branch: `main` / `/ (root)`）。
4. 在 Cloudflare 上将 `sub.yourdomain.com` CNAME 到 `<your-github-username>.github.io`。

## 2) 维护节点
编辑 `nodes/nodes.json`，每条记录一个节点（当前模板支持 `vless+ws+tls`）。

## 3) 自动任务
工作流每 30 分钟运行一次，也可手动触发：
- 读取节点
- TCP/TLS 打分
- 选择 Top N
- 生成 `public/sub.txt`
- 提交回仓库

## 4) 手机端导入
你的订阅地址：
- `https://sub.yourdomain.com/sub.txt?token=你的SUBSCRIPTION_TOKEN`

在 v2ray 客户端里添加订阅地址并更新即可。

## 5) 关于“优选纯净 IP”
这个模板可以自动筛掉高延迟/握手异常节点，但“TikTok 可用性”受地区策略与平台风控动态影响，无法百分百保证。建议维持 3-5 个不同 ASN 的出口，持续轮换。
