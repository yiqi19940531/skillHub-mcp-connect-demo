# 企业 Skill Hub + MCP 本机 PoC 开发与验收计划书（V1.1）

确认日期：2026-10-19。本文记录用户在 Plan 阶段确认的需求、澄清、接口边界和验收依据；附录保留原始 V1.0 文档全文。

## 一、目标、范围与文档优先级

### 1.1 项目目标

建设本机运行的企业 Skill 平台，让员工通过 Web 或 MCP，以自己的真实身份发现、获取、安装、上传和共享 Skill，并通过统一权限实现团队隔离。

必须完成：

1. 使用闭环：授权 MCP → 搜索获授权 Skill → 获取安装计划 → Agent 使用自身能力校验并安装 → 客户端发现 → 上报结果。
2. 共享闭环：Web/Agent 上传 → 草稿与文件检查 → 提交审核 → 批准发布 → 获授权成员检索安装。
3. 维护闭环：发布新版本 → 检查更新 → Agent 按用户意图更新/卸载 → 记录执行结果。
4. 治理闭环：维护账号、团队、成员、角色 → 审批共享 → 管理收藏集 → 处理反馈 → 查询审计。

平台托管文件和管理授权，本地文件由 Agent 操作。下载地址、计划或自报结果不等于服务端验证了本地安装。

### 1.2 已确认决策

| 事项 | 结论 |
| --- | --- |
| 功能范围 | P0 与 P1 全部交付，分阶段验收 |
| 必验客户端 | Qoder IDE、Codex 桌面端 |
| 其他客户端 | 保留 Qoder CLI、Cursor、Claude Code 配置和适配设计，不作为首版强制实测目标 |
| 管理功能 | 可创建/停用/恢复账号、重置密码、调整平台角色，创建/归档/恢复团队及调整成员角色 |
| Skill 名称 | 全平台唯一；同名更新须有维护权，并明确关联已有 Skill ID |
| 内容发布 | 平台管理员或 Reviewer 审批；作者、上传者及申请人不能自审 |
| 跨团队和个人共享 | 所属团队 TeamOwner 审批，平台管理员兜底 |
| 企业范围共享 | 平台管理员审批 |
| 原文纳入 | 全文附录，并映射功能和验收 |
| 部署定位 | 本机、单进程、文件持久化 PoC |

### 1.3 文档解释规则

- 正文明确的澄清、补充和调整优先于原文；未明确的部分沿用附录逻辑。
- P0/P1 表示实施顺序，P1 属于本次交付范围。
- 客户端强制验收安排以上表取代原文。
- 后续澄清更新本文件的决策、接口、任务与验收，不静默扩大或缩减范围。
- 附录中的开发 Agent 任务指令属于原文，受上述优先级约束。
- 原文基线另存 `docs/baseline/Enterprise_Skill_Hub_Local_MCP_Implementation_Plan_20261018.md`，SHA-256 为 `4701e133f667b6d42c95beff2fc6b77e76dbadd93c7ef92f04dd9e2cfe9965cb`。

## 二、完整功能与业务规则

### 2.1 功能映射

| 功能域 | 原文 | 交付内容 | 阶段 |
| --- | --- | --- | --- |
| 运行存储 | §2、§3、§14 | 单端口 Web/REST/MCP/OAuth，JSON/NDJSON/ZIP，启动与重置 | 0 |
| 身份授权 | §4、§6 | Web 登录、OAuth、真实主体、角色/团队 ACL、切换与撤销 | 1 |
| 发现 | §5、§7、§10 | 分类、搜索、标签、团队筛选、详情、版本、文件预览 | 2 |
| 收藏与集合 | §5.4、§7、§10 | 个人收藏、团队收藏集与成员维护 | 2、4 |
| 组织管理 | §4、§10 | 账号、团队、成员、角色的真实管理操作 | 2 |
| 安装与传输 | §8 | 单文件/ZIP、票据、哈希、目录指引、收据与结果上报 | 3 |
| 上传发布 | §9 | Web/Agent 上传、草稿、检查、审核、版本发布 | 3 |
| 共享生命周期 | §4.2、§7.2、§9.4 | 共享申请审批、收回、废弃、撤回、即时权限 | 3、4 |
| 安装维护 | §7.2 | 预检查、已装记录、检查更新、更新/卸载计划 | 4 |
| 评分反馈推荐 | §7.2 | 版本评分、问题与处理、关键词标签规则推荐 | 4 |
| 安全审计 | §3.1、§8.6、§9.3、§16 | 全入口鉴权、归档安全、脱敏、事务恢复 | 全阶段 |
| 演示数据 | §4、§5 | 原定账号、业务团队、分类、8 个 Skill、收藏数据 | 0、2 |
| 文档验收 | §13、§15、最终清单 | 原文 T01～T20、扩展 T21～T36、客户端证据、手册 | 5 |

### 2.2 身份、团队、权限

Web 密码登录使用 HttpOnly/SameSite Cookie，写请求验证 CSRF。MCP 使用 Authorization Code + PKCE S256，主体来自已验证 Token 的 sub，不能使用 Cookie 冒充 Token。浏览器切换用户不改变旧 MCP 身份。

REST/MCP 共用授权服务，搜索、计数、详情、版本、文件、下载、上传、收藏与审批逐次检查。支持 private、team、enterprise、custom；custom 可授权团队或个人。成员维护自己的上传；TeamOwner 管理团队集合并审批限定范围共享；平台管理员管理组织与全局治理。

移除成员、停用账号、调整角色或收回 ACL 在后续请求生效。停用和密码重置撤销会话与凭据。禁止移除最后一位有效平台管理员；管理员可配置独立 Reviewer。TeamOwner 自己提出的共享请求由平台管理员处理。

### 2.3 Skill、版本、审核

name 按 Agent Skills 格式校验，全平台唯一，创建后不直接改名；中文标题使用 display_name。无权者不能借同名更新原对象，冲突响应不返回原对象详情。

发布文件、清单、摘要不可修改。版本生命周期为 draft → pending_review → published，或 rejected；发布后可 deprecated/revoked。草稿与驳回版本可编辑重审，待审版本冻结，审批绑定内容摘要与修订号。新版本待审时旧发布版继续可用，批准后更新当前发布版。

默认发现和安装仅使用 published；废弃保留历史说明，撤回停止新下载和安装。作者能看自己的非发布内容，其他成员不能越权读取。预置 8 个 1.0.0 版本明确标记为种子发布，普通上传不能走种子捷径。

### 2.4 共享、收藏、团队资产

扩大跨团队/个人范围须 TeamOwner 或管理员批准；企业可见须管理员批准。作者和管理员可直接收回既有共享。共享不转移作者或维护权。

个人收藏仅本人可见。团队集合支持创建、重命名、归档、增删 Skill，由负责人/管理员维护。加入集合不扩大 Skill ACL，添加检查受众权限，读取时重新过滤内容与计数。

团队归档保留历史和已有资产，停止该团队的新上传与管理写入；恢复后继续维护。首版不做账号/团队物理删除。

### 2.5 安装、更新、卸载

| 客户端 | 项目级 | 用户级 |
| --- | --- | --- |
| Qoder IDE | .qoder/skills/&lt;name&gt;/ | ~/.qoder/skills/&lt;name&gt;/ |
| Codex | .agents/skills/&lt;name&gt;/ | ~/.agents/skills/&lt;name&gt;/ |

install_skill 返回授权来源、版本、清单、哈希、目标和步骤；简短文本可 inline，多文件/二进制用 ZIP。Agent 确定自己的工作区、临时下载、校验摘要/路径/链接、写入并验证；不执行脚本。

明确要求装到当前项目的自然语言视为该意图授权，路径不清、覆盖或额外目录另行确认。同名、本地修改、额外文件不得静默覆盖/删除。安装后保存 .skill-hub-install.json，记录来源、Skill、版本和文件摘要，不保存凭据。

更新比较发布版本和安装记录；Agent 核对原清单，必要时确认、备份。卸载仅处理收据列出的文件；无收据不自动认领。服务端状态始终 agent_reported，分别记录文件写入和客户端发现；不扫描任意客户端路径，不强制远程收回离线文件。

### 2.6 上传、安全及增强

Web 支持 SKILL.md/ZIP；Agent 支持文本和“申请会话 → 上传 ZIP → 提交草稿”，不做分片续传。元数据覆盖分类、标签、显示名称、描述、自定义 ACL 和更新目标 ID，主体强制来自身份上下文。

ZIP 最大 2 MiB，展开 10 MiB，100 文件。拒绝路径穿越、链接逃逸、重复/大小写冲突和压缩炸弹。高置信度凭据拒绝，可疑内容人工审核，脚本允许保存但不执行。扫描能力按具体规则验证，不宣称覆盖所有风险。

评分为本人对授权发布版本的 1～5 分，重复评分更新本人记录。反馈含类型、描述和 open/in_progress/resolved/closed 状态，作者和管理员处理。推荐先 ACL 再名称/标签/描述匹配并说明理由，不使用模型或向量库。最近按发布时间，热门按已有收藏等简单规则。

## 三、架构与接口

