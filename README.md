# 数字人文文本校勘

这是一个 Python 标准库实现的校勘工作台，使用 SQLite 保存作品、版本、残片、转录、段落、异文、注释、修订层和快照，并通过 `http.server` 暴露 JSON API。

## 启动与测试

```bash
python app.py
python -m unittest discover -s tests -v
```

默认端口 `8114`，地址 <http://127.0.0.1:8114>。首次启动创建一个带缺页残片和不可辨标记的示例。数据库可通过 `COLLATION_DB` 指定，端口可通过 `PORT` 指定。

## 业务规则

- 版本类型限定为 `version`、`fragment`、`transcription`。
- 段落和版本必须属于同一作品，同一版本不能重复对齐同一段落。
- 只有负责人或被单独授权的编辑可以修改对应版本；其他用户只有查看权限。
- `[缺页]`、`[不可辨]`、`[残损]` 等标记会参与校勘稿导出和缺口统计，不匹配的方括号会拒绝保存。
- 每次新增或修改异文都会产生递增修订号和 JSON 快照；提交必须携带 `expected_revision`，旧页面不能覆盖新层。
- 锁定段落由负责人执行，锁定后任何新修订都会被拒绝。
- 负责人或被授予 `review` 权限的用户可对段落提交签认：结论为 `approved`（通过）或 `returned`（退回），并必须填写处理意见；同一审阅人的新签认取代其生效中的旧签认。
- 存在生效的退回签认时，新增异文或新修订层必须携带 `address_review_id`（对应签认编号），提交后该签认标记为 `addressed`；段落内容一旦产生新修订，其余生效中的签认一律失效（`superseded`）。
- 有签认记录的段落，负责人只有在存在生效的通过签认且没有生效的退回签认时才能锁定；从未签认过的旧段落维持原锁定方式。
- 锁定后的段落不能再提交签认。

## 主要接口

- `POST /api/users`、`POST /api/works`
- `POST /api/works/{id}/witnesses`、`POST /api/witnesses/{id}/editors`
- `POST /api/works/{id}/passages`、`POST /api/works/{id}/access`
- `POST /api/alignments`
- `POST /api/variants`、`POST /api/variants/{id}/revisions`（均可选带 `address_review_id`）
- `POST /api/passages/{id}/reviews`（`decision` + `opinion`）
- `GET /api/passages/{id}/snapshots/{revision}?user_id=...`
- `POST /api/passages/{id}/lock`
- `GET /api/works/{id}/collation?user_id=...`

导出接口把版本对齐、异文、注释、残损缺口、锁定状态和段落签认组合成可复核的校勘稿；每个段落附带 `reviews` 明细（结论、处理意见、审阅人、状态）和汇总的 `review_state`（`none`/`pending`/`approved`/`returned`）。
