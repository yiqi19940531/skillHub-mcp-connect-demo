# 桌面端实际验收操作单

本机项目：`<PROJECT_ROOT>`。
服务：`http://127.0.0.1:8765/mcp`，服务名 `enterprise-skills`。
实际结果以 [ACCEPTANCE.md](ACCEPTANCE.md) 为准；本操作单不是通过证明。

2026-10-19 执行结果：两端已完成本操作单的安装、文本/ZIP 上传、独立审核和原生发现调用。下文保留复现步骤；最终脱敏证据见 [desktop-acceptance-results.json](ACCEPTANCE.md)。

## 当前接入准备（2026-10-19）

- Qoder IDE 1.32.2：已合并 `~/.qoder/mcp.json`；其他服务保持原样，原配置有权限为 600 的备份。原生浏览器回调已显示“授权成功”，设置页已实际列出 32 个工具。
- Codex 桌面版 26.1013.40934：已配置 `~/.codex/config.toml`。PATH CLI 0.148.0 首次授权虽显示成功，桌面日志却拒绝缺少 issuer 的刷新凭据；改用桌面自带 CLI 0.163.0-alpha.10.2 重新授权并重连后，原生桌面聊天已完成 38 次 MCP 调用，安装、两种上传、独立发布和原生发现/实际使用均通过，详见 [ACCEPTANCE.md](ACCEPTANCE.md)。
- 两端都不配置固定 Bearer Token，也不改用管理员身份。
- 当前电脑控制工具禁止操作 Codex 自身窗口；Qoder 的窗口坐标输入返回窗口不可用。因此需要用户完成客户端内的认证、重连和必要的对话输入。

## 连接确认

Qoder：打开本项目文件夹，进入「Qoder IDE 设置 → MCP 服务」，认证 `enterprise-skills`。选择张三演示账号。成功后核对工具列表，预期 32 个。

Codex：进入「设置 → MCP servers」，重连 `enterprise-skills`，使用 `/mcp` 查看状态。如果已有聊天未获取新工具，在重连后的本项目聊天中继续验收。不要通过直接 HTTP 调用冒充桌面 MCP 工具调用。

## 第一步：安装并上传

下面的提示词分别交给两个桌面端执行。将 `CLIENT` 在 Qoder 替换为 `qoder-ide`，在 Codex 替换为 `codex-desktop`；将 `FIXTURE` 分别替换为 `qoder` 或 `codex`。

```text
请实际验收企业 Skill Hub MCP。只使用 enterprise-skills 的 MCP 业务工具；本地文件由你的文件/终端能力操作，不编写安装 CLI。当前项目应为 <PROJECT_ROOT>；若不是，请先停止并说明。

1. 调用 whoami，确认 OAuth 主体为 zhangsan / user-zhangsan。调用 list_my_teams、list_skills 和 search_skills。确认可见 java-code-review 和企业公共技能，不能获取 python-style-guide；不要因 Web 切换账号而假设 MCP 身份改变。
2. 搜索 git-commit-guide，调用 get_skill_install_plan，然后 install_skill，client=CLIENT，scope=project，workspace_id=本项目绝对路径。按返回清单验证 SHA-256 和安全相对路径。优先使用 inline_files，保留准确 UTF-8 字节；如需下载，只使用该计划的短效票据。不要执行任何包内脚本。
3. 用你的文件能力把 Skill 安装到返回的本项目原生目录，保存返回的 .skill-hub-install.json 收据。已有同名目录时先核对收据和摘要；存在未知目录或本地修改则停下询问，不静默覆盖。确认 SKILL.md 和清单摘要后 report_install_result，status=written、files_written=true、client_discovered=false，关联返回的 installation_id，operation=install。记录目录、版本、摘要和 trace_id，不记录票据或 OAuth 凭据。
4. 读取 test-results/desktop-acceptance/fixtures/FIXTURE-desktop-acceptance-helper/SKILL.md。调用 upload_skill，以 team-dev-a、team 可见性、0.1.0 版本创建草稿，显示名称为本客户端桌面验收助手，分类 api-mcp，标签 desktop-acceptance。使用稳定的 request_id 避免重试重复创建，随后 request_skill_review。记录 skill_id、review_id 和真实作者。
5. 读取同一 fixtures 目录下的 FIXTURE-desktop-acceptance-helper.zip；按 manifest.json 核对大小和 SHA-256。调用 prepare_skill_upload，用自身网络能力 POST ZIP 到返回地址，再调用 upload_skill，明确关联刚创建的 skill_id、upload_id，版本 0.2.0，team-dev-a / team。提交审核，并记录 review_id。不要把 Token 放入终端，不打印一次性传输 URL，也不要自行批准。
6. 汇总实际工具调用、安装落盘证据和两次上传的草稿/审核状态。客户端技能发现若尚未验证，明确保留待验，不能上报 discovered。
```

验收输入存放在 Git 忽略的 `test-results/desktop-acceptance/fixtures/`；它们只是待上传文件，不是已经安装的技能。ZIP 只含 `SKILL.md` 和 `reference.txt`，无脚本、无凭据。`manifest.json` 含两个客户端的绝对输入路径、大小和摘要。

本仓库将 `.qoder/skills/` 和 `.agents/skills/` 作为本机验收安装产物保留并由 Git 忽略；正式种子内容在 `seed/skills/`，脱敏验收证据在 `docs/evidence/`。

## 第二步：独立审核

在 Web「审核中心」由 admin 演示账号批准对应上传。先批准 0.1.0，确认可检索，再批准 0.2.0，确认默认版本切换。审核理由应明确为桌面端验收测试。上传者不可自审；客户端 Agent 不应使用 Bearer 调用审核决定。

由两个客户端重新搜索自己的助手，核对已发布 0.2.0 和附件。可再安装该助手到各自原生项目目录，按相同清单验证和上报 written。

## 第三步：客户端发现

Qoder：按客户端实际提示重载/重启，打开本项目，在 `/` 技能列表中查找安装的名称，实际调用验收助手。Codex：重载后在本项目的新会话检查可用技能列表，再按名称调用验收助手。提示词只要求使用对应助手，不手工提供文件路径或预期输出。

必须区分以下证据：

1. 文件证据：原生目录的 `SKILL.md`、清单摘要和无凭据收据。
2. 发现证据：客户端技能列表/会话技能元数据出现名称，并能实际使用。单纯搜索文件并读取内容不构成客户端发现。
3. 上报证据：确认发现后，关联原 installation_id 调用 report_install_result，status=discovered、files_written=true、client_discovered=true。来源仍为 agent_reported。

证据只保存演示内容、版本、工具结果的 trace_id、安装/审核 ID 和必要截图；不要保存密码、Token、授权码或传输票据。遇到错误保留原始业务错误码、客户端版本和具体步骤，再定位处理。

参考：[Codex MCP 官方文档](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、[Qoder MCP 官方文档](https://docs.qoder.com/user-guide/chat/model-context-protocol)。