Python 3.12、FastAPI、Pydantic；React、Vite、TypeScript、Tailwind CSS；官方 mcp==2.3.0；全部依赖锁定。一个 Uvicorn Worker 在 127.0.0.1:8765 提供 /app、/api/v1、/mcp、OAuth 和发现。授权服务与 MCP 资源服务职责分离、同进程运行。MCP 生命周期由顶层 ASGI 管理，端点不能重复成为 /mcp/mcp。首次准备依赖后，一条命令启动。以 macOS 本机验收为准，其他部署范围沿用原文排除项。

### 3.1 OAuth 与凭据

提供根及 /mcp 的资源元数据、授权服务器元数据、授权页、Token 和 DCR。采用 public client DCR，保留预注册兜底，不广告未实现 CIMD。

授权码一次使用、短时有效，验证 PKCE、客户端、回调、resource、scope。回调精确匹配主机路径，原生 loopback 端口允许按规范变化。响应包含一致 iss，Token 绑定本 MCP 资源。

Access Token 30 分钟；Refresh 7 天并轮换，服务端保存哈希和撤销状态；签名密钥持久化受文件权限保护。有效 Access/Refresh 重启保留，未完成码和票据失效。Web 注销不自动注销 MCP，用户可撤销连接；停用和密码重置撤销账号凭据。

传输票据 120 秒、一次使用、绑定用户和资源，兑换重查权限。Agent 不把 OAuth Token 放进对话或 Shell；URL 票据、授权码、密码、Token 从访问与异常日志脱敏。

### 3.2 全部 MCP 工具

| 分组 | 工具 |
| --- | --- |
| 身份分类 | whoami、list_my_teams、list_skill_categories |
| 发现读取 | list_skills、search_skills、get_skill、get_skill_instructions、get_skill_file、list_skill_versions |
| 个人收藏 | list_favorites、add_favorite、remove_favorite |
| 团队集合 | list_collections、list_collection_skills、add_skill_to_collection、remove_skill_from_collection |
| 安装维护 | get_skill_install_plan、install_skill、report_install_result、check_skill_updates、update_skill、uninstall_skill、list_installed_skills |
| 上传审核 | prepare_skill_upload、upload_skill、request_skill_review、get_skill_review_status、list_my_uploads |
| 共享反馈 | share_skill、rate_skill、report_skill_issue、recommend_skills |

合计 32 个。纯预检查不签票据、不记安装；安装/更新/卸载返回计划；share_skill 只发申请，不通过 MCP 审批；上报关联 installation_id 和操作类型。上传及上报可用 request_id 关联重试，避免重复创建。统一业务响应和错误结构沿用原文；HTTP/OAuth/文件传输保持各自协议格式。

### 3.3 REST、数据与 Web

保留原文 §11 接口，补齐用户/团队/成员/角色管理，Skill 元数据/生命周期/我的上传/下载票据，共享申请审批与收回，集合管理，安装维护，评分反馈推荐，授权连接查询撤销。

数据沿用原文，新增 ShareRequest、Rating、Issue、上传会话和票据；安装记录有操作、工作区、清单摘要、写入和发现状态。采用进程锁、文件锁、revision、临时文件、fsync 和原子替换。多文件变更使用 redo journal 恢复，启动完成恢复后才接受请求。

Web 覆盖原文全部页面，并增加共享、评分、反馈、版本维护、授权管理和安装记录。Markdown 不执行不安全 HTML；所有页面有加载、空状态、失败和权限说明。API 参数以当前 OpenAPI 与 MCP_TOOLS.md 为实现接口记录。

## 四、阶段、测试与交付

| 阶段 | 交付与门槛 | 估算 |
| --- | --- | --- |
| 0 | 骨架、存储、种子、构建托管；同端口、幂等、重启持久化 | 1 天 |
| 1 | Web/OAuth/ACL；两目标客户端真实身份及切换 | 3～5 天 |
| 2 | 发现、详情、收藏、团队库与基础管理；入口权限一致 | 3～4 天 |
| 3 | 安装、传输、上传、安全与发布；真实使用/共享闭环 | 4～5 天 |
| 4 | 全部 P1：更新卸载、记录、共享、评分反馈推荐 | 3～5 天 |
| 5 | 完整回归、两客户端实测、截图、手册、备份重置说明 | 2～3 天 |

单人经验估算 16～23 工作日，另留 3～5 天客户端调试，不作固定日期承诺。每阶段先业务、权限和自动化，再对应页面；两客户端 OAuth 应早验证。

### 4.1 验收

原文 T01～T20 全保留，客户端项扩展至 Qoder IDE、Codex 桌面端。自动化验证接口/权限/安全/恢复；Playwright 验证登录切换、收藏、上传审核、管理及共享；真实桌面端记录版本、授权主体、工具结果、文件与发现证据。SDK 内存调用、模拟 Agent 或 CLI 不能冒充桌面验收。

扩展 T21 Codex 完整闭环；T22 全局同名与并发；T23 新版本待审保留旧版；T24 权限即时变更与票据；T25 组织管理和最后管理员；T26 共享审批边界与自审；T27 纯预检查无副作用；T28 更新与本地修改；T29 卸载保护额外文件；T30 本人安装记录；T31 收藏集动态 ACL；T32 评分反馈推荐；T33 OAuth/票据重放；T34 重启与事务恢复；T35 管理员也不能自审；T36 撤回废弃不伪称远程收回。

实际完成状态与证据单独记录在 ACCEPTANCE.md；未实测项目必须保留待验状态。

### 4.2 交付物

- 可运行源码、锁定依赖、统一启动脚本，共用业务服务的 REST 与 32 工具。
- 5 演示账号、4 业务团队、7 类、8 Skill 及收藏数据；测试成员按管理页或隔离测试创建。
- 两必验客户端接入说明、版本、结果与证据；自动化用例和 T01～T36 状态。
- README、配置示例、幂等种子、显式确认重置、本机备份说明。
- 本计划、澄清和功能映射、原始文档全文附录及独立基线副本。

## 五、附录 A：原始文档全文

以下保持原始文档内容，冲突按正文澄清执行。

<details>
<summary>原始 V1.0 需求全文</summary>

# 企业 Skill Hub + MCP 本机 PoC 实施方案（V1.0）

> 编制日期：2026-10-18  
> 交付类型：可直接用于项目开发、分阶段验收的实施文档  
> 当前定位：单机演示 / 开发验证（PoC），不是生产级企业 IAM 或大规模共享部署  
> 对接目标：Qoder、Cursor、Claude Code，其他支持 MCP 的 Agent 可按同一协议验证

## 0. 本版相较此前规划的调整

此文档承接此前的《企业级 Skill Hub + MCP 接入技术方案 V2.0》，但根据本次要求明确收敛架构：

1. 保留一个有实际交互的 Web Skill 平台，支持账号密码登录、分类浏览、搜索、团队隔离、收藏、上传、审核及共享。
2. 保留独立 MCP HTTP 接入地址，面向 Coding Agent 暴露 Skill 查询、获取、安装计划、上传、收藏、团队及身份相关工具。
3. MCP 接入时应打开浏览器进行 OAuth 登录；登录后 MCP 使用该用户身份，不允许匿名复用管理员身份。
4. 不开发独立的本地安装 CLI 或 Sync Adapter。安装、更新与上传时，由 *Agent 自身已有的文件读写/终端能力* 完成实际本地操作；MCP 提供经过授权的内容、下载/上传凭据、路径建议及清晰的执行步骤。
5. 不部署 MySQL、PostgreSQL、Redis、OSS、OpenSearch 或额外数据库服务。全部测试数据、用户及 Skill 内容持久化为本机 JSON / NDJSON / 目录 / ZIP 文件。
6. 项目运行在本机，一个 Python Web/ASGI 进程同时提供 Web API、静态前端和 MCP HTTP 服务。开发阶段前端热更新可临时启用 Vite 服务。
7. 预置几名演示账号、团队、分类、简短 Skill、团队收藏集和个人收藏记录，启动后即可验证完整功能。

### 本期设计原则

- *先保证端到端真实可用*：Web 能登录，MCP 能拉起授权，权限可隔离，Agent 能真实安装一个 `SKILL.md`，员工能上传共享一个 Skill。
- *拒绝伪成功*：远程 MCP 不因返回 ZIP URL 就声称完成本地安装；必须区分“操作指引已生成 / Agent 已执行 / 已验证”。
- *所有权限由服务端判定*：不能相信 Agent 自报的用户名、团队和资源权限。
- *Skill 内容是文件，不是执行服务*：本平台托管、下载、检索 Skill，不在服务端执行 Skill 中的脚本。

---

## 1. 功能范围与验收目标

