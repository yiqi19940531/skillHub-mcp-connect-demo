import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Code2,
  Download,
  FileText,
  GitBranch,
  MessageSquare,
  Pencil,
  Share2,
  ShieldCheck,
  Star,
} from "lucide-react";
import Markdown from "react-markdown";
import { patch, post, remove } from "../api";
import {
  Badge,
  CopyButton,
  Failure,
  Field,
  Form,
  Loading,
  Modal,
  Notice,
  bytes,
  date,
  useApp,
  useData,
  visibilityText,
} from "../ui";
import type { Category, Grant, Plan, Skill, Targets } from "../types";

export default function SkillDetail({ skillId }: { skillId: string }) {
  const { perform, busy, navigate, notify } = useApp(),
    result = useData<Skill>("/skills/" + encodeURIComponent(skillId));
  const [version, setVersion] = useState(""),
    [file, setFile] = useState("SKILL.md"),
    [dialog, setDialog] = useState<
      "install" | "share" | "issue" | "edit" | "status" | "revoke" | null
    >(null),
    [client, setClient] = useState("qoder-ide"),
    [scope, setScope] = useState("project"),
    [plan, setPlan] = useState<Plan | null>(null),
    [visibility, setVisibility] = useState("custom"),
    [grants, setGrants] = useState<Grant[]>([]),
    [description, setDescription] = useState(""),
    [kind, setKind] = useState("description"),
    [label, setLabel] = useState(""),
    [tags, setTags] = useState(""),
    [category, setCategory] = useState(""),
    [status, setStatus] = useState("deprecated");
  const skill = result.data,
    chosen = skill?.versions?.find((v) => v.version === version);
  useEffect(() => {
    if (skill && !skill.versions?.some((v) => v.version === version))
      setVersion(skill.current_version || skill.versions?.[0]?.version || "");
  }, [skill, version]);
  const contents = useData<{ content: string; sha256: string }>(
      version
        ? "/skills/" +
            encodeURIComponent(skillId) +
            "/versions/" +
            encodeURIComponent(version) +
            "/files/" +
            file
        : null,
    ),
    targets = useData<Targets>(dialog === "share" ? "/share-targets" : null),
    categories = useData<Category[]>(dialog === "edit" ? "/categories" : null);
  const toggleGrant = (value: Grant) =>
    setGrants((items) =>
      items.some((g) => g.type === value.type && g.id === value.id)
        ? items.filter((g) => g.type !== value.type || g.id !== value.id)
        : [...items, value],
    );
  const download = async () => {
    await perform(async () => {
      const transfer = await post<{ download_url: string }>(
        "/skills/" + skillId + "/download",
        { version },
      );
      const response = await fetch(transfer.download_url, {
        credentials: "omit",
      });
      if (!response.ok) throw new Error("下载票据失效或权限已变化");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = skillId + "-" + version + ".zip";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      return true;
    }, "下载已开始");
  };
  if (result.loading) return <Loading />;
  if (result.error || !skill)
    return <Failure text={result.error || "Skill 不可访问"} />;
  return (
    <>
      <button className="back-link" onClick={() => navigate("/app")}>
        <ArrowLeft size={15} />
        返回技能市场
      </button>
      <section className="detail-heading">
        <div className="detail-heading-main">
          <span className="skill-symbol large-symbol violet">
            <Code2 size={32} />
          </span>
          <div>
            <div className="detail-labels">
              <Badge
                tone={skill.visibility === "enterprise" ? "green" : "team"}
              >
                {visibilityText[skill.visibility]}
              </Badge>
              {chosen && <Badge value={chosen.status} />}
            </div>
            <h1>{skill.display_name}</h1>
            <code>{skill.name}</code>
          </div>
        </div>
        <div className="button-row">
          <button
            className={`button secondary ${skill.favorite ? "favorite-active" : ""}`}
            onClick={() =>
              void perform(
                () =>
                  skill.favorite
                    ? remove("/favorites/" + skillId)
                    : post("/favorites", { skill_id: skillId }),
                skill.favorite ? "已取消收藏" : "已收藏",
              )
            }
          >
            <Star size={16} fill={skill.favorite ? "currentColor" : "none"} />
            {skill.favorite ? "已收藏" : "收藏"}
          </button>
          {chosen?.status === "published" && (
            <>
              <button
                className="button secondary"
                onClick={() => void download()}
                disabled={busy}
              >
                <Download size={16} />
                下载
              </button>
              <button
                className="button primary"
                onClick={() => {
                  setPlan(null);
                  setDialog("install");
                }}
              >
                <Code2 size={16} />
                安装到 Agent
              </button>
            </>
          )}
        </div>
      </section>
      <p className="detail-description">{skill.description}</p>
      <div className="detail-meta">
        <span>
          <span className="mini-avatar">{skill.author_name[0]}</span>
          {skill.author_name}
        </span>
        <span>{skill.team_name}</span>
        <span>
          <GitBranch size={14} />v{version}
        </span>
        <span>
          <ShieldCheck size={14} />
          {chosen?.risk === "low" ? "基础检查通过" : "请核对风险提示"}
        </span>
      </div>
      <div className="detail-layout">
        <section className="panel instructions-panel">
          <div className="file-tabs">
            <span>
              <FileText size={16} />
              {file}
            </span>
            <div>
              {contents.data && (
                <CopyButton
                  text={contents.data.content}
                  className="icon-copy"
                  label="复制内容"
                />
              )}
            </div>
          </div>
          {contents.loading ? (
            <Loading />
          ) : contents.error ? (
            <Failure text={contents.error} />
          ) : (
            <div className="markdown">
              <Markdown>
                {contents.data?.content.replace(
                  /^---\r?\n[\s\S]*?\r?\n---\r?\n/,
                  "",
                ) || ""}
              </Markdown>
            </div>
          )}
          {contents.data && (
            <div className="digest-line">
              SHA-256 <code>{contents.data.sha256}</code>
            </div>
          )}
        </section>
        <aside className="detail-aside">
          <section className="panel">
            <h3>关于此 Skill</h3>
            <dl>
              <dt>所属团队</dt>
              <dd>{skill.team_name}</dd>
              <dt>可见范围</dt>
              <dd>{visibilityText[skill.visibility]}</dd>
              <dt>版本</dt>
              <dd>
                <select
                  aria-label="选择版本"
                  value={version}
                  onChange={(e) => {
                    setVersion(e.target.value);
                    setFile("SKILL.md");
                  }}
                >
                  {skill.versions?.map((v) => (
                    <option key={v.version} value={v.version}>
                      {v.version} · {v.status}
                    </option>
                  ))}
                </select>
              </dd>
              <dt>创建时间</dt>
              <dd>{date(chosen?.created_at)}</dd>
            </dl>
            <div className="tags">
              {skill.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
          </section>
          <section className="panel">
            <h3>
              文件清单 <small>{chosen?.manifest.length || 0}</small>
            </h3>
            <div className="manifest-list">
              {chosen?.manifest.map((item) => (
                <button
                  key={item.path}
                  onClick={() =>
                    item.binary
                      ? notify("二进制文件请下载 ZIP 获取")
                      : setFile(item.path)
                  }
                  className={file === item.path ? "active" : ""}
                >
                  <FileText size={14} />
                  <span>{item.path}</span>
                  <small>{bytes(item.size)}</small>
                </button>
              ))}
            </div>
          </section>
          <section className="panel">
            <h3>你的体验，帮助团队改进</h3>
            <div className="rating-row">
              {[1, 2, 3, 4, 5].map((score) => (
                <button
                  className="icon-button star"
                  key={score}
                  aria-label={"评分 " + score + " 星"}
                  disabled={busy || chosen?.status !== "published"}
                  onClick={() =>
                    void perform(
                      () =>
                        post("/skills/" + skillId + "/ratings", {
                          version,
                          score,
                        }),
                      "评分已保存",
                    )
                  }
                >
                  <Star
                    size={22}
                    fill={
                      skill.rating && score <= Math.round(skill.rating)
                        ? "#e9ae42"
                        : "none"
                    }
                  />
                </button>
              ))}
            </div>
            <p className="muted small-text">
              {skill.rating
                ? `${skill.rating} / 5 · ${skill.rating_count} 次评分`
                : "还没有评分，欢迎分享体验"}
            </p>
            <button
              className="button secondary full"
              onClick={() => {
                setDescription("");
                setDialog("issue");
              }}
            >
              <MessageSquare size={15} />
              反馈问题
            </button>
          </section>
          {skill.can_edit && (
            <section className="panel owner-actions">
              <h3>维护技能</h3>
              <button
                onClick={() => {
                  setLabel(skill.display_name);
                  setCategory(skill.category_id);
                  setTags(skill.tags.join(", "));
                  setDialog("edit");
                }}
              >
                <Pencil size={15} />
                编辑展示信息
              </button>
              <button
                onClick={() => navigate("/app/upload?skill_id=" + skillId)}
              >
                <GitBranch size={15} />
                上传新版本
              </button>
              {skill.current_version && (
                <>
                  <button
                    onClick={() => {
                      setVisibility("custom");
                      setGrants(skill.acl || []);
                      setDialog("share");
                    }}
                  >
                    <Share2 size={15} />
                    申请共享范围
                  </button>
                  <button onClick={() => setDialog("revoke")}>
                    <ShieldCheck size={15} />
                    收回共享授权
                  </button>
                </>
              )}
              {chosen &&
                ["published", "deprecated"].includes(chosen.status) && (
                  <button
                    className="danger"
                    onClick={() => {
                      setStatus(
                        chosen.status === "deprecated"
                          ? "revoked"
                          : "deprecated",
                      );
                      setDialog("status");
                    }}
                  >
                    废弃 / 撤回此版本
                  </button>
                )}
            </section>
          )}
        </aside>
      </div>
      {chosen && chosen.scan.length > 0 && (
        <Notice>
          此版本包含需人工核对的内容：
          {chosen.scan.map((s) => s.path + " — " + s.message).join("；")}
        </Notice>
      )}
      {dialog === "install" && (
        <Modal
          title="安装到你的 Agent"
          subtitle="平台提供授权内容和执行指引，由 Agent 在本机完成文件操作。"
          close={() => setDialog(null)}
          wide={!!plan}
        >
          {!plan ? (
            <Form
              onSubmit={() =>
                void perform(() =>
                  post<Plan>("/installations/preflight", {
                    skill_id: skillId,
                    version,
                    client,
                    scope,
                  }),
                ).then((value) => {
                  if (value) setPlan(value);
                })
              }
            >
              <Field label="客户端">
                <select
                  value={client}
                  onChange={(e) => setClient(e.target.value)}
                >
                  <option value="qoder-ide">Qoder IDE</option>
                  <option value="codex-desktop">Codex 桌面端</option>
                  <option value="cursor">Cursor</option>
                  <option value="claude-code">Claude Code</option>
                </select>
              </Field>
              <Field label="安装范围">
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                >
                  <option value="project">当前项目</option>
                  <option value="user">当前用户</option>
                </select>
              </Field>
              <button className="button primary" disabled={busy}>
                查看安装指引
              </button>
            </Form>
          ) : (
            <>
              <Notice good>检查通过。此步骤尚未在你的电脑上安装文件。</Notice>
              <ol className="instruction-list">
                {plan.agent_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <CopyButton
                label="复制给 Agent 的安装请求"
                text={`请通过 Enterprise Skill Hub MCP，以当前授权身份安装 ${skillId} 版本 ${version} 到 ${client} 的${scope === "project" ? "当前项目" : "用户级目录"}。调用 install_skill，使用自身文件能力校验并落盘，保存安装收据，验证客户端发现结果后调用 report_install_result。存在同名或本地修改时先确认。`}
              />
            </>
          )}
        </Modal>
      )}
      {dialog === "share" && (
        <Modal
          title="申请共享 Skill"
          subtitle="跨团队 / 个人共享由团队负责人审批；企业共享由平台管理员审批。"
          close={() => setDialog(null)}
        >
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post("/skills/" + skillId + "/sharing", {
                    visibility,
                    acl: visibility === "custom" ? grants : [],
                  }),
                "共享申请已提交，请在审核中心查看",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Field label="目标范围">
              <select
                value={visibility}
                onChange={(e) => setVisibility(e.target.value)}
              >
                {Object.entries(visibilityText).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            {visibility === "custom" && (
              <div className="grant-picker">
                <h4>授权团队</h4>
                {targets.data?.teams.map((t) => (
                  <label key={t.id}>
                    <input
                      type="checkbox"
                      checked={grants.some(
                        (g) => g.type === "team" && g.id === t.id,
                      )}
                      onChange={() => toggleGrant({ type: "team", id: t.id })}
                    />
                    {t.name}
                  </label>
                ))}
                <h4>授权成员</h4>
                {targets.data?.users.map((u) => (
                  <label key={u.id}>
                    <input
                      type="checkbox"
                      checked={grants.some(
                        (g) => g.type === "user" && g.id === u.id,
                      )}
                      onChange={() => toggleGrant({ type: "user", id: u.id })}
                    />
                    {u.name}
                  </label>
                ))}
              </div>
            )}
            <button
              className="button primary"
              disabled={busy || (visibility === "custom" && !grants.length)}
            >
              提交共享申请
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "issue" && (
        <Modal title="反馈 Skill 问题" close={() => setDialog(null)}>
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post("/skills/" + skillId + "/issues", {
                    version,
                    kind,
                    description,
                  }),
                "问题已提交，可以在问题反馈中跟进",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Field label="问题类型">
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="description">描述或指令错误</option>
                <option value="broken">文件损坏 / 无法使用</option>
                <option value="security">安全问题</option>
                <option value="other">其他</option>
              </select>
            </Field>
            <Field
              label="问题描述"
              hint="请提供复现信息，不要包含密码或访问凭据。"
            >
              <textarea
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={4000}
                required
              />
            </Field>
            <button
              className="button primary"
              disabled={busy || !description.trim()}
            >
              提交反馈
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "edit" && (
        <Modal
          title="编辑展示信息"
          subtitle="修改文件内容请上传新版本；共享范围需单独审批。"
          close={() => setDialog(null)}
        >
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  patch("/skills/" + skillId, {
                    revision: skill.revision,
                    display_name: label,
                    category_id: category,
                    tags: tags
                      .split(",")
                      .map((t) => t.trim())
                      .filter(Boolean),
                  }),
                "展示信息已保存",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Field label="显示名称">
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                required
                maxLength={100}
              />
            </Field>
            <Field label="分类">
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {categories.data?.map((c) => (
                  <option key={c.category_id} value={c.category_id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="标签（逗号分隔）">
              <input value={tags} onChange={(e) => setTags(e.target.value)} />
            </Field>
            <button className="button primary" disabled={busy}>
              保存信息
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "status" && (
        <Modal title="管理版本生命周期" close={() => setDialog(null)}>
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post(
                    "/skills/" + skillId + "/versions/" + version + "/status",
                    { status },
                  ),
                "版本状态已更新",
              ).then((res) => {
                if (res) setDialog(null);
              })
            }
          >
            <Notice>
              该操作会停止此版本的新安装，不会删除其他用户已安装的本地文件。
            </Notice>
            <Field label="版本状态">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                {chosen?.status === "published" && (
                  <option value="deprecated">废弃：保留历史说明</option>
                )}
                <option value="revoked">撤回：停止新下载和安装</option>
              </select>
            </Field>
            <button className="button danger-button" disabled={busy}>
              确认更新版本状态
            </button>
          </Form>
        </Modal>
      )}
      {dialog === "revoke" && (
        <Modal title="收回共享授权" close={() => setDialog(null)}>
          <Notice>
            收回后，此 Skill
            仅自己可见。后续请求会重新检查权限，已安装文件不会被远程删除。
          </Notice>
          <div className="modal-actions">
            <button
              className="button secondary"
              onClick={() => setDialog(null)}
            >
              取消
            </button>
            <button
              className="button danger-button"
              disabled={busy}
              onClick={() =>
                void perform(
                  () =>
                    post("/skills/" + skillId + "/sharing/revoke", {
                      visibility: "private",
                      acl: [],
                    }),
                  "共享授权已收回",
                ).then((res) => {
                  if (res) setDialog(null);
                })
              }
            >
              确认收回
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
