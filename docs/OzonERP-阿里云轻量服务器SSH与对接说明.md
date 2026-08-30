# Ozon ERP 对接阿里云轻量服务器说明

更新时间：2026-08-30

## 1. 当前服务器信息

| 项目 | 值 |
| --- | --- |
| 云服务器 | 阿里云轻量应用服务器 |
| 公网地址 | `8.148.227.139` |
| SSH 用户 | `root` |
| SSH 私钥 | `D:\Desktop\api\美客多.pem` |
| 项目目录 | `/srv/amazon-meli-publisher` |
| 对外网址 | `https://ml-erp.woxq.cn` |
| 健康检查 | `https://ml-erp.woxq.cn/health` |
| 当前服务 | FastAPI 后端、前端静态站点、PostgreSQL、Redis、采集/审核/发布 worker |

私钥只保存在本机，不上传 GitHub，不写入项目文档，不发送给浏览器或 API。

## 2. SSH 连接

在 PowerShell 中执行：

```powershell
$key = 'D:\Desktop\api\美客多.pem'
ssh -o ConnectTimeout=15 -o StrictHostKeyChecking=no -i $key root@8.148.227.139
```

首次连接时确认主机指纹。若 Windows 拒绝读取私钥，检查文件权限，确保当前 Windows 用户可以读取该文件，并确认阿里云安全组允许 TCP `22`，不建议对公网开放给所有地址。

连接后：

```bash
cd /srv/amazon-meli-publisher
docker-compose ps
curl -fsS https://ml-erp.woxq.cn/health
```

## 3. SSH 和业务 API 的边界

Ozon ERP 不应在浏览器中保存服务器 SSH 私钥，也不应让浏览器直接执行 SSH 命令。

正确链路：

```text
Ozon ERP 前端
    -> HTTPS /api/ozon/*
服务器 FastAPI 后端
    -> Ozon Seller API
数据库保存店铺授权、任务和结果
```

SSH 只用于以下运维动作：

- 上传后端或前端构建文件；
- 更新 `.env` 中的服务端配置；
- 执行数据库迁移；
- 查看 Docker 服务和日志；
- 重启单个无状态服务。

## 4. 部署现有项目

本地仓库：

```text
C:\Users\Administrator\Documents\amazon --美客多\work\mercado-libre-erp-github
```

推荐先提交并推送 GitHub，再通过 SSH 同步服务器。GitHub 备份成功不等于服务器已经部署，服务器健康检查和线上页面资源必须另行确认。

前端构建并上传：

```powershell
cd 'C:\Users\Administrator\Documents\amazon --美客多\work\mercado-libre-erp-github\frontend'
npm run build
scp -i 'D:\Desktop\api\美客多.pem' -r dist/. root@8.148.227.139:/srv/amazon-meli-publisher/frontend/dist/
```

后端代码同步后，在服务器执行：

```bash
cd /srv/amazon-meli-publisher
docker-compose run --rm migrate
docker-compose restart backend
docker-compose ps
curl -fsS https://ml-erp.woxq.cn/health
```

不要使用 `docker-compose down -v`，否则可能删除数据库或 Redis 数据。服务器使用旧版 `docker-compose 1.29.2`，不要随意执行 `--force-recreate`；更新前先确认采集、审核、发布队列没有正在处理的任务。

查看日志：

```bash
cd /srv/amazon-meli-publisher
docker-compose logs --since 10m backend
docker-compose logs --since 10m collection_worker publish_worker review_worker
```

## 5. Ozon ERP 对接现状

当前仓库已经具备 Amazon 采集、草稿、AI 辅助、店铺管理及美客多发布能力，但不是已经完成的 Ozon ERP 连接器：

- 当前后端的发布适配器面向 Mercado Libre；
- 当前数据库模型和店铺授权流程主要面向 Mercado Libre；
- 尚未确认 Ozon Seller API 的 Client ID、API Key、店铺区域和授权方式；
- 因此不能把当前服务器地址直接称为“已经对接 Ozon”。

## 6. Ozon 对接建议

新增独立的 Ozon 适配层，不修改现有美客多发布流程：

```text
店铺授权
  -> 保存加密的 Ozon 凭证
商品草稿
  -> 映射 Ozon 商品字段、类目和属性
发布任务
  -> Ozon API 请求
  -> 保存 request_id / 商品 ID / 状态 / 原始错误码
状态同步
  -> worker 定时查询导入或发布结果
```

建议的后端路由：

```text
GET  /api/ozon/stores
POST /api/ozon/stores/{store_id}/authorize
POST /api/ozon/stores/{store_id}/diagnostics
GET  /api/ozon/categories
GET  /api/ozon/categories/{category_id}/attributes
POST /api/ozon/drafts/{draft_id}/publish
GET  /api/ozon/publish-jobs/{job_id}
```

建议的实现原则：

1. Ozon 凭证只在后端加密保存，前端只显示“已配置/未配置”和错误状态。
2. 每个 Ozon 店铺单独绑定区域、Client ID、API Key 和卖家身份。
3. 类目、属性、图片和视频先完成 Ozon 侧校验，再创建发布任务。
4. 发布接口使用幂等键，超时或断网时标记为“结果待核对”，禁止盲目重复创建商品。
5. Ozon 异步任务必须保存任务 ID，并由 worker 查询最终状态。
6. Ozon 适配器与 Mercado Libre 适配器分开，不能共用站点、类目或发布状态字段。

## 7. 需要提供的 Ozon 配置

不要把以下内容发到聊天、GitHub 或前端代码中，应通过服务器 `.env` 或后端加密凭证设置：

```dotenv
OZON_API_BASE_URL=https://api-seller.ozon.ru
OZON_CLIENT_ID=
OZON_API_KEY=
OZON_SELLER_ID=
OZON_REGION=
```

实际变量名以最终实现为准。拿到凭证后，先做非发布诊断，只验证授权、卖家身份和 API 可达性；不要用诊断接口创建商品。

## 8. 上线验收标准

### SSH / 服务

- SSH 可以登录服务器；
- `docker-compose ps` 中 backend 和各 worker 正常；
- `https://ml-erp.woxq.cn/health` 返回 `status: ok`；
- 前端 HTML 引用了本次构建的新资源 hash；
- 数据库和 Redis 数据没有被清除。

### Ozon

- Ozon 店铺可以保存并显示已配置状态；
- 非发布诊断能返回卖家身份和 API 状态；
- 类目和属性能从 Ozon API 加载并缓存；
- 图片、视频、变体和必填属性校验结果能在草稿页显示；
- 发布任务能显示处理中、成功、失败、结果待核对；
- 成功时保存 Ozon 商品 ID；
- 超时或未知结果不会自动重复创建商品。

在以上验收全部通过前，只能说“服务器 SSH 已配置”或“代码已部署”，不能说“Ozon ERP 已完成对接”。