| 领域 | 必须完成的 PoC 能力 | 本期不做 |
| --- | --- | --- |
| 身份 | Web 密码登录、MCP OAuth 浏览器授权、`whoami`、注销、切换演示用户 | 对接真实 AD/LDAP/企业微信/钉钉 SSO |
| 团队 | 多团队、成员归属、团队管理员、跨团队 ACL、个人与团队视图隔离 | 多企业租户及复杂组织目录同步 |
| 发现 | 全部已授权 Skill、分类列表、关键词搜索、标签筛选、团队筛选、详情、版本 | 向量数据库、复杂语义搜索 |
| 下载与安装 | MCP 返回受控下载内容与操作指引；Agent 安装到原生目录；校验与结果上报 | 自研安装 CLI、守护进程或系统级自动下发 |
| 上传共享 | Web 上传 ZIP/SKILL.md；Agent 将本地文件上传；指定目标团队；草稿审核发布 | 任意外部 Git 仓库自动抓取与同步 |
| 收藏 | 个人收藏、团队收藏集、收藏集内 Skill 管理 | 个性化推荐模型 |
| 治理 | 草稿/待审核/已发布/驳回/撤回、版本号、基础审核、审计日志 | 复杂审批引擎、CI 扫描集群 |
| 运维 | 本机一条命令启动、种子数据可重建、自动化测试 | K8s 高可用、对象存储、生产备份体系 |

### 业务闭环验收

- 张三通过浏览器登录 Web 后，只看到企业公共 Skill、研发一组 Skill 以及明确共享给自己的内容。
- 李四登录同一套 Web 或 MCP 后，看到研发二组的 Skill，而无法读取研发一组的私有 Skill。
- Qoder 或 Cursor 配置 `http://127.0.0.1:8765/mcp` 后，可以通过浏览器完成登录，调用 `whoami` 得到实际登录用户。
- Agent 可以搜索并安装一个已授权 Skill 到当前项目原生 Skill 目录，文件真实存在且客户端可以识别。
- 张三让 Agent 将项目中的一个简短 `SKILL.md` 上传到研发一组，管理员通过 Web 审核后，组内其他成员可以搜索到；组外无权看到。
- 用户可浏览分类、个人收藏、团队收藏集，并能安装收藏集内的 Skill。

---

## 2. 总体架构

```text
┌────────────────────────────────────────────────────────────────────┐
│                       同一台开发 / 演示电脑                        │
│                                                                    │
│  浏览器（Web）                Qoder / Cursor / Claude Code          │
│         │                              │                           │
│         │ HTTP + Cookie                │ MCP Streamable HTTP       │
│         │                              │ OAuth 浏览器跳转          │
│         └──────────────┬───────────────┘                           │
│                        ▼                                           │
│              http://127.0.0.1:8765                                 │
│        ┌─────────────────────────────────────────┐                 │
│        │              FastAPI / ASGI             │                 │
│        │  /app      Web 静态页面 / 前端           │                 │
│        │  /api/v1   Web / 文件传输 / 管理 REST    │                 │
│        │  /mcp      MCP Server (Tools)            │                 │
│        │  /oauth/*  OAuth / Browser Login         │                 │
│        └───────────────┬─────────────────────────┘                 │
│                        │                                           │
│       ┌────────────────┼─────────────────────────────┐             │
│       ▼                ▼                             ▼             │
│  Identity / ACL   Skill Registry               Review / Audit      │
│       │                │                             │             │
│       └────────────────┼─────────────────────────────┘             │
│                        ▼                                           │
│                  本地 ./data/                                      │
│  users.json / teams.json / skills.json / favorites.json           │
│  versions.json / oauth/*.json / audit.ndjson                      │
│  bundles/*.zip / expanded/*/SKILL.md / staging/                   │
│                                                                    │
│  Agent 经确认后，自行使用已具备的文件工具 / 终端：                    │
│  授权获取文件 → 校验 → 写入本地 ~/.qoder/skills 等目录               │
└────────────────────────────────────────────────────────────────────┘
```

### 2.1 为什么仍然需要 REST API

MCP 用来告诉 Agent “有什么 Skill、你能否使用、如何安全下载或上传”；Web 页面、浏览器登录、二进制 ZIP 文件传输与管理操作更适合 REST。REST 和 MCP 必须共用 *同一套* 用户身份、Skill 元数据、ACL 以及审计服务，避免同一用户在两个入口看到不同的权限。

### 2.2 运行边界

- PoC 默认 `127.0.0.1:8765`，只向本机提供服务，不暴露公网。
- Agent 和浏览器都需要能访问该地址。如果 Agent 在容器、远程工作区或云端，`127.0.0.1` 指向的是它自己的环境，不能直接访问开发电脑；这类环境需要反向代理、可达域名及 HTTPS，并单独验证 OAuth 回调。
- 本文仅保证本机 PoC 设计；跨设备、生产部署属于后续范围。

---

## 3. 技术栈与项目结构

| 层次 | 推荐选型 | 原因 |
| --- | --- | --- |
| 前端 | React + Vite + TypeScript | 便于做浏览、分类、收藏、上传、权限管理等页面 |
| UI | Tailwind CSS 或简洁组件库 | 构建可演示的企业内部 Skill Marketplace |
| 后端 | Python 3.11+、FastAPI、Pydantic | REST + 静态文件 + ASGI 统一运行 |
| MCP | 官方 MCP Python SDK、Streamable HTTP | 支持通用 MCP Tools、HTTP Auth 中间件与协议发现 |
| OAuth | 使用官方 SDK 授权组件/示例改造为本机文件持久化的授权服务 | 支持 OAuth Authorization Code + PKCE、令牌校验及用户身份 |
| 本地存储 | JSON、NDJSON、ZIP、目录、文件锁 | 免独立数据库服务，方便检查与重置 |
| 搜索 | Python 字符串/关键词匹配、标签与分类过滤 | 8~30 个演示 Skill 足够，后续可换索引 |
| 测试 | pytest + httpx、Playwright（可选） | 权限、OAuth、接口和 Web 自动化验证 |

> 开发前锁定 SDK 版本，并对照对应版本的 OAuth / ASGI 接口实现，不要假定不同版本中 `FastMCP`、`MCPServer` 的鉴权构造参数完全相同。可优先参考 MCP 官方 Python SDK 的 simple-auth 和 OAuth story 示例。

### 建议目录结构

```text
enterprise-skill-hub/
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml                 # 或 requirements.txt
├── backend/
│   └── app/
│       ├── main.py                # 统一 ASGI 入口
│       ├── config.py
│       ├── auth/                  # Web 登录、OAuth、令牌验证
│       ├── api/                   # REST routers
│       ├── mcp/                   # MCP 工具声明与实现
│       ├── models/                # Pydantic Schemas
│       ├── services/              # Skill、团队、权限、版本、审核、收藏
│       ├── storage/               # JSON repository、原子写、文件锁
│       └── security/              # 上传校验、路径检查、哈希、票据
├── frontend/
│   ├── src/
│   │   ├── pages/                # 登录、市场、详情、收藏、团队、上传、审核
│   │   ├── components/
│   │   ├── api/
│   │   └── App.tsx
│   └── dist/                      # 构建后由 FastAPI 静态提供
├── scripts/
│   ├── seed_demo.py              # 幂等预置演示数据
│   └── reset_demo.py             # 明确确认后重置（不得静默清数据）
├── seed/
│   ├── users.example.json
│   ├── teams.example.json
│   └── skills/                   # 8 个极简 SKILL.md 示例
├── data/                         # 运行时本地持久化；不提交 Git
│   ├── users.json
│   ├── teams.json
│   ├── memberships.json
│   ├── categories.json
│   ├── skills.json
│   ├── versions.json
│   ├── collections.json
│   ├── favorites.json
│   ├── reviews.json
│   ├── installations.json
│   ├── oauth/                     # 注册客户端、授权码、token 状态
│   ├── secrets/                   # 本机签名秘钥，chmod 600
│   ├── bundles/<skill-id>/<version>.zip
│   ├── expanded/<skill-id>/<version>/SKILL.md
│   ├── staging/                   # 未审核上传包隔离存放
│   └── audit.ndjson
└── tests/
    ├── test_auth_oauth.py
    ├── test_acl.py
    ├── test_registry.py
    ├── test_mcp_tools.py
    ├── test_install_upload.py
    └── test_web_flow.py
```

### 3.1 JSON 并发策略

- 仅运行 *一个* Uvicorn Worker，禁止多进程并发写同一个 JSON 文件。
- 更新时使用进程内写锁 + 文件锁，对文件先写临时文件、`fsync` 后原子替换，避免部分写入。
- 修改 ACL、收藏、审批等操作采用“加载 → 校验版本 → 更新 → 原子替换”的事务式流程。
- 审计采用追加写入 NDJSON；不得把密码、完整 OAuth Token 或下载票据写入日志。
- 种子初始化必须幂等；已有演示修改不得在每次启动时被覆盖。
- JSON 是本地轻量 PoC 方案，不承诺跨进程事务和高并发；后续生产化再替换数据库层。

---

## 4. 演示身份、组织与授权

### 4.1 预置登录账号

所有账号仅供本机测试。开发初始化时使用 Argon2id（或同等级密码哈希算法）存储密码哈希，不能把下表的密码明文写进运行时 `users.json`。首次运行须在控制台明确提示“演示账号，禁止公网暴露”。

