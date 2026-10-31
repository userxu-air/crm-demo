# CRM Demo 上线部署清单（P1-W3）

目标：crm.example.com 可访问（HTTPS），数据库不出公网，每日自动备份。

## 一、你人工要做的两步

**1. 阿里云 DNS 加记录**（约 1 分钟）
- 控制台 → 云解析 DNS → example.com → 添加记录
- 记录类型 `A`，主机记录 `crm`，记录值 = ECS 公网 IP
- 子域名沿用主备案，无需新备案

**2. 上传代码到 ECS**（二选一）
- 方式 A（推荐）：Gitee 建私库 `crm-demo`，本地推送后 ECS 上 `git clone`
- 方式 B：宝塔文件管理上传整个 `crm-demo/` 目录到 `/www/crm-demo`

## 二、ECS 上执行（SSH / 宝塔终端，约 5 分钟）

```bash
# 1. 起后端 + 数据库（首次自动建表 + 创建管理员 13800000001 / Demo@2026）
cd /www/crm-demo/deploy
docker compose up -d

# 2. 验证
curl http://127.0.0.1:8000/api/health   # 应返回 {"ok":true,"app":"CRM Demo"}

# 3. 前端构建并部署（ECS 需有 node；没有就本地 build 后上传 dist）
cd /www/crm-demo/frontend
npm install --registry=https://registry.npmmirror.com
npm run build
mkdir -p /www/wwwroot/crm.example.com
cp -r dist /www/wwwroot/crm.example.com/dist
```

## 三、宝塔面板操作（约 3 分钟）

1. **建站**：网站 → 添加站点 → 域名 `crm.example.com`，纯静态，根目录 `/www/wwwroot/crm.example.com/dist`
2. **反代 API**：站点设置 → 配置文件，按 `deploy/nginx-crm.conf` 调整（关键：`location /api/` 反代 `127.0.0.1:8000` + SPA `try_files`）
3. **SSL**：站点设置 → SSL → Let's Encrypt 一键申请 → 开启「强制 HTTPS」

## 四、每日备份（1 分钟）

宝塔 → 计划任务 → 添加 Shell 脚本，每日 03:00 执行：

```bash
bash /www/crm-demo/deploy/backup-crm.sh
```

（pg_dump 压缩存 `/www/backup/crm/`，保留 7 份轮转）

## 五、上线后账号说明

**生产环境首次启动只自动创建 1 个管理员账号**：

- 地址：`https://crm.example.com`
- 账号：`13800000001` / `Demo@2026`
- **第一件事**：系统设置 → 修改账号 → 改掉初始密码

**其他同事账号（本地测试数据不会带到生产）**：

1. 管理员登录 → 系统设置 → 新建账号（姓名 + 手机号 + 你自定的初始密码 + 角色）
2. 初始密码发给同事本人
3. 同事首次登录后自行修改密码
4. 离职流程：停用账号 → 客户详情页转移客户 → 删除账号

## 六、日常更新（约 30 秒）

```bash
cd /www/crm-demo && git pull
cd deploy && docker compose up -d --build
cd ../frontend && npm run build && cp -r dist /www/wwwroot/crm.example.com/dist
```

## 密钥备忘（已写入 deploy/docker-compose.yml，Gitee 私库可见）

| 项 | 值 |
|---|---|
| 生产管理员初始密码 | `Demo@2026`（首次登录必改） |
| bot 写入口令（V2 用） | `CHANGE_ME_INGEST_API_KEY` |
| JWT 密钥 / DB 密码 | 已内置于 compose，无需手动操作 |

## 红线

- 绝不在 `/root` 放业务文件（项目固定在 `/www/crm-demo`）
- PG 不暴露公网端口（compose 已锁定）
- 更新前先跑 `bash /www/crm-demo/deploy/backup-crm.sh` 手动快照
