# 美客多 ERP 服务器维护记录（2026-09-09）

## 结论

正式 ERP 确认运行在阿里云服务器 `8.148.227.139` 的
`/srv/amazon-meli-publisher`，本机仓库只用于开发和 Git 备份。

## 已执行

1. 在确认采集、发布、审核队列均无活动任务后开始维护。
2. 创建并启用 `/swapfile`：2GB，权限 600，并写入 `/etc/fstab`。
3. 写入 `/etc/sysctl.d/99-meli-swap.conf`：
   - `vm.swappiness=10`
   - `vm.vfs_cache_pressure=50`
4. 将生产 AI 手动生成超时从 300 秒调整为 90 秒；普通接口保持 20 秒，避免与 Nginx 300 秒边界竞态。
5. 重建干净后端镜像并将 `mvp-skeleton-backend:latest` 指向新镜像：
   - 不再声明 `/app/alembic.ini`、`/app/alembic`、`/app/app` 等错误镜像 Volume；
   - 不在镜像环境层写入美客多凭据或真实发布开关；
   - 包含 Pillow 12.3.0 和当前后端源码；
   - 清除继承的 `sh` entrypoint，worker 可直接运行 `python -m app.worker`。
6. 逐个重建 backend、collection worker、publish worker；没有重建 PostgreSQL、Redis、前端或浏览器数据。
7. 删除带错误 Volume/运行配置的旧后端镜像标签和临时镜像归档。
8. 将项目目录中的旧 compose 备份移动到 `/root/meli-config-backups/`，恢复服务器 Git 工作区干净。

## 验证

- 新镜像隔离导入主应用和 Pillow：通过。
- 新镜像服务器内完整测试：470 passed、13 skipped。
- backend：healthy，restart count 0。
- collection worker：healthy，restart count 0，进程存在。
- publish worker：healthy，restart count 0，进程存在。
- PostgreSQL、Redis：healthy，未重建。
- `/health`、`/api/system/readiness`、1000 条草稿列表：HTTP 200。
- 公网首页及公网 readiness：HTTP 200。
- 维护后 10 分钟窗口内三个新容器没有 ERROR、Traceback、HTTP 500/502/504。
- 维护后可用内存约 533MB；Swap 2GB 正常，构建高峰曾安全承接约 200MB。

## 历史“结果待核对”任务

任务 #7、#19、#33、#38 都早于可搜索的 `publish_reference` 机制，因此系统不能可靠证明当时是否创建过商品，不能自动标记“确认未创建”或自动重发。

任务 #38 的同一草稿后来由 #39 发布为 `CBT5173511210`，但这只能证明后续任务成功，不能排除 #38 当时创建过另一个商品，所以仍保留原始 BLOCKED 证据，不篡改历史状态。其余任务同样等待操作员在店铺后台核对。

## 后续建议

- 旧镜像曾在服务器本地镜像元数据中包含运行配置。该镜像已删除且未发现被推送，但仍建议在美客多开放平台方便时轮换应用 Secret，完成后重新授权店铺。
- `review_worker` 仍未启动；当前 Claude/NVIDIA 审核属于可选能力且 review 队列为空，为节省 1.6GB 服务器内存，维持不启动。
- 服务器外网稳定后，可按正式 `backend/Dockerfile` 和 `.env` 中的 DaoCloud 基础镜像重新做一次完整无缓存构建；当前生产镜像已通过完整测试，不影响运行。

## 禁止事项

- 不执行 `docker-compose down -v`。
- 不强制重建 PostgreSQL、Redis 或浏览器配置。
- 未经准确回查，不自动重发未知结果任务。