| 账号 | 显示姓名 | 初始密码（仅演示） | 团队 | 角色 |
| --- | --- | --- | --- | --- |
| `admin` | 平台管理员 | `Admin@123456` | 平台管理 | PlatformAdmin / Reviewer |
| `zhangsan` | 张三 | `ZhangSan@123456` | 研发一组 | Member / SkillAuthor |
| `lisi` | 李四 | `LiSi@123456` | 研发二组 | TeamOwner / SkillAuthor |
| `wangwu` | 王五 | `WangWu@123456` | 运维组 | Member / SkillAuthor |
| `zhaoliu` | 赵六 | `ZhaoLiu@123456` | AI 应用组 | Member / SkillAuthor |

企业（演示租户）统一固定为 `demo-company`；用户主键采用内部 ID，用户名称仅作显示，不作为权限主键。

### 4.2 权限与可见性

- Skill 归属一个创建人和一个管理团队；可以额外授权其他团队或个人。
- 可见性：`private`、`team`、`enterprise`、`custom`。
- 动作：`list`、`read`、`download`、`install`、`create`、`edit`、`share`、`review`、`publish`、`revoke`、`favorite`、`collection:manage`。
- 成员可创建自己的草稿；是否可发布由管理团队 Reviewer 决定。
- TeamOwner 可以管理其团队的收藏集，审核/邀请须经过具有相应权限的后端规则；本期默认平台管理员负责最终发布审批。
- 个人收藏仅当前用户可读；团队收藏集仅被授权团队成员可查看和维护。
- 服务端搜索先筛选 ACL，再对授权集排序；详情、文件读取、版本包下载、安装票据签发都必须再次鉴权。
- 不可见对象通过统一的 `SKILL_NOT_FOUND_OR_NOT_ACCESSIBLE` 响应避免泄露名称和存在性。
- 发布或编辑时不能靠传 `user_id` 冒充作者，`created_by` 等字段强制来自 Token 中的 `sub`。

### 4.3 账号切换特别规则

Web 与 MCP 是 *同一账号体系*，但不等于共享一份浏览器 Cookie/Agent Access Token。浏览器切换为李四后，已授权给张三的 Agent Token 仍然代表张三；必须在客户端断开/重新授权或清理对应会话凭据后才能切换。`whoami` 必须始终报告真正的 Token 主体，而不是浏览器当前用户。

---

## 5. 预置分类、Skill 与收藏集

### 5.1 分类（固定演示数据，可通过 Web 分类筛选）

1. AI Coding
2. Testing / 测试
3. DevOps / 运维
4. Data / 数据
5. AIGC / 内容创作
6. API & MCP
7. Office / 知识与办公

每个 Skill 最少有：`skill_id`、`name`、`display_name`、`description`、`category_id`、`tags`、`owner_user_id`、`owner_team_id`、`visibility`、`version`、`status`、`created_at`。

### 5.2 预置 8 个极简 Skill

| Skill ID | 名称 | 分类 | 可见性 | 预置所有者 |
| --- | --- | --- | --- | --- |
| `java-code-review` | Java 代码审查清单 | AI Coding | 研发一组 | 张三 |
| `python-style-guide` | Python 代码风格提示 | AI Coding | 研发二组 | 李四 |
| `ack-pod-triage` | ACK Pod 故障初排 | DevOps | 运维组 | 王五 |
| `video-summary-outline` | 视频理解摘要大纲 | AIGC | AI 应用组 | 赵六 |
| `unit-test-outline` | 单元测试用例纲要 | Testing | 企业共享 | 管理员 |
| `git-commit-guide` | Git Commit 说明规范 | AI Coding | 企业共享 | 管理员 |
| `mcp-tool-checklist` | MCP 工具设计检查清单 | API & MCP | 企业共享 | 管理员 |
| `data-cleaning-notes` | CSV 数据清理基础流程 | Data | 企业共享 | 管理员 |

上述示例内容只需基本操作要点和安全提示，*不必实现复杂脚本或依赖任何外部服务*。所有 Skill 均预置已发布版本 `1.0.0`，可以下载、安装、查看 `SKILL.md`。

### 5.3 一个最小 `SKILL.md` 示例

```markdown
---
name: java-code-review
description: Review Java changes for readability, null safety, logging and exception handling when checking a pull request.
---

# Java Code Review

1. 先理解改动目标和涉及的 Java 类。
2. 检查异常处理、日志、空指针、资源关闭和可读性。
3. 输出问题位置、影响和可选修改建议。
4. 不自动修改生产配置，不自动提交代码。
```

### 5.4 演示收藏

| 收藏集/收藏 | 归属 | 预置内容 |
| --- | --- | --- |
| `研发一组常用技能` | 研发一组团队收藏集 | `java-code-review`、`git-commit-guide` |
| `研发二组提效工具` | 研发二组团队收藏集 | `python-style-guide`、`unit-test-outline` |
| `运维排障集` | 运维组团队收藏集 | `ack-pod-triage` |
| `张三的收藏` | 张三个人收藏 | `java-code-review`、`mcp-tool-checklist` |
| `李四的收藏` | 李四个人收藏 | `python-style-guide`、`git-commit-guide` |

收藏集 `collection_id` 与 Skill ID 分开存储，方便未来同一个 Skill 出现在多个团队集合中。添加到集合不自动改变 Skill 自身 ACL；添加前后均要确认被集合成员具备访问权。

---

## 6. 登录与 MCP OAuth 方案（重点）

### 6.1 Web 登录

1. 浏览器打开 `http://127.0.0.1:8765/app/login`。
2. 输入 `zhangsan` 和其演示密码，后端验证 Argon2id 哈希。
3. 登录成功后创建 HttpOnly、SameSite Cookie 会话（本机 HTTP 演示场景）。
4. 跳到 Skill 市场，显示当前姓名和团队；调用 `/api/v1/me` 得到身份。
5. 页面可退出登录并切换李四、王五；写操作必须校验 CSRF 或使用等效保护。

### 6.2 MCP 登录：必须采用浏览器 OAuth 授权

> `login(username,password)` 不作为 MCP Tool。不要把用户密码传给 Agent，也不要把用户名硬编码在 `mcp.json` 中。

推荐把 OAuth *授权服务* 与 MCP *资源服务* 部署在同一个 FastAPI/ASGI 地址下，但仍区分两者职责：授权服务负责密码登录、授权码和 Token；MCP 负责检查 Token 和权限。这不需要额外部署进程。

```text
Agent 客户端 → GET/POST /mcp（尚未带 Token）
              ← 401 + WWW-Authenticate / 资源元数据地址
Agent 客户端 → 读取 OAuth Protected Resource Metadata
Agent 客户端 → 读取 Authorization Server Metadata
Agent 客户端 → OAuth Authorization Code + PKCE (S256)
              → 打开浏览器 /oauth/authorize
浏览器        → 登录本机演示账号（张三/李四等）
              → 明确授权给当前 MCP 客户端
授权服务      → 重定向到客户端预注册回调 URI（携带 code 和 state）
Agent 客户端 → /oauth/token + code_verifier 换取 Access Token
Agent 客户端 → /mcp (Authorization: Bearer ...)
MCP 服务     → 校验 Token 的 iss/aud/sub/exp/scope，再执行 ACL
Agent        → whoami 返回对应用户和团队
```

实现要点：

- 提供 `/.well-known/oauth-protected-resource`（以及所使用 SDK 针对 `/mcp` 的规范发现路径）、`/.well-known/oauth-authorization-server`、`/oauth/authorize`、`/oauth/token`；若客户端要求动态注册/Client ID Metadata，则按兼容性增加注册与元数据能力。
- 必须支持 Authorization Code + PKCE S256、`state` 绑定、一次性短时效授权码、精确回调 URI 校验；访问令牌带有 `aud`（指向本 MCP 服务）、`sub`（真实 user_id）、`scope`、`exp`。
- Web Cookie 只用于网页登录和授权确认页；MCP API 不接受 Web Cookie 冒充 Bearer Token。
- 优先支持公开客户端注册（DCR 或所选协议版本支持的 Client ID Metadata），同时保留为特定客户端预注册 public client ID 的回退方案；*不要*把客户端 Secret 写进 Agent 对话。
- 本机 HTTP 仅限 loopback 测试。绑定其他网卡或对外提供服务时必须改为 HTTPS，并配置正式地址、回调 URI、Cookie Secure 与可信主机检查。
- 禁止把 OAuth Access Token 交给 LLM 输出或拼入 Agent 即将执行的 Shell 命令。
- Token、刷新凭据、授权码的服务端存储必须最小化并受文件权限保护；重启后已签发有效 Token 的处理方式需要在初始化时明确。
- Token 主体停用、团队变更和 ACL 变更应在后续 MCP 请求时重新生效。

### 6.3 不同客户端验证

| 客户端 | MCP 地址/方式 | OAuth 验证内容 |
| --- | --- | --- |
| Qoder IDE | 在 MCP 配置页添加 `http://127.0.0.1:8765/mcp` | 是否自动开启浏览器、令牌回传与重新加载工具 |
| Qoder CLI | Streamable HTTP，按官方 `mcpServers` 格式 | OAuth metadata、PKCE/回调与 `whoami` |
| Cursor | `~/.cursor/mcp.json` 中的 `url` | 自动 OAuth、DCR/静态 client ID 回退、当前账号 |
| Claude Code | `claude mcp add --transport http enterprise-skills http://127.0.0.1:8765/mcp` | `/mcp` 认证、登录跳转、工具发现 |

