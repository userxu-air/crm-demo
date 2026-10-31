# YueCRM — 小团队 CRM 学习模板

一个面向小团队（2~12 人）的客户管理系统参考实现：销售自拓客户 → 跟进时间线 → 3 天滚动回访提醒 → 成交流水 → 老板看板 → Excel 报表一键导出。

> ⚠️ **免责声明 / License**
>
> 本项目仅作为**学习与技术交流的模板**，可自由 Fork、阅读、修改、自用。
> **严禁任何形式的商业使用**（包括二次开发后对外售卖、SaaS 化运营、交付给第三方等）。
> 项目内所有数据均为演示占位数据，与任何真实企业、客户无关。

## 功能特性

- **客户管理**：线索-客户合一，5 阶段流转（新客户→跟进→成交/流失），3 天滚动回访自动提醒
- **防撞单**：手机号归一存储 + 唯一约束 + 409 拦截，销售间客户不撞单
- **跟进时间线**：电话/微信/上门等分类，编辑旧跟进不覆盖最新提醒
- **成交流水**：数量×单价自动算金额（显式金额优先）、复购标记、开票/收款账户
- **历史数据一键导入**：Excel 多 sheet 合并解析、客户名归一查重（全角/空格变体）、成交去重（同客户+日期+产品+金额）、名称疑似重复提醒、导入批次溯源、单飞锁防并发
- **附件**：合同 PDF/交易明细上传下载（uuid 存储、白名单、20MB 上限）
- **三级角色**：admin（全权）/ sales（仅本人数据，行级隔离）/ boss（只读看板）
- **报表导出**：业绩汇总（按人员开关过滤）/ 销售明细表汇总 / 个人日报，模板驱动、模板即样例
- **安全**：JWT（12h）、bcrypt、参数化 ORM、上传白名单、容器内存天花板、密钥全部环境变量外置

## 技术栈

- 后端：FastAPI + SQLAlchemy 2.0 + PostgreSQL 16（本地开发可 SQLite）+ Alembic-ready
- 前端：React 18 + TypeScript + Vite 5 + Ant Design 5 + ProComponents
- 部署：Docker Compose + nginx 反代 + 每日备份脚本（DB + 附件，7 天轮转）

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/<you>/yuecrm.git
cd yuecrm/deploy
cp .env.example .env        # 修改其中的密码与密钥
docker compose up -d --build
# 访问 http://localhost:8000 （前端见方式二，或自行反代）
```

### 方式二：本地开发

```bash
# 后端（默认 SQLite，零配置）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev   # http://localhost:5173
```

默认管理员账号：`13800000001 / Demo@2026`（首登后请立即修改）。

## 项目结构

```
backend/
  app/
    main.py          # 路由挂载
    models.py        # users / customers / followups / deals / attachments / import_logs
    routers/         # auth, customers, deals, exports, attachments, importer, ingest, users
    seed.py          # 建表 + 轻量迁移（PG/SQLite 方言自适应）+ 种子管理员
  templates/         # 报表模板（*_样板.xlsx 为占位数据版）
  test_*.py          # 8 套件 149 项按钮级/接口级测试
frontend/
  src/pages/         # Dashboard / Customers / CustomerDetail / Settings / ImportCard
deploy/
  docker-compose.yml # 双容器（api + PG16），api 有 600M 内存天花板
  nginx-crm.conf     # 反代参考配置
  backup-crm.sh      # 每日备份（DB + 附件）
```

## 值得一看的设计点

- **防撞单**：手机号 NFKC 归一（去 +86/横线/空格）后唯一索引，多入口（手工/导入/bot）统一拦截
- **导入健壮性**：单飞锁（并发只允许 1 个）+ 瘦行投影（丢弃 WPS 万列填充，内存 -98%）+ 成交去重（同客户+日期+产品+金额）+ 文件大小护栏
- **导入溯源**：每笔导入数据带批次号（customers/deals/import_logs 三表关联）
- **权限模型**：行级隔离在路由层统一实现，boss 角色写操作全 403
- **部署健壮性**：密钥全外置、数据库不对公网、容器内存天花板、备份轮转

## 免责声明

本项目仅供学习交流使用，作者不对任何因商业使用产生的后果负责。
如需商业使用的 CRM，请选择正规商业产品或获取相应授权。
