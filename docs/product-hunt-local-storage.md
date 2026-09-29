# Product Hunt 本地存储

结果数据库：`runtime/product_hunt.sqlite3`，表名 `products`。

每日采集在调用 AITDK 前读取数据库，用「发布日期 + Product Hunt 链接」
去重。相同组合只存一条；不同发布日期可以保留同一产品。重试使用 upsert
更新原结果，不追加重复行。每个网站完成以及后台 RDAP 返回时提交到数据库。

默认采集与重试入口不再读取或写入飞书。旧 `--skip-feishu` 参数保留兼容。
JSON 报告与 checkpoint 继续保留，便于恢复和排查。

2026-09-10 已迁移本机现存报告与 checkpoint，并读取飞书补入 4,866 条历史
记录，数据库共 6,325 条唯一记录。导入时保留本地已有结果；飞书的表头、
空行及缺失去重键的 17 行未导入。Product Hunt 原始产品缓存不视为已完成采集。
