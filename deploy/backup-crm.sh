#!/bin/bash
# CRM Demo 每日备份：宝塔计划任务每日 03:00 执行本脚本
# 备份内容：PostgreSQL 数据库 + 客户附件文件，保留 7 份轮转
BACKUP_DIR=/www/backup/crm
mkdir -p "$BACKUP_DIR"

# 1. 数据库
docker exec crm-demo-db pg_dump -U crm-demo crm-demo | gzip > "$BACKUP_DIR/crm-demo_$(date +%F).sql.gz"

# 2. 客户附件（uploads volume）
docker exec crm-demo-api tar czf - -C /app uploads 2>/dev/null | cat > "$BACKUP_DIR/uploads_$(date +%F).tar.gz"

# 3. 轮转：保留 7 天
find "$BACKUP_DIR" -name "crm-demo_*.sql.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +7 -delete

# 4. 清理 Docker 悬空镜像层（防止 --build 累积吃磁盘）
docker image prune -f >/dev/null 2>&1

# 5. 磁盘水位报告（低于 20% 时标记警告）
DISK_PCT=$(df / | awk 'NR==2 {gsub("%",""); print $5}')
echo "backup done: $(ls -t "$BACKUP_DIR" | head -2 | tr '\n' ' ') | 磁盘已用: ${DISK_PCT}% $([ "$DISK_PCT" -ge 80 ] && echo '⚠️ 磁盘告急，请清理') "
