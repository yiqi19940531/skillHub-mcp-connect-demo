# 客户端接入与兼容

Endpoint：`http://127.0.0.1:8765/mcp`。Streamable HTTP、浏览器 Authorization Code + PKCE S256、DCR public client。所有客户端先验证 `whoami`，不复用管理员身份。

实测环境的两原生桌面端已通过张三 OAuth、真实安装、文本/ZIP 上传、独立发布和原生技能发现调用。实际结果见 [ACCEPTANCE.md](ACCEPTANCE.md)，复现步骤见 [DESKTOP_ACCEPTANCE.md](DESKTOP_ACCEPTANCE.md)。

本机兼容性注意：PATH 中的 `codex` 为 0.148.0，桌面自带 CLI 为 0.163.0-alpha.10.2。旧 CLI 创建的 OAuth 刷新凭据导致桌面日志出现缺少 authorization server issuer 的错误。优先通过桌面设置认证；本机已使用下面的桌面自带二进制重新授权，之后须让桌面连接重新读取凭据：

```bash
/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex mcp login enterprise-skills --oauth-client-registration dcr --scopes skills:read,skills:write
```

以上为本机实际路径。其他安装位置以对应桌面应用内置 CLI 为准，避免混用旧版本 CLI 的凭据格式。

| 客户端 | 配置位置/方式 | 项目 Skill 目录 | 首版验收要求 |
| --- | --- | --- | --- |
| Qoder IDE | 设置 → MCP 服务；本机添加入口为 `~/.qoder/mcp.json` | `.qoder/skills/` | 必验；实际状态见 ACCEPTANCE.md |
| Codex 桌面端 | 设置 → MCP servers；本机 `~/.codex/config.toml` | `.agents/skills/` | 必验；实际状态见 ACCEPTANCE.md |
| Qoder CLI | `~/.qoder/settings.json` 的 `mcpServers`，或原生 CLI 配置 | `.qoder/skills/` | 配置和适配设计保留 |
| Cursor | `~/.cursor/mcp.json` | `.cursor/skills/` | 配置和适配设计保留 |
| Claude Code | 原生 `claude mcp add` | `.claude/skills/` | 配置和适配设计保留 |

Qoder IDE/CLI 通用配置条目（按版本选择实际配置文件；只合并本条，不覆盖现有服务）：

```json
{"mcpServers":{"enterprise-skills":{"url":"http://127.0.0.1:8765/mcp","type":"http"}}}
```

Cursor：

```json
{"mcpServers":{"enterprise-skills":{"url":"http://127.0.0.1:8765/mcp"}}}
```

Codex：

```toml
[mcp_servers.enterprise-skills]
url = "http://127.0.0.1:8765/mcp"
```

Claude Code：

```bash
claude mcp add --transport http enterprise-skills http://127.0.0.1:8765/mcp
```

用户级 Skill 目录为上述项目目录在 `~/` 下的对应目录。Qoder IDE 按官方说明重启并在 `/` 中检查；Codex 验证新会话中的技能发现。不同客户端的热重载和同名优先级须按实际版本记录。

客户端可能在添加时认证，也可能需要手动点击钥匙/Authenticate。服务不会自行代替用户认证。Qoder IDE 的本机观察中，OAuth 客户端注册名为 `lingma-ide`，回调使用 loopback `/callback`。

本机授权使用准确的资源和 issuer。HTTP loopback 原生客户端允许端口变化，主机、路径和查询仍匹配；不能将 localhost、127.0.0.1 或不同路径混用。授权码一次使用、Token 绑定 `/mcp`，声明支持 issuer 响应，未实现的 CIMD 不广告。

如果客户端只能使用预注册 public client，可向本机 OAuthClient 仓库配置固定 client_id 与允许的回调 URI；保持 PKCE 和用户浏览器授权，不需要 client secret。不要把密码、Access Token 或固定管理员 Token 放进配置或对话。

参考：[Qoder MCP](https://docs.qoder.com/user-guide/chat/model-context-protocol)、[Qoder Skills](https://docs.qoder.com/extensions/skills)、[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)、[Codex Skills](https://learn.chatgpt.com/docs/build-skills)。