参考的配置方向（Cursor）：

```json
{
  "mcpServers": {
    "enterprise-skills": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

如个别版本不触发 OAuth，需要先检查该客户端对 HTTP loopback/发现路径/回调 URI 的支持，并使用该客户端允许的静态 OAuth 客户端配置方式；不可直接降级为所有成员共享一个固定管理员 Token。

---

## 7. MCP Tool 实施清单

所有 MCP Tool 都通过 SDK 的 `tools/list` 暴露，以 `tools/call` 调用。根据用途分成默认读取型与需用户确认的变更型；Tool 名称是本项目自行约定，并非已存在的 Qoder 官方接口。

### 7.1 必须完成 P0

| Tool | 参数（关键字段） | 返回/行为 | 权限 |
| --- | --- | --- | --- |
| `whoami` | 无 | `user_id`、`username`、`display_name`、`teams`、角色 | 已登录 |
| `list_my_teams` | 无 | 归属/管理团队 | 已登录 |
| `list_skill_categories` | 无 | 分类及各分类授权 Skill 数量 | `skill:list` |
| `list_skills` | `category?`、`team_id?`、`cursor?`、`limit?` | 当前用户可见列表 | `skill:list` |
| `search_skills` | `query`、`category?`、`tags?`、`team_id?` | ACL 后的搜索匹配结果 | `skill:list` |
| `get_skill` | `skill_id` | 元数据、风险、版本、获授权操作 | `skill:read` |
| `get_skill_instructions` | `skill_id`、`version?` | `SKILL.md` 正文和完整性信息 | `skill:read` |
| `get_skill_file` | `skill_id`、`version`、`relative_path` | 允许的附属文本内容 | `skill:read` |
| `list_skill_versions` | `skill_id` | 版本列表及发布状态 | `skill:read` |
| `list_favorites` | 无 | 当前用户个人收藏 | 已登录 |
| `add_favorite` | `skill_id` | 添加收藏 | `skill:read` |
| `remove_favorite` | `skill_id` | 取消收藏 | 收藏拥有者 |
| `list_collections` | `team_id?` | 当前用户可见的团队收藏集 | 集合可读 |
| `list_collection_skills` | `collection_id` | 集合内获授权 Skill | 集合可读 + Skill ACL |
| `install_skill` | `skill_id`、`version?`、`client`、`scope` | 返回 *Agent 安装计划*（见第 8 章） | `skill:install` |
| `report_install_result` | `skill_id`、`version`、`client`、`scope`、`status`、`target_path?`、`digest?` | 记录“Agent 自报”的安装状态，不假冒服务端校验 | 已授权用户 |
| `upload_skill` | `team_id`、`visibility`、`skill_md?`、`upload_id?`、`version?` | 小文本直接上传或提交已上传 ZIP，产生草稿 | `skill:create` |
| `prepare_skill_upload` | `team_id`、`filename`、`size`、`sha256` | 二进制上传会话、受限上传入口 | `skill:create` |
| `request_skill_review` | `skill_id`、`version` | 创建审核请求，返回 `review_id` | 作者/管理员 |
| `get_skill_review_status` | `review_id` | 扫描与审核状态 | 作者/Reviewer |

> `install_skill` *不负责在远端服务器写用户电脑的目录*。这个工具的效果是生成任务明确、可安全执行的下载和安装指导；Agent 实际执行并核对文件后再报结果。`upload_skill` 也不直接读取一个由用户字符串指定的任意本地路径。

### 7.2 增强 P1（P0 闭环完成后再做）

| Tool | 作用 |
| --- | --- |
| `get_skill_install_plan` | 仅做安装前检查，无状态变更；也可作为 `install_skill` 的内部实现 |
| `check_skill_updates` | 比较 Agent 上报的安装版本与 Registry 发布版本 |
| `update_skill` | 返回目标版本更新计划，由 Agent 自己落盘 |
| `uninstall_skill` | 提供卸载目标与边界，由 Agent 确认后删除受管理文件 |
| `list_installed_skills` | 列出 Agent 曾上报的安装记录，明确标记为自报状态 |
| `add_skill_to_collection` | TeamOwner 将有权访问的 Skill 纳入团队收藏集 |
| `remove_skill_from_collection` | 移除团队收藏集成员 |
| `share_skill` | Skill Owner 修改授权申请/发起共享（需相应审批） |
| `list_my_uploads` | 个人草稿、送审、发布记录 |
| `rate_skill` | 给授权版本评分 |
| `report_skill_issue` | 上报描述错误、损坏或安全问题 |
| `recommend_skills` | 根据 query 与标签做简单规则推荐（不引入模型/向量库） |

### 7.3 工具返回统一格式

```json
{
  "ok": true,
  "data": {},
  "trace_id": "req_demo_01"
}
```

错误统一为：

```json
{
  "ok": false,
  "error": {
    "code": "SKILL_NOT_FOUND_OR_NOT_ACCESSIBLE",
    "message": "Skill 不存在或当前用户无权访问",
    "retryable": false
  },
  "trace_id": "req_demo_02"
}
```

建议错误码：`UNAUTHENTICATED`、`FORBIDDEN`、`SKILL_NOT_FOUND_OR_NOT_ACCESSIBLE`、`VERSION_NOT_PUBLISHED`、`UPLOAD_INVALID`、`UPLOAD_EXPIRED`、`APPROVAL_REQUIRED`、`INSTALL_ACTION_REQUIRED`、`DIGEST_MISMATCH`、`RATE_LIMITED`。

---

## 8. Agent 自主安装：无独立 CLI Adapter（本项目核心）

### 8.1 前提与边界

- Agent 必须已经具有获用户许可的文件写入能力、终端能力或编辑工作区文件的能力。
- MCP 服务无法凭空给远程 Agent 增加本地写权限：如果客户端禁止写入或运行在云端，必须返回“需要手工操作/切换为有写权限的工作区”，不能标记成功。
- 对已授权的 Skill，后端可提供 `SKILL.md` 文本及文件包，供 Agent 自行按客户端原生目录安装。
- 安装动作本身原则上需要用户确认；Skill 包中的脚本不因安装就自动执行。

### 8.2 `install_skill` 输入示例

```json
{
  "skill_id": "java-code-review",
  "version": "1.0.0",
  "client": "qoder-ide",
  "scope": "project"
}
```

输出示例（字段均为演示结构，Ticket 由运行中的后端实时签发）：

```json
{
  "ok": true,
  "data": {
    "status": "agent_action_required",
    "skill_id": "java-code-review",
    "version": "1.0.0",
    "package": {
      "format": "zip",
      "download_url": "http://127.0.0.1:8765/api/v1/transfers/download/{one_time_ticket}",
      "sha256": "<server-generated-sha256>",
      "expires_in_seconds": 120,
      "max_downloads": 1
    },
    "target": {
      "client": "qoder-ide",
      "scope": "project",
      "base_relative_path": ".qoder/skills",
      "directory_name": "java-code-review"
    },
    "agent_steps": [
      "向用户确认安装位置及同名覆盖策略",
      "使用已有网络/终端能力下载 ZIP；不得执行来自 ZIP 的脚本",
      "比对整个 ZIP 的 SHA-256 和文件清单，验证相对路径安全",
      "将文件写入项目 .qoder/skills/java-code-review/ 目录",
      "检查 SKILL.md 存在且 name 与目录一致",
      "按客户端要求重新加载 Skill 并报告执行结果"
    ],
    "overwrite_policy": "ask_user_if_exists"
  }
}
```

### 8.3 安装步骤（由 Agent 自己执行）

1. 用户：“帮我安装平台里的 Java Code Review Skill 到当前项目。”
2. Agent 调用 `search_skills`，再调用 `install_skill`。
3. MCP 校验 Token、`skill:install`、版本状态，生成短效单次下载票据并返回计划。
4. Agent 基于当前工作区确定 *自己的* 项目根目录，提示用户确认是否安装到当前项目。
5. Agent 利用其已有工具下载到临时位置，按 ZIP `sha256` 和文件清单验证。禁止 Zip Slip、路径穿越、链接逃逸与压缩炸弹。
6. Agent 使用已有文件 API/终端写入目标目录。建议先写临时目录，验证完成后原子替换；存在同名本地 Skill 时先询问，未经确认不得覆盖。
7. Agent 校验目标 `SKILL.md`，按客户端实际加载方式刷新或提示重启；只有文件写入和校验成功后才能声称“已安装到本机”。
8. Agent 调用 `report_install_result`，后端标记 `source=agent_reported`；如果本机平台能够安全检查目标在白名单目录内的实际文件，可增加 `source=server_verified`，但不可假造这个标签。

### 8.4 适配的目标目录（首批）

| Client | 项目级 | 用户级 | 安装后动作 |
| --- | --- | --- | --- |
| Qoder IDE | `.qoder/skills/<name>/` | `~/.qoder/skills/<name>/` | 按 IDE 版本重新加载/重启 |
| Qoder CLI | `.qoder/skills/<name>/` | `~/.qoder/skills/<name>/` | 新会话或 `/skills reload` |
| Cursor | `.cursor/skills/<name>/` | `~/.cursor/skills/<name>/` | 验证 Cursor 实际发现的 Skill |
| Claude Code | `.claude/skills/<name>/` | `~/.claude/skills/<name>/` | 验证 Claude Code 的技能发现 |

首期只承诺本机已实测的客户端/版本组合。特别是 Qoder IDE 和 CLI 的同名优先级及热重载方式可能不同，以实际产品文档和测试结果为准；安装前检查冲突。

### 8.5 单文件安装降级路径

演示 Skill 仅含 `SKILL.md` 或少量文本附件时，可先通过 `get_skill_instructions` / `get_skill_file` 将内容返回给 Agent；Agent 直接在目标目录新建文件，无需打包下载，也无需任何单独的 CLI。超过工具输出大小阈值或包含二进制资源时，再走 ZIP + 一次性下载票据。

### 8.6 下载票据安全控制

- 票据只有在 `install_skill` / 授权下载类 MCP Tool 内检查身份成功后才签发；绑定 user、skill、version、摘要、单次下载和有效期。
- 本机默认 120 秒有效，使用后立即失效；不能拿另一用户的票据下载其他 Skill。
- 票据不能被打印进普通访问日志、URL 预览、分析事件。票据是临时 Bearer 凭据，不允许 Agent 将其提交到代码仓库。
- ZIP 与 SKILL.md 视为不可信内容；下载成功不代表获准执行脚本或生产操作。

---

## 9. Agent 自主上传与团队分享

### 9.1 上传原则

用户可以说：“把当前项目 `./.qoder/skills/my-helper` 的 Skill 上传到研发一组，供团队共享。”

- Agent *自己读取本地文件*，明确展示待上传路径、文件数、目标团队以及可见性供用户确认。
- 后端不可根据 Agent 提供的绝对路径去任意扫描宿主机；Agent 只提交它已经读取、选择并授权上传的内容。
- 用户身份取自 MCP OAuth，不接受客户端直接指定 `created_by=admin` 等信息。
- 上传到团队并不等于立即在企业范围发布：先草稿，后扫描和审核，再进入对该团队可见的已发布状态。

### 9.2 两种上传模式

*模式 A：单个 SKILL.md（优先实现，测试最方便）*

1. Agent 读取本机 `SKILL.md`。
2. Agent 调用 `upload_skill({team_id,visibility:"team",skill_md:"...",version:"0.1.0"})`。
3. 后端验证用户在该 Team 有创建权限，校验 name/description/frontmatter，生成草稿和版本记录。
4. 用户在 Web 的“我的上传”看到草稿，发起审核。

*模式 B：目录 / ZIP（必须实现，第二步闭环）*

1. Agent 用自身文件工具打包指定 Skill 目录，且不得包含 `.env`、凭据、无关项目文件。
2. Agent 调用 `prepare_skill_upload`，取得短时效一次性上传凭据或受控上传地址。
3. Agent 使用已有网络工具通过 `POST /api/v1/transfers/upload/{ticket}` 上传 ZIP（二进制文件不经过大模型文本上下文）。
4. Agent 调用 `upload_skill({team_id,visibility:"team",upload_id,...})` 完成提交；服务端二次鉴权、比对哈希、解包检查后创建草稿。
5. 上传结束后用户通过 `request_skill_review` 或 Web 提交审核；Reviewer 审核通过后发布。

> Web 页面上传沿用相同的后端服务，但使用 Cookie 会话和正常的 Web 上传接口，不绕过校验与审批。

### 9.3 上传包强制检查

- 包内必须有一个有效的 `SKILL.md`，必填 `name`、`description`；`name` 与目录规范保持一致。
- PoC 默认压缩包不超过 2 MiB、解压总量不超过 10 MiB、文件数不超过 100；超过返回 `UPLOAD_INVALID`。
- 禁止绝对路径、`..`、系统特殊文件、软链接/硬链接逃逸、重复覆盖目录以及高压缩比 ZIP 炸弹。
- 扫描典型凭据特征：私钥、API Key、密码配置、云厂商 AK/SK；命中则拒绝或标记待人工审核。
- 有 `scripts/` 时标记风险级；首期允许保存，但绝不自动执行。
- SHA-256 对每个文件与归档记录，发布版本不可变。后续改动必须新建版本。
- 审核人和作者不能自动视为同一人；上传者不具备自审自发权限。

### 9.4 生命周期

`draft → pending_review → published`；异常可进入 `rejected`；发布后可 `deprecated` 或 `revoked`。用户搜索/安装默认仅返回 `published` 版本，作者在“我的上传”可以看到自己草稿。

---

## 10. Web 平台页面与交互

| 页面 | 主要组件 | 重点验收 |
| --- | --- | --- |
| 登录 | 用户名、密码、当前会话提示 | 张三/李四独立登录与退出 |
| 首页 / Skill 市场 | 搜索栏、分类、团队范围、热门/最近列表 | 默认只展示当前用户授权 Skill |
| Skill 详情 | `SKILL.md` 预览、标签、作者、版本、收藏、下载 | 未授权时不能通过 URL 直接访问 |
| 个人收藏 | 收藏/取消收藏、个人列表 | 不串用户数据 |
| 团队 Skill 库 | 团队列表、团队资产、可见性说明 | 仅所属/授权团队可见 |
| 团队收藏集 | 集合卡片、添加/移除 Skill、成员访问 | TeamOwner 管理，普通成员查看 |
| 我的上传 | 草稿、待审核、已发布、驳回原因 | 可提交审核与版本更新 |
| 上传 Skill | 选择 SKILL.md/ZIP、目标 Team、权限、描述 | 未授权团队不能上传 |
| 审核中心 | 待审核项、扫描结果、通过/驳回 | 仅 Reviewer / Admin 可执行 |
| 用户与团队管理 | 演示账号、团队、成员、基础授权 | 管理权限受限、可见真实关系 |
| MCP 接入帮助 | 本机 Endpoint、支持客户端、配置示例、登录说明 | 可复制地址并完成实际授权 |

建议 UI 左侧固定导航：`发现 Skills / 分类 / 我的收藏 / 团队库 / 我的上传 / 审核中心 / 设置`；顶部显示登录姓名、团队与退出按钮。Skill 卡片显示标题、分类、作者、团队、版本和可用操作，避免把未授权的名称、作者等元数据发给前端。

---

## 11. REST API 清单（P0）

以下是平台自定义的 REST 路由；Web、MCP Service 与文件传输共享内部业务函数。除登录与发现元数据外，所有接口都须验证用户身份。

| HTTP | 路由 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 浏览器密码登录、创建会话 |
| `POST` | `/api/v1/auth/logout` | 浏览器退出 |
| `GET` | `/api/v1/me` | 当前身份与角色 |
| `GET` | `/api/v1/teams` | 当前用户授权团队 |
| `GET` | `/api/v1/categories` | 分类与授权计数 |
| `GET` | `/api/v1/skills` | ACL 后搜索、列表、分页 |
| `GET` | `/api/v1/skills/{id}` | Skill 详情 |
| `GET` | `/api/v1/skills/{id}/versions` | 版本 |
| `GET` | `/api/v1/skills/{id}/versions/{version}/files/{path}` | 获授权的文本文件读取，路径规范化 |
| `GET` | `/api/v1/favorites` | 个人收藏 |
| `POST` | `/api/v1/favorites` | 添加收藏 |
| `DELETE` | `/api/v1/favorites/{id}` | 删除收藏 |
| `GET` | `/api/v1/collections` | 团队收藏集 |
| `GET` | `/api/v1/collections/{id}/skills` | 集合内 Skill |
| `POST` | `/api/v1/collections/{id}/skills` | 添加 Skill（有权限者） |
| `DELETE` | `/api/v1/collections/{id}/skills/{skill_id}` | 从集合移除 |
| `POST` | `/api/v1/skills` | 创建草稿 |
| `POST` | `/api/v1/skills/{id}/versions` | 创建新版本/关联上传包 |
| `POST` | `/api/v1/uploads` | Web 上传或创建受控会话 |
| `POST` | `/api/v1/transfers/upload/{ticket}` | 一次性 ZIP 上传 |
| `GET` | `/api/v1/transfers/download/{ticket}` | 一次性已授权 ZIP 下载 |
| `POST` | `/api/v1/skills/{id}/reviews` | 提交审核 |
| `GET` | `/api/v1/reviews` | 待审核列表 |
| `POST` | `/api/v1/reviews/{id}/decision` | 审核通过/驳回 |
| `POST` | `/api/v1/installations` | Agent 上报状态 |
| `GET` | `/api/v1/audit-events` | 管理员审计查询 |

OAuth/发现路由使用适用协议规范中的标准路由：`/.well-known/*`、`/oauth/authorize`、`/oauth/token`，必要时提供客户端注册接口。OAuth 路由不直接复用 Web `/api/v1/auth/login` 交换 Access Token，必须实施正规授权码流程。

### 11.1 REST 与 MCP 共用的服务对象

内部推荐实现以下服务：`IdentityService`、`AuthorizationService`、`TeamService`、`SkillRegistryService`、`SearchService`、`CollectionService`、`TransferService`、`ReviewService`、`AuditService`。

开发中严禁出现两套各自独立的 ACL 筛选实现；REST `/skills` 与 MCP `search_skills` 都应调用相同的 `SearchService.list_authorized(principal, filters)`。

---

## 12. 关键数据模型（本机 JSON Schema 思路）

每条记录至少包含 `id`、`created_at`、`updated_at`，时间使用 ISO 8601 UTC，必要对象有 `revision` 用于乐观锁。

| 对象 | 主要字段 |
| --- | --- |
| `User` | `user_id`、`username`、`display_name`、`password_hash`、`disabled`、`roles[]` |
| `Team` | `team_id`、`name`、`owner_user_id`、`description` |
| `Membership` | `user_id`、`team_id`、`role`、`status` |
| `Skill` | `skill_id`、`name`、`description`、`category_id`、`tags[]`、`owner_user_id`、`owner_team_id`、`visibility`、`acl[]`、`current_version` |
| `SkillVersion` | `skill_id`、`version`、`status`、`bundle_path`、`sha256`、`manifest[]`、`review_id` |
| `Collection` | `collection_id`、`name`、`owner_team_id`、`skill_ids[]`、`acl[]` |
| `Favorite` | `user_id`、`skill_id`、`created_at` |
| `Review` | `review_id`、`skill_id`、`version`、`submitted_by`、`reviewed_by`、`decision`、`reason` |
| `Installation` | `user_id`、`client`、`scope`、`skill_id`、`version`、`status`、`source`、`reported_at` |
| `OAuthClient` | `client_id`、`redirect_uris[]`、`grant_types[]`、`scopes[]`、`registered_at` |
| `AuditEvent` | `request_id`、`actor`、`action`、`target`、`decision`、`result`、`time` |

示例 `Skill`：

```json
{
  "skill_id": "java-code-review",
  "name": "java-code-review",
  "display_name": "Java 代码审查清单",
  "category_id": "ai-coding",
  "tags": ["java", "review", "coding"],
  "owner_user_id": "user-zhangsan",
  "owner_team_id": "team-dev-a",
  "visibility": "team",
  "acl": [],
  "current_version": "1.0.0",
  "status": "published",
  "revision": 1
}
```

服务端读取 Skill 时应独立校验请求者是否属于 `team-dev-a`，不能因为前端展示了这个对象就默认许可。

---

## 13. 分阶段开发任务计划

> 时间为单名有经验开发者的粗略开发工作量参考，不是确定交付承诺。OAuth 客户端行为与本机环境差异可能增加调试时间。

### 阶段 0：项目骨架与运行环境（约 0.5~1 天）

任务：

- [ ] 建立前后端目录、统一启动入口、配置 `.env.example`。
- [ ] FastAPI 提供 `/healthz`、`/api/v1` 和 `/mcp` 预留入口。
- [ ] React 构建后静态产物由 FastAPI 托管。
- [ ] 建立 JSON 文件库抽象与文件锁、基本日志/异常处理。
- [ ] `scripts/seed_demo.py` 写入 5 名用户、4 个业务团队、分类、8 个 Skill 以及收藏集。

完成标准：浏览器能打开登录页和健康检查；重启后演示数据仍在；无需数据库服务。

### 阶段 1：身份、OAuth 与权限内核（约 3~4 天）

任务：

- [ ] Web 登录/退出，密码仅以哈希存储。
- [ ] OAuth 授权服务 + 规范元数据发现 + PKCE + Token 验证；先使用官方 MCP 测试客户端跑通。
- [ ] RBAC/Team ACL 统一中间件。
- [ ] `whoami`、`list_my_teams`，Token 的 `sub` 与 Web 用户对应。
- [ ] 用张三、李四测试 Web 与 MCP 的独立身份。
- [ ] 验证账号禁用、登录切换、Token 过期及权限更新。

完成标准：配置一个 MCP 客户端时能触发浏览器登录，并能以张三和李四身份调用 `whoami`，看到不同的团队和授权对象。

### 阶段 2：Skill Registry、搜索和 Web 页面（约 2~3 天）

任务：

- [ ] Skill 模型、分类、标签、授权搜索、详情、版本、文件读取。
- [ ] Web 首页/列表/详情/分类/团队库。
- [ ] 个人收藏 + 团队收藏集页面与操作。
- [ ] MCP `list_skills`、`search_skills`、`get_skill*`、`list_collections`、`list_favorites`。
- [ ] 服务端搜索与按 ID 读取均应用 ACL。

完成标准：张三搜索与李四搜索结果不同；匿名访问和猜 ID 不泄漏私有内容；Web 与 MCP 查询相同权限集。

### 阶段 3：Agent 自主安装与上传闭环（约 3~4 天）

任务：

- [ ] 实现 `install_skill` 返回清晰结构化操作计划。
- [ ] 实现一次性下载票据、归档 Manifest、SHA-256。
- [ ] Agent 使用自己已有的编辑/终端能力实际写入 Qoder/ Cursor 原生目录，不使用任何独立安装程序。
- [ ] `report_install_result` 区分自报和真实可验证状态。
- [ ] `upload_skill` 单文件上传、`prepare_skill_upload`、ZIP 分段式上传。
- [ ] SKILL.md 验证、安全 ZIP 检查、团队归属和权限校验。
- [ ] Web“我的上传”、审核页面；审核后团队成员可见。

完成标准：一个 Agent 自然语言请求下实现“搜索 → 获取 → 安装”，另一个请求实现“读取项目 Skill → 上传为草稿 → 审核发布 → 团队成员检索安装”。

### 阶段 4：客户端兼容、测试与交付（约 2~3 天）

任务：

- [ ] 对 Qoder IDE、Qoder CLI、Cursor 分别验证 MCP 授权和 `whoami`；Claude Code 作为额外兼容目标。
- [ ] 测试不同安装目标（用户级/项目级）、重载、冲突、错误码。
- [ ] 单元测试、权限集成测试、安全测试、至少一条 Web 端到端流程。
- [ ] 完整 `README.md`：部署启动、演示账号、MCP 配置、流程截图、限制与故障排查。
- [ ] 提供 `seed_demo.py`、显式确认的 `reset_demo.py`、演示数据备份说明。

完成标准：全新电脑按 README 装好开发依赖、启动一次即可演示全部闭环，不依赖任何额外数据库/存储组件。

### 推荐先后依赖

`阶段 0 → 阶段 1 → 阶段 2 → 阶段 3 → 阶段 4`。前端 UI 可在阶段 1 后并行推进；但 *权限内核必须先完成*，避免上传和下载接口被临时匿名实现污染设计。

---

## 14. 启动与配置样例

示意 `.env.example`：

```dotenv
APP_ENV=local-demo
APP_HOST=127.0.0.1
APP_PORT=8765
APP_BASE_URL=http://127.0.0.1:8765
DATA_DIR=./data
DEMO_SEED_ENABLED=true
SESSION_TTL_MINUTES=120
OAUTH_ACCESS_TOKEN_TTL_MINUTES=30
TRANSFER_TICKET_TTL_SECONDS=120
MAX_UPLOAD_ZIP_BYTES=2097152
MAX_UNCOMPRESSED_BYTES=10485760
MAX_UPLOAD_FILES=100
LOG_LEVEL=INFO
```

示意启动步骤（Python 和 Node.js 是*项目开发依赖*，并非单独的 Skill 安装 CLI）：

```bash
# 1. 克隆/打开项目后安装后端开发依赖
python -m venv .venv
source .venv/bin/activate          # Windows 请使用对应的激活方式
pip install -r requirements.txt   # 开发时生成并锁定依赖版本

# 2. 前端首次构建
cd frontend
npm ci
npm run build
cd ..

# 3. 首次写入演示数据
python scripts/seed_demo.py

# 4. 单机运行 Web / API / MCP
uvicorn backend.app.main:app --host 127.0.0.1 --port 8765 --workers 1
```

启动后：

- Web：`http://127.0.0.1:8765/app`
- MCP Endpoint：`http://127.0.0.1:8765/mcp`
- 健康检查：`http://127.0.0.1:8765/healthz`
- 协议发现：`http://127.0.0.1:8765/.well-known/oauth-protected-resource`

说明：项目目录和真实命令以代码实现结果为准；必须保持 `README.md` 和运行方式一致。开发服务启动后不应自动执行演示数据重置。

---

## 15. 测试矩阵与验收用例

| ID | 验收项 | 执行步骤 | 通过条件 |
| --- | --- | --- | --- |
| T01 | 单机启动 | 初始化并运行 | Web、REST、MCP 在同一端口可用 |
| T02 | Web 用户登录 | 张三登录并退出 | 姓名和团队正确，退出后受保护页面被拦截 |
| T03 | MCP 跳转登录 | 新客户端连接 `/mcp` | 弹出浏览器、完成授权、`whoami=张三` |
| T04 | MCP 身份切换 | 重新授权李四 | `whoami=李四`，不会沿用张三 Token |
| T05 | ACL 搜索 | 两人搜索相同关键词 | 权限过滤正确、组间隔离 |
| T06 | 越权详情 | 李四读取 `java-code-review` | 被拒绝且不泄露私有文件 |
| T07 | 分类浏览 | 打开 AI Coding、DevOps | 返回各自授权分类结果与正确计数 |
| T08 | 个人收藏 | 张三添加收藏 | 李四个人收藏不受影响 |
| T09 | 团队收藏 | 研发一组查看集合 | 仅组内/授权者可见，集合内容可读 |
| T10 | Agent 安装 | 请求 Qoder 安装 `git-commit-guide` | 文件真正写入 `.qoder/skills/.../SKILL.md`，可被发现 |
| T11 | 安装冲突 | 本地已有同名 Skill | Agent 提示确认，不静默覆盖 |
| T12 | 文件校验 | 篡改下载 ZIP | 安装失败，返回/记录 `DIGEST_MISMATCH` |
| T13 | Agent 上传单文件 | 张三上传自制 SKILL.md 到研发一组 | 服务端生成张三名下草稿 |
| T14 | Agent 上传 ZIP | Agent 打包并提交目录 | 后端接收包且扫描、关联正确文件 |
| T15 | 审批发布 | Admin 审核通过 | 研发一组能检索安装；研发二组仍不能 |
| T16 | 未授权上传 | 李四向研发一组上传 | 被拒绝，不能冒用张三身份 |
| T17 | 上传安全 | 构造 `../`、软链接、超大归档 | 上传拒绝、日志记录、无越界写入 |
| T18 | 票据超时 | 过期/二次使用下载票据 | 返回失效，不再次下载 |
| T19 | 服务重启 | 上传和收藏后重启 | JSON 与 ZIP 数据仍然存在 |
| T20 | 审计 | 搜索、上传、审核、安装 | 关键操作可追溯，没有密码/Token/票据泄漏 |

### 15.1 项目最终验收演示脚本

演示一（Web）：张三登录 → 搜索 Skill → 查看分类 → 收藏 → 团队库；切换李四确认隔离。

演示二（Agent 安装）：在 Qoder 配置 MCP → 浏览器以张三授权 → `whoami` → 搜索 `git-commit-guide` → 请求安装至当前项目 → Agent 自行下载/校验/写文件 → 刷新并检查技能出现。

演示三（Agent 上传）：在 Qoder 工作区手动创建 `my-demo-helper/SKILL.md` → 告诉 Agent 上传到研发一组 → Agent 读取文件并调用 MCP → Web 端审核发布 → 张三团队成员查找和安装。

演示四（越权）：李四尝试搜索、读取、下载、安装 `java-code-review` → 全部按 ACL 拒绝。

---

## 16. 安全与已知限制

1. *本机 PoC 不等于生产环境*：演示账户密码公开在文档中，因此只绑定 loopback，不允许直接暴露公网。生产化必须替换密码与身份系统。
2. *OAuth 不可省略*：既然目标是“配置 MCP → 浏览器跳转登录 → Agent 用这个人身份访问”，就必须完整实现 OAuth 授权码和 token 验证，不能仅通过一个自定义 `login` MCP Tool 冒充。
3. *不存在通用的远程自动写本地文件能力*：Tool 只能传达计划；具体安装由 Agent 自有工具和用户权限决定。没有文件工具的 Agent 只能给出手工指引。
4. *路径与脚本安全*：不直接解压到用户真实目录，先校验；禁止任意路径覆盖、执行来源不明脚本；必须检查压缩包与源文件的恶意指令/凭据泄漏风险。
5. *角色权限不能依赖前端*：统一后端 ACL 适用于搜索、详情、逐文件读取、下载 Ticket、上传、审核、共享及收藏。
6. *本地 JSON 限制*：单进程单机适用，存在文件系统人为编辑风险，不能把它视作真实生产的多用户安全边界。
7. *已安装版本不能强制收回*：发布版本在服务器端撤回，只能阻止新下载/提醒更新；无法保证其他客户端手动复制出去的离线文件被删除。
8. *本期不保证跨设备访问*：云 Agent、容器 Agent、Web Agent 的 localhost 与本机可能不同；需要可达 HTTPS 地址及单独适配。
9. *不让 Agent 直接审批自己的上传*：审批只保留在授权 Web Reviewer / Admin。
10. *不要把工具输出的 Skill 指令提升为系统指令*：读取到的 `SKILL.md` 是来源受控但仍不可信的业务内容，不能越权执行系统修改。

---

## 17. 明确不在第一版做的事项

- MySQL/Redis/OSS/ES、K8s 部署、跨组织多租户。
- 独立 CLI 安装器、独立 Sync Agent、系统托盘、常驻客户端守护程序。
- 直接依赖 Qoder/Cursor/Claude Code 的私有市场发布 API。
- 自动抓取任意外部 Skill 仓库、联网搜索社区 Skill、下载不可信第三方 ZIP。
- LLM 语义索引与自动评测、自动运行 Skill 脚本、生产系统变更。
- 自动强制卸载所有员工电脑上的 Skill。

这些都可以在基础闭环稳定后单独评估。第一版不要因为框架泛化而拖慢“上传/搜索/安装/权限”的核心交付。

---

## 18. 交给开发 Agent 的实施任务指令（可直接使用）

> 在当前空项目中构建 `enterprise-skill-hub`。请严格按照本文件进行分阶段实现，先完成可运行的最小闭环，再扩展 UI 和管理功能。后端使用 Python FastAPI + 官方 MCP Python SDK，前端使用 React + Vite。单机运行时，一个 ASGI 端口同时提供 Web 静态界面、REST 和 Streamable HTTP MCP。不要引入 MySQL、Redis、OSS、独立数据库服务，也不要编写独立本地 Skill 安装 CLI/Adapter；所有数据和 ZIP 文件都存在本机 `data/` 目录。
>
> 
> 预置 `admin`、`zhangsan`、`lisi`、`wangwu`、`zhaoliu` 等演示账号、4 个业务团队、7 类 Skill、8 个简短 SKILL.md、个人收藏和团队收藏集。实现浏览器账户密码登录与 MCP OAuth Authorization Code + PKCE 的完整跳转认证，使 `whoami` 真正反映当前 OAuth Token 对应用户；Web 与 MCP 使用统一 ACL。
>
> 
> MCP 必须支持 `search_skills`、`list_skills`、`get_skill`、`list_skill_categories`、`get_skill_instructions`、`get_skill_file`、`list_favorites`、`list_collections`、`install_skill`、`upload_skill` 等本文列明 P0 Tool。`install_skill` 只返回受权下载 Ticket、哈希、目标目录和让 Agent 使用自身文件/终端能力完成安装的结构化计划；不得把生成 URL 当成已安装。`upload_skill` 允许单 SKILL.md 文本上传和 ZIP 受控上传，必须先审核再发布。
>
> 
> 按阶段提交：每阶段先写关键接口、权限和自动化测试，再完成前端；给出本阶段变更说明和可演示步骤。所有文件操作必须有路径安全和 SHA-256 校验；所有审计不得记录密码、Token、一次性票据。最后完成 T01~T20 全套验收，提供 README、`.env.example`、启动脚本和清晰的本地 MCP 客户端配置方法。遇到客户端 OAuth 或 Skill 目录兼容性差异，先查官方文档并记录差异，禁止用固定管理员 Token 绕过。

---

## 19. 官方参考资料

1. MCP 授权规范（MCP Authorization）：https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
2. MCP 官方 Python SDK（OAuth 示例和资源服务器）：https://github.com/modelcontextprotocol/python-sdk
3. Agent Skills 开放格式：https://agentskills.io/specification
4. Qoder IDE Skills：https://docs.qoder.com/extensions/skills
5. Qoder CLI Skills：https://docs.qoder.com/cli/Skills
6. Qoder CLI MCP Reference：https://docs.qoder.com/cli/mcp-reference
7. Cursor MCP：https://prod.cursor.com/docs/mcp
8. Cursor Agent Skills：https://cursor.com/docs/skills
9. Claude Code MCP：https://code.claude.com/docs/en/mcp
10. Open SSR 社区参考：https://github.com/cobibean/shared-skills-registry-mcp
11. Skillet 社区参考：https://github.com/joshrotenberg/skillet

---

## 最终交付清单

- [ ] 一个本机运行的 Web Skill Hub，提供浏览、搜索、分类、详情、上传、审核、个人收藏和团队收藏集。
- [ ] 一套共享业务逻辑的 REST API + Streamable HTTP MCP Server。
- [ ] 真实 Web 演示账号与 OAuth 浏览器授权，含身份切换和组间隔离。
- [ ] 由 Agent 自己执行的 Skill 安装、上传，以及服务端下载票据、上传会话和完整性验证。
- [ ] 8 个简短预置 Skill、4 个业务团队、5 个登录账号、示例收藏集。
- [ ] 本机 JSON + ZIP 文件持久化，不启动额外数据库服务。
- [ ] 自动化测试、演示操作说明、运行手册和 MCP 配置示例。

**验收总原则：让张三、李四分别登录同一个平台，在 Web 和 MCP 中获得不同的 Skill 视图，并真实完成“检索 → Agent 安装”和“Agent 上传 → 团队审核 → 组内分享”两条操作链路。**

</details>
