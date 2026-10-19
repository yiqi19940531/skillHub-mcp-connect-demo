# 接口与能力分类

REST 与全部 32 个 MCP 工具复用业务服务和授权规则。MCP 的完整输入参数见 [工具参数表](MCP_TOOLS.md)。运行后可以在 `/api/docs` 查看当前 OpenAPI。

## MCP 工具

| 类别 | 工具 | 典型用法与权限 |
| --- | --- | --- |
| 身份与分类 | `whoami`、`list_my_teams`、`list_skill_categories` | 先核对 Token 的真实主体；分类计数经过 ACL 过滤 |
| 发现与读取 | `list_skills`、`search_skills`、`get_skill`、`get_skill_instructions`、`get_skill_file`、`list_skill_versions` | 列出/搜索授权技能，读取正文、文本附件和可访问版本；不会泄露他人草稿 |
| 个人收藏 | `list_favorites`、`add_favorite`、`remove_favorite` | 仅操作当前用户的星标，收藏后仍重新检查技能授权 |
| 团队收藏集 | `list_collections`、`list_collection_skills`、`add_skill_to_collection`、`remove_skill_from_collection` | 团队成员读取，TeamOwner/管理员维护；集合受众须有 Skill 使用权 |
| 安装与维护 | `get_skill_install_plan`、`install_skill`、`report_install_result`、`check_skill_updates`、`update_skill`、`uninstall_skill`、`list_installed_skills` | 检查、获取计划、上报执行、比较版本和受管理文件；Agent 自己完成本地操作 |
| 上传与送审 | `prepare_skill_upload`、`upload_skill`、`request_skill_review`、`get_skill_review_status`、`list_my_uploads` | 文本或一次性 ZIP 上传、草稿、送审和查询；上传者不得自审 |
| 共享与反馈 | `share_skill`、`rate_skill`、`report_skill_issue`、`recommend_skills` | 共享范围申请、版本评分、问题反馈与规则推荐；推荐先按 ACL 过滤 |

合计 3 + 6 + 3 + 4 + 7 + 5 + 4 = **32 个**。统计是新增 REST/Web 能力，保持 MCP 工具清单兼容。

读取需 `skills:read`，变更还需 `skills:write`；OAuth 范围不能代替资源权限。业务返回 `{ok,data,trace_id}` 或 `{ok:false,error,trace_id}`，MCP 同步设置 `isError`。

## REST 分类

| 接口组 | 主要路径 | 用途 |
| --- | --- | --- |
| Web 身份 | `POST /api/v1/auth/login`、`POST /auth/logout`、`GET /me` | Cookie 会话、CSRF 和当前身份 |
| 技能市场 | `GET /skills`、`GET /categories`、`GET /teams`、`GET /skills/{id}` | 检索、分类、团队与详情 |
| 内容与版本 | `GET /skills/{id}/versions`、`GET /skills/{id}/versions/{version}/files/{path}` | 授权版本、清单和文本读取 |
| 收藏与团队集合 | `/favorites`、`/collections`、`/collections/{id}/skills` | 个人星标，团队集合创建/修改/归档和成员维护 |
| 上传与审核 | `POST /skills`、`POST /skills/{id}/versions`、`POST /uploads`、`POST /skills/{id}/reviews`、`POST /reviews/{id}/decision` | 上传、草稿、版本和独立审批 |
| 共享治理 | `/skills/{id}/sharing`、`/sharing/revoke`、`/versions/{version}/status` | 共享申请/审批、收回授权、废弃或撤回 |
| 安装维护 | `/installations/preflight`、`/installations/plan`、`/installations`、`/installations/update`、`/installations/uninstall` | 安装前检查、计划、结果上报与维护 |
| 文件传输 | `/transfers/upload/{ticket}`、`/transfers/download/{ticket}` | 120 秒一次性、按主体和资源绑定的二进制传输 |
| 组织管理 | `/admin/users`、`/admin/teams`、`/admin/teams/{id}/members` | 账号、角色、团队和成员管理 |
| 反馈和授权 | `/issues`、`/skills/{id}/ratings`、`/recommendations`、`/oauth/grants`、`/audit-events` | 反馈处理、评分、规则推荐、连接撤销与审计 |
| 使用统计 | `GET /analytics`、`GET /skills/{id}/stats` | 当前授权范围内的汇总与逐技能统计 |

上表除首个完整路径外，REST 业务路径均以 `/api/v1` 为前缀；OAuth 标准路由独立位于 `/oauth/*` 与 `/.well-known/*`。

审核决定只允许经过 CSRF 校验的 Web 会话，不能用 MCP Bearer 凭据绕到 REST 批准自己的上传。

## 使用与下载统计

```http
GET /api/v1/analytics?days=30
GET /api/v1/skills/git-commit-guide/stats?days=30
```

`days` 为 1～365。响应包含 `period_days`、`from`、`totals`、`items`，每一行都有 Skill ID、显示名、团队及以下数值：

- `detail_views`：成功调用详情读取。
- `content_fetches`：成功读取 SKILL.md 或文本附件；安装计划内部的读取不额外计数。
- `downloads`：成功兑换下载票据且归档完整性检查通过。不是链接签发量，也不保证客户端最终保存完成。
- `installations`：Agent 成功上报写入/发现，按安装 ID 去重；更新属于新的安装记录。
- `discoveries`：Agent 上报客户端发现，按安装 ID 去重。
- `favorites`：当前有效收藏数，非时间窗口内新增量。

重放、失败、无权限访问和纯安装前检查不增加下载/安装成功数。同一安装从 written 更新到 discovered 只计一次安装。数据从功能启用后开始记录，不根据旧审计推测历史值。

平台不会将正文获取次数解释为离线实际执行次数。统计查询不返回账号标识、工作区路径、Token 或传输票据；ACL 变化在下一次统计请求生效。
