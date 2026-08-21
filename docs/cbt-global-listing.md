# CBT Global Selling 刊登规则

适用对象：授权站点为 `CBT`、账号 tags 中没有 `user_products_seller` 的传统跨境卖家。

## 正确接口

- 店铺能力：`GET /marketplace/users/{CBT_SELLER_ID}`
- 市场配额：`GET /marketplace/users/cap`
- CBT 类目预测：`GET /sites/CBT/domain_discovery/search?q=...`
- 类目属性：`GET /categories/{CBT_CATEGORY_ID}/attributes`
- 刊登：`POST /global/items`

传统 CBT 不使用本土店的 `POST /items`。`/items` 只适用于单一站点卖家；将 CBT 商品发到该接口会造成站点和物流模型错误。

## 发布体

根对象必须以全球商品为单位保存：

- `category_id`：必须为 `CBT...`
- `currency_id`：固定 `USD`
- `price`、`available_quantity`
- `title`、`description`：`description` 必须是 `{"plain_text": "..."}` 对象，不能发送字符串
- `family_name`：传统 CBT 必填
- `attributes`：至少包含 `ITEM_CONDITION`、`SELLER_SKU`、包裹长宽高重量以及类目要求属性
- `sale_terms`：按类目补充质保等条款
- `sites_to_sell`：每个目标市场一个元素

`sites_to_sell` 中保存市场专有资料：`site_id`、`logistic_type: remote`、`listing_type_id`、本地标题和图片。图片与变体不能误放到根层。

## 本 ERP 的限制

- 仅展示并允许 Remote 市场；`fulfillment`/FULL 永远不进入发布请求。
- 所有目标市场都来自已授权 CBT 店铺的实时能力返回；不能手填未开通市场。
- 当前阶段提供配置保存和 payload 预检。真实 `POST /global/items` 仍必须接入现有的审核、人工批准、幂等与发布队列后才开放。
- 若账号出现 `user_products_seller` tag，必须改为 `/global/user-products` 流程，不能混用本文流程。
