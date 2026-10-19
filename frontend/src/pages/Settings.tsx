import { useState } from "react";
import {
  Code2,
  KeyRound,
  Link2,
  Monitor,
  RefreshCw,
  Terminal,
  Trash2,
} from "lucide-react";
import { remove } from "../api";
import {
  Badge,
  CopyButton,
  Empty,
  Failure,
  Loading,
  Modal,
  Notice,
  PageTitle,
  date,
  useApp,
  useData,
} from "../ui";
import type { Audit, Installation, OAuthGrant } from "../types";
import Usage from "./Usage";

export default function Settings() {
  const { me, perform, busy } = useApp(),
    [tab, setTab] = useState("connect"),
    [request, setRequest] = useState("");
  const grants = useData<OAuthGrant[]>("/oauth/grants"),
    records = useData<Installation[]>(
      tab === "installations" ? "/installations" : null,
    ),
    audit = useData<Audit[]>(tab === "audit" ? "/audit-events" : null),
    runtime = useData<{ mcp_endpoint: string; web_url: string }>("/runtime");
  const endpoint = runtime.data?.mcp_endpoint || "http://127.0.0.1:8765/mcp";
  const qoder = JSON.stringify(
      { mcpServers: { "enterprise-skills": { url: endpoint, type: "http" } } },
      null,
      2,
    ),
    codex = `[mcp_servers.enterprise-skills]\nurl = "${endpoint}"\n\n# 也可使用原生 Codex CLI 配置和授权：\n# codex mcp add enterprise-skills --url ${endpoint}\n# codex mcp login enterprise-skills`;
  const command = (record: Installation, operation: string) => {
    setRequest(
      `请通过 Enterprise Skill Hub MCP，${operation === "update" ? "检查并更新" : "卸载"}我已上报的 Skill ${record.skill_id}，原 installation_id 为 ${record.installation_id}。调用 ${operation === "update" ? "update_skill" : "uninstall_skill"} 获取计划，使用自身文件能力核对本地 .skill-hub-install.json 与清单。${operation === "update" ? "本地修改先确认并备份，不静默覆盖额外文件。" : "只移除收据中受管理的文件，保留额外文件；修改过的内容先确认。"}完成后调用 report_install_result 上报；不要把生成计划当成执行成功。`,
    );
  };
  return (
    <>
      <PageTitle
        eyebrow="CONNECTED WORKFLOWS"
        title="设置与 Agent 接入"
        description="连接你的工具、管理授权，并查看由 Agent 上报的执行记录。"
      />
      <div className="tab-bar">
        {[
          ["connect", "MCP 接入指南"],
          ["grants", "我的授权"],
          ["installations", "安装记录"],
          ["usage", "使用统计"],
          ...(me.roles.includes("PlatformAdmin")
            ? [["audit", "审计日志"]]
            : []),
        ].map(([id, label]) => (
          <button
            key={id}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "usage" && <Usage />}
      {tab === "connect" && (
        <>
          <section className="panel endpoint-panel">
            <span className="endpoint-icon">
              <Link2 size={25} />
            </span>
            <div>
              <h2>一个地址，连接团队技能</h2>
              <p>Streamable HTTP · OAuth 浏览器授权 · 按用户隔离</p>
              <code>{endpoint}</code>
            </div>
            <CopyButton text={endpoint} label="复制 MCP 地址" />
          </section>
          <div className="connection-grid">
            <section className="panel connection-card">
              <div className="connection-title">
                <span className="skill-symbol violet">
                  <Monitor size={24} />
                </span>
                <div>
                  <h2>Qoder IDE</h2>
                  <p>在 IDE 中发现与使用团队 Skills</p>
                </div>
              </div>
              <ol className="instruction-list">
                <li>打开 Qoder 的 MCP 配置，添加 Streamable HTTP 服务。</li>
                <li>
                  填写下方地址配置。客户端如需 OAuth 开关，请按实际版本启用。
                </li>
                <li>连接或认证时，在浏览器登录 Skill Hub 并同意授权。</li>
                <li>
                  调用 whoami，核对姓名和团队，再让 Agent 搜索和安装 Skill。
                </li>
              </ol>
              <pre className="code-block">{qoder}</pre>
              <CopyButton text={qoder} label="复制配置示例" />
              <p className="small-text muted">
                项目级
                Skills：.qoder/skills/&lt;name&gt;/。安装后重启或重新加载，并检查
                / 技能列表。
              </p>
            </section>
            <section className="panel connection-card">
              <div className="connection-title">
                <span className="skill-symbol blue">
                  <Terminal size={24} />
                </span>
                <div>
                  <h2>Codex 桌面端</h2>
                  <p>通过本机 MCP 连接使用技能库</p>
                </div>
              </div>
              <ol className="instruction-list">
                <li>
                  打开设置中的 MCP servers，添加 Streamable HTTP
                  地址；也可编辑本机配置。
                </li>
                <li>保存后重新加载或重启，在需要授权的连接上选择认证。</li>
                <li>在浏览器登录并同意授权，回到客户端调用 whoami。</li>
                <li>
                  项目 Skill 安装至 .agents/skills，确认新会话中可被发现。
                </li>
              </ol>
              <pre className="code-block">{codex}</pre>
              <CopyButton text={codex} label="复制配置示例" />
              <p className="small-text muted">
                用户级 Skills：~/.agents/skills/&lt;name&gt;/。CLI
                可辅助排查，桌面端仍需单独验收。
              </p>
            </section>
          </div>
          <Notice>
            浏览器切换账号不会切换已授权的 Agent。切换 MCP
            身份时，请断开或撤销原授权，再以目标账号重新认证。
          </Notice>
          <section className="panel sample-prompts">
            <h2>试试这样开始</h2>
            {[
              "先调用 whoami 核对身份，然后搜索我有权访问的代码审查技能。",
              "把 git-commit-guide 安装到当前项目，校验文件并确认客户端能发现它，然后上报结果。",
              "把我选择的本地 Skill 上传到所属团队，保存为草稿并提交审核，不要直接发布。",
            ].map((text) => (
              <div key={text}>
                <Code2 size={16} />
                <p>{text}</p>
                <CopyButton text={text} className="icon-copy" label="复制" />
              </div>
            ))}
          </section>
        </>
      )}
      {tab === "grants" && (
        <>
          <Notice>
            这里撤销的是 Skill Hub 签发给 MCP 客户端的授权，不影响你的 Web
            登录。
          </Notice>
          {grants.loading ? (
            <Loading />
          ) : grants.error ? (
            <Failure text={grants.error} />
          ) : grants.data?.length ? (
            <div className="panel table-panel">
              <table>
                <thead>
                  <tr>
                    <th>客户端</th>
                    <th>授权范围</th>
                    <th>授权时间</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {grants.data.map((grant) => (
                    <tr key={grant.grant_id}>
                      <td>
                        <strong>{grant.client_name}</strong>
                        <small>{grant.client_id}</small>
                      </td>
                      <td>
                        <code>{grant.scope}</code>
                      </td>
                      <td>{date(grant.created_at)}</td>
                      <td>
                        <Badge tone={grant.revoked ? "neutral" : "green"}>
                          {grant.revoked ? "已撤销" : "有效"}
                        </Badge>
                      </td>
                      <td>
                        {!grant.revoked && (
                          <button
                            className="button secondary small danger"
                            disabled={busy}
                            onClick={() =>
                              void perform(
                                () => remove("/oauth/grants/" + grant.grant_id),
                                "MCP 授权已撤销",
                              )
                            }
                          >
                            <KeyRound size={13} />
                            撤销授权
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              title="还没有已授权客户端"
              text="按接入指南连接 Qoder 或 Codex，完成浏览器授权后将显示在这里。"
            />
          )}
        </>
      )}
      {tab === "installations" && (
        <>
          <Notice>
            下列状态来自 Agent
            上报。平台不会扫描你的电脑，也不会因生成计划就声称已经安装。
          </Notice>
          {records.loading ? (
            <Loading />
          ) : records.error ? (
            <Failure text={records.error} />
          ) : records.data?.length ? (
            <div className="panel table-panel">
              <table>
                <thead>
                  <tr>
                    <th>Skill / 版本</th>
                    <th>客户端 / 范围</th>
                    <th>操作</th>
                    <th>执行状态</th>
                    <th>记录来源</th>
                    <th>维护</th>
                  </tr>
                </thead>
                <tbody>
                  {[...records.data].reverse().map((record) => (
                    <tr key={record.installation_id}>
                      <td>
                        <strong>{record.skill_id}</strong>
                        <small>v{record.version}</small>
                      </td>
                      <td>
                        {record.client}
                        <small>
                          {record.scope === "project" ? "项目级" : "用户级"} ·{" "}
                          {record.workspace_id}
                        </small>
                      </td>
                      <td>
                        {
                          {
                            install: "安装",
                            update: "更新",
                            uninstall: "卸载",
                          }[record.operation]
                        }
                      </td>
                      <td>
                        <Badge value={record.status} />
                        <small>
                          {record.files_written ? "文件已写入" : "尚未确认写入"}{" "}
                          ·{" "}
                          {record.client_discovered
                            ? "客户端已发现"
                            : "尚未确认发现"}
                        </small>
                      </td>
                      <td>
                        <Badge tone="neutral">Agent 自报</Badge>
                      </td>
                      <td>
                        {["written", "discovered"].includes(record.status) && (
                          <div className="button-row">
                            <button
                              className="icon-button"
                              aria-label={"更新 " + record.skill_id}
                              onClick={() => command(record, "update")}
                            >
                              <RefreshCw size={15} />
                            </button>
                            <button
                              className="icon-button danger"
                              aria-label={"卸载 " + record.skill_id}
                              onClick={() => command(record, "uninstall")}
                            >
                              <Trash2 size={15} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty
              title="尚无安装上报记录"
              text="让 Agent 调用 install_skill、实际执行后，再调用 report_install_result。"
            />
          )}
        </>
      )}
      {tab === "audit" &&
        (audit.loading ? (
          <Loading />
        ) : audit.error ? (
          <Failure text={audit.error} />
        ) : (
          <div className="panel table-panel">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作主体</th>
                  <th>操作</th>
                  <th>对象</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                {audit.data?.map((event) => (
                  <tr key={event.event_id}>
                    <td>{date(event.time)}</td>
                    <td>
                      <code>{event.actor}</code>
                    </td>
                    <td>
                      <code>{event.action}</code>
                    </td>
                    <td className="truncate">{event.target || "—"}</td>
                    <td>
                      <Badge
                        tone={event.decision === "deny" ? "rejected" : "green"}
                      >
                        {event.result}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      {request && (
        <Modal
          title="交给 Agent 执行"
          subtitle="文件操作由 Agent 的现有工具完成；服务端无法远程删除或改写本地文件。"
          close={() => setRequest("")}
        >
          <p className="agent-request">{request}</p>
          <CopyButton text={request} label="复制维护请求" />
        </Modal>
      )}
    </>
  );
}
