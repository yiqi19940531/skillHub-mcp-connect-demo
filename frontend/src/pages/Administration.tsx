import { useState } from "react";
import { Archive, KeyRound, Pencil, Plus, UserPlus, Users } from "lucide-react";
import { patch, post } from "../api";
import {
  Badge,
  Failure,
  Field,
  Form,
  Loading,
  Modal,
  Notice,
  PageTitle,
  useApp,
  useData,
} from "../ui";
import type { Team, User } from "../types";

const roleLabels: Record<string, string> = {
  Member: "成员",
  SkillAuthor: "作者",
  Reviewer: "审核员",
  PlatformAdmin: "平台管理员",
};
export default function Administration() {
  const { me, perform, busy } = useApp(),
    isAdmin = me.roles.includes("PlatformAdmin"),
    users = useData<User[]>(isAdmin ? "/admin/users" : null),
    teams = useData<Team[]>(isAdmin ? "/admin/teams" : null),
    [tab, setTab] = useState("users"),
    [dialog, setDialog] = useState<
      "user" | "team" | "password" | "member" | null
    >(null),
    [user, setUser] = useState<User | null>(null),
    [team, setTeam] = useState<Team | null>(null),
    [username, setUsername] = useState(""),
    [name, setName] = useState(""),
    [password, setPassword] = useState(""),
    [roles, setRoles] = useState<string[]>(["Member", "SkillAuthor"]),
    [owner, setOwner] = useState(""),
    [description, setDescription] = useState(""),
    [memberUser, setMemberUser] = useState(""),
    [memberRole, setMemberRole] = useState("member"),
    [memberStatus, setMemberStatus] = useState("active");
  const openUser = (value: User | null) => {
    setUser(value);
    setUsername(value?.username || "");
    setName(value?.display_name || "");
    setPassword("");
    setRoles(value?.roles || ["Member", "SkillAuthor"]);
    setDialog("user");
  };
  const openTeam = (value: Team | null) => {
    setTeam(value);
    setName(value?.name || "");
    setDescription(value?.description || "");
    setOwner(
      value?.owner_user_id ||
        users.data?.find((u) => !u.disabled)?.user_id ||
        "",
    );
    setDialog("team");
  };
  const saveUser = async () => {
    const result = user
      ? await perform(
          () =>
            patch("/admin/users/" + user.user_id, {
              revision: user.revision,
              display_name: name,
              roles,
            }),
          "账号已更新",
        )
      : await perform(
          () =>
            post("/admin/users", {
              username,
              display_name: name,
              password,
              roles,
            }),
          "账号已创建",
        );
    if (result) setDialog(null);
  };
  const saveTeam = async () => {
    const result = team
      ? await perform(
          () =>
            patch("/admin/teams/" + team.team_id, {
              revision: team.revision,
              name,
              description,
            }),
          "团队已更新",
        )
      : await perform(
          () =>
            post("/admin/teams", { name, description, owner_user_id: owner }),
          "团队已创建",
        );
    if (result) setDialog(null);
  };
  if (!isAdmin)
    return <Failure text="只有平台管理员可以管理账号和组织关系。" />;
  return (
    <>
      <PageTitle
        eyebrow="PEOPLE & PERMISSIONS"
        title="成员与团队"
        description="管理账号、组织关系和角色。权限变更将在后续请求中生效。"
        action={
          <button
            className="button primary"
            onClick={() => (tab === "users" ? openUser(null) : openTeam(null))}
          >
            <Plus size={16} />
            {tab === "users" ? "创建账号" : "创建团队"}
          </button>
        }
      />
      <div className="tab-bar">
        <button
          className={tab === "users" ? "active" : ""}
          onClick={() => setTab("users")}
        >
          账号管理<span>{users.data?.length || 0}</span>
        </button>
        <button
          className={tab === "teams" ? "active" : ""}
          onClick={() => setTab("teams")}
        >
          团队管理
          <span>{teams.data?.filter((t) => !t.internal).length || 0}</span>
        </button>
      </div>
      {users.loading || teams.loading ? (
        <Loading />
      ) : users.error || teams.error ? (
        <Failure text={users.error || teams.error} />
      ) : tab === "users" ? (
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>成员</th>
                <th>账号</th>
                <th>平台角色</th>
                <th>状态</th>
                <th>管理操作</th>
              </tr>
            </thead>
            <tbody>
              {users.data?.map((u) => (
                <tr key={u.user_id}>
                  <td>
                    <div className="person-cell">
                      <span className="avatar">{u.display_name[0]}</span>
                      <strong>
                        {u.display_name}
                        {u.user_id === me.user_id && <small>当前账号</small>}
                      </strong>
                    </div>
                  </td>
                  <td>
                    <code>{u.username}</code>
                  </td>
                  <td>
                    <div className="tags">
                      {u.roles.map((r) => (
                        <span key={r}>{roleLabels[r]}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <Badge tone={u.disabled ? "neutral" : "green"}>
                      {u.disabled ? "已停用" : "使用中"}
                    </Badge>
                  </td>
                  <td>
                    <div className="button-row">
                      <button
                        className="icon-button"
                        aria-label={"编辑 " + u.display_name}
                        onClick={() => openUser(u)}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label={"重置密码 " + u.display_name}
                        onClick={() => {
                          setUser(u);
                          setPassword("");
                          setDialog("password");
                        }}
                      >
                        <KeyRound size={15} />
                      </button>
                      <button
                        className={`text-button ${u.disabled ? "" : "danger"}`}
                        disabled={busy}
                        onClick={() =>
                          void perform(
                            () =>
                              patch("/admin/users/" + u.user_id, {
                                revision: u.revision,
                                disabled: !u.disabled,
                              }),
                            u.disabled
                              ? "账号已启用"
                              : "账号已停用，凭据已撤销",
                          )
                        }
                      >
                        {u.disabled ? "启用" : "停用"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="admin-team-list">
          {teams.data?.map((t) => (
            <section key={t.team_id} className="panel admin-team">
              <div className="section-heading">
                <div>
                  <h2>
                    <Users size={18} />
                    {t.name}
                    <Badge tone={t.archived ? "neutral" : "team"}>
                      {t.archived
                        ? "已归档"
                        : t.internal
                          ? "平台管理"
                          : "业务团队"}
                    </Badge>
                  </h2>
                  <p>{t.description}</p>
                </div>
                <div className="button-row">
                  <button
                    className="button secondary small"
                    onClick={() => openTeam(t)}
                  >
                    <Pencil size={13} />
                    编辑
                  </button>
                  <button
                    className="button secondary small"
                    disabled={t.archived}
                    onClick={() => {
                      setTeam(t);
                      setMemberUser("");
                      setMemberRole("member");
                      setMemberStatus("active");
                      setDialog("member");
                    }}
                  >
                    <UserPlus size={13} />
                    添加成员
                  </button>
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() =>
                      void perform(
                        () =>
                          patch("/admin/teams/" + t.team_id, {
                            revision: t.revision,
                            archived: !t.archived,
                          }),
                        t.archived ? "团队已恢复" : "团队已归档",
                      )
                    }
                  >
                    <Archive size={13} />
                    {t.archived ? "恢复" : "归档"}
                  </button>
                </div>
              </div>
              <div className="member-list">
                {t.members
                  ?.filter((m) => m.status === "active")
                  .map((m) => (
                    <div className="member-chip" key={m.membership_id}>
                      <span className="mini-avatar">
                        {
                          users.data?.find((u) => u.user_id === m.user_id)
                            ?.display_name[0]
                        }
                      </span>
                      <span>
                        {users.data?.find((u) => u.user_id === m.user_id)
                          ?.display_name || m.user_id}
                      </span>
                      <Badge tone="neutral">
                        {m.role === "owner" ? "负责人" : "成员"}
                      </Badge>
                      <button
                        className="icon-button"
                        disabled={t.archived}
                        aria-label={"调整成员 " + m.user_id}
                        onClick={() => {
                          setTeam(t);
                          setMemberUser(m.user_id);
                          setMemberRole(m.role);
                          setMemberStatus(m.status);
                          setDialog("member");
                        }}
                      >
                        <Pencil size={12} />
                      </button>
                    </div>
                  ))}
                {!t.members?.some((m) => m.status === "active") && (
                  <span className="muted">暂无有效成员</span>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
      {dialog === "user" && (
        <Modal
          title={user ? "编辑账号" : "创建账号"}
          close={() => setDialog(null)}
        >
          <Form onSubmit={() => void saveUser()}>
            {!user && (
              <Field label="账号">
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  minLength={3}
                  maxLength={40}
                  autoComplete="off"
                />
              </Field>
            )}
            <Field label="显示姓名">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={80}
              />
            </Field>
            {!user && (
              <Field label="初始密码" hint="10～128 字符，仅以密码哈希持久化。">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={10}
                  maxLength={128}
                  autoComplete="new-password"
                  required
                />
              </Field>
            )}
            <fieldset className="role-picker">
              <legend>平台角色</legend>
              {Object.entries(roleLabels).map(([id, label]) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={roles.includes(id)}
                    onChange={() =>
                      setRoles((values) =>
                        values.includes(id)
                          ? values.filter((v) => v !== id)
                          : [...values, id],
                      )
                    }
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <Notice>
              不能移除最后一个有效平台管理员。审核员也不能审批自己上传的内容。
            </Notice>
            <button className="button primary" disabled={busy || !roles.length}>
              保存账号
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "password" && user && (
        <Modal
          title={"重置 " + user.display_name + " 的密码"}
          close={() => setDialog(null)}
        >
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post("/admin/users/" + user.user_id + "/password", {
                    password,
                  }),
                "密码已重置，该账号原有会话和 MCP 授权已撤销",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Notice>重置密码后，该用户须重新登录 Web 和授权 MCP。</Notice>
            <Field label="新密码">
              <input
                type="password"
                minLength={10}
                maxLength={128}
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <button className="button primary" disabled={busy}>
              确认重置密码
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "team" && (
        <Modal
          title={team ? "编辑团队" : "创建团队"}
          close={() => setDialog(null)}
        >
          <Form onSubmit={() => void saveTeam()}>
            <Field label="团队名称">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={80}
              />
            </Field>
            <Field label="团队描述">
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={1000}
              />
            </Field>
            {!team && (
              <Field label="首位团队负责人">
                <select
                  value={owner}
                  onChange={(e) => setOwner(e.target.value)}
                  required
                >
                  {users.data
                    ?.filter((u) => !u.disabled)
                    .map((u) => (
                      <option key={u.user_id} value={u.user_id}>
                        {u.display_name} · {u.username}
                      </option>
                    ))}
                </select>
              </Field>
            )}
            <button className="button primary" disabled={busy}>
              保存团队
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "member" && team && (
        <Modal
          title={"调整 " + team.name + " 的成员"}
          close={() => setDialog(null)}
        >
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post("/admin/teams/" + team.team_id + "/members", {
                    user_id: memberUser,
                    role: memberRole,
                    status: memberStatus,
                  }),
                "成员关系已保存",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Field label="成员账号">
              <select
                value={memberUser}
                onChange={(e) => setMemberUser(e.target.value)}
                required
              >
                <option value="">请选择成员</option>
                {users.data
                  ?.filter((u) => !u.disabled)
                  .map((u) => (
                    <option key={u.user_id} value={u.user_id}>
                      {u.display_name} · {u.username}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="团队角色">
              <select
                value={memberRole}
                onChange={(e) => setMemberRole(e.target.value)}
              >
                <option value="member">普通成员</option>
                <option value="owner">团队负责人</option>
              </select>
            </Field>
            <Field label="成员状态">
              <select
                value={memberStatus}
                onChange={(e) => setMemberStatus(e.target.value)}
              >
                <option value="active">加入 / 保留团队</option>
                <option value="removed">移出团队</option>
              </select>
            </Field>
            <button className="button primary" disabled={busy || !memberUser}>
              保存成员关系
            </button>
          </Form>
        </Modal>
      )}
    </>
  );
}
