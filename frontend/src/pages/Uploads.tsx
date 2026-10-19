import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  FileArchive,
  FileText,
  GitBranch,
  Plus,
  Send,
  UploadCloud,
} from "lucide-react";
import { api, post } from "../api";
import {
  Badge,
  Empty,
  Failure,
  Field,
  Form,
  Loading,
  Notice,
  PageTitle,
  date,
  useApp,
  useData,
  visibilityText,
} from "../ui";
import type { Category, Grant, Skill, Targets } from "../types";

export function MyUploads() {
  const { navigate, perform, busy } = useApp(),
    result = useData<Skill[]>("/my/uploads");
  return (
    <>
      <PageTitle
        eyebrow="YOUR CONTRIBUTIONS"
        title="我的上传"
        description="从一份草稿开始，让你的经验成为团队的共同能力。"
        action={
          <button
            className="button primary"
            onClick={() => navigate("/app/upload")}
          >
            <Plus size={16} />
            上传 Skill
          </button>
        }
      />
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : result.data?.length ? (
        <div className="upload-list">
          {result.data.map((skill) => (
            <section className="panel upload-item" key={skill.skill_id}>
              <div className="section-heading">
                <div>
                  <h2>{skill.display_name}</h2>
                  <p>
                    {skill.name} <span>·</span> {skill.team_name}
                  </p>
                </div>
                <button
                  className="button secondary small"
                  onClick={() => navigate("/app/skills/" + skill.skill_id)}
                >
                  查看详情
                  <ArrowRight size={14} />
                </button>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>状态</th>
                    <th>基础检查</th>
                    <th>创建时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {skill.versions?.map((version) => (
                    <tr key={version.version}>
                      <td>
                        <GitBranch size={13} /> {version.version}
                      </td>
                      <td>
                        <Badge value={version.status} />
                      </td>
                      <td>
                        {version.scan.length
                          ? `${version.scan.length} 项待人工核对`
                          : "基础检查通过"}
                      </td>
                      <td>{date(version.created_at)}</td>
                      <td>
                        <div className="button-row">
                          {["draft", "rejected"].includes(version.status) && (
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                void perform(
                                  () =>
                                    post(
                                      "/skills/" + skill.skill_id + "/reviews",
                                      { version: version.version },
                                    ),
                                  "已提交审核",
                                )
                              }
                            >
                              <Send size={13} />
                              提交审核
                            </button>
                          )}
                          {version.review_id && (
                            <button
                              className="text-button"
                              onClick={() => navigate("/app/reviews")}
                            >
                              查看审核
                            </button>
                          )}
                          {["draft", "rejected"].includes(version.status) && (
                            <button
                              className="text-button"
                              onClick={() =>
                                navigate(
                                  "/app/upload?skill_id=" +
                                    skill.skill_id +
                                    "&version=" +
                                    version.version,
                                )
                              }
                            >
                              修改草稿
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ))}
        </div>
      ) : (
        <Empty
          title="让你的经验成为第一个 Skill"
          text="上传 SKILL.md 或 ZIP，审核通过后即可按授权范围共享。"
          action={
            <button
              className="button primary"
              onClick={() => navigate("/app/upload")}
            >
              <Plus size={15} />
              上传 Skill
            </button>
          }
        />
      )}
    </>
  );
}

const template =
  "---\nname: my-team-helper\ndescription: Help the team complete a repeatable workflow with clear steps.\n---\n\n# 团队工作助手\n\n1. 先确认输入信息和任务目标。\n2. 按团队约定执行并核对结果。\n3. 说明不确定信息，不自动执行生产变更。\n";
export function Upload() {
  const { me, perform, busy, navigate } = useApp(),
    mySkills = useData<Skill[]>("/my/uploads"),
    categories = useData<Category[]>("/categories");
  const params = new URLSearchParams(window.location.search);
  const [existing, setExisting] = useState(params.get("skill_id") || ""),
    [version, setVersion] = useState(params.get("version") || "0.1.0"),
    [mode, setMode] = useState<"file" | "text">("file"),
    [file, setFile] = useState<File | null>(null),
    [text, setText] = useState(template),
    [team, setTeam] = useState(
      me.teams.find((t) => !t.archived && !t.internal)?.team_id ||
        me.teams[0]?.team_id ||
        "",
    ),
    [visibility, setVisibility] = useState("team"),
    [label, setLabel] = useState(""),
    [category, setCategory] = useState("ai-coding"),
    [tags, setTags] = useState(""),
    [grants, setGrants] = useState<Grant[]>([]),
    [drag, setDrag] = useState(false);
  const targets = useData<Targets>(
      visibility === "custom" ? "/share-targets" : null,
    ),
    fileInput = useRef<HTMLInputElement>(null);
  const existingDetail = useData<Skill>(
    existing ? "/skills/" + encodeURIComponent(existing) : null,
  );
  const existingSkill =
    existingDetail.data?.skill_id === existing ? existingDetail.data : null;
  const sourceVersion = params.get("version") || existingSkill?.current_version;
  const sourceFile = useData<{ content: string }>(
    existing && sourceVersion
      ? "/skills/" +
          encodeURIComponent(existing) +
          "/versions/" +
          encodeURIComponent(sourceVersion) +
          "/files/SKILL.md"
      : null,
  );
  useEffect(() => {
    const found =
      existingSkill || mySkills.data?.find((s) => s.skill_id === existing);
    if (found) {
      setTeam(found.owner_team_id);
      setLabel(found.display_name);
      setCategory(found.category_id);
      setTags(found.tags.join(", "));
      setVisibility(found.visibility);
      setGrants(found.acl || []);
      if (!params.get("version")) {
        const parts = (found.current_version || "0.0.0").split(".");
        setVersion(`${parts[0]}.${parts[1]}.${Number(parts[2]) + 1}`);
      }
    }
  }, [existing, mySkills.data, existingSkill]);
  useEffect(() => {
    if (existing && sourceFile.data) {
      setText(sourceFile.data.content);
      const source = existingSkill?.versions?.find(
        (v) => v.version === sourceVersion,
      );
      if (params.get("version") && source?.manifest.length === 1)
        setMode("text");
    }
  }, [existing, sourceFile.data, existingSkill, sourceVersion]);
  const chooseFile = (value: File | undefined) => {
    if (!value) return;
    setFile(value);
  };
  const submit = async () => {
    const metadata = {
      team_id: team,
      visibility,
      version,
      skill_id: existing || undefined,
      display_name: label || undefined,
      category_id: category,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      acl: visibility === "custom" ? grants : [],
      request_id: crypto.randomUUID(),
    };
    const result = await perform(async () => {
      if (mode === "text")
        return post<{ skill: Skill }>("/skills", {
          ...metadata,
          skill_md: text,
        });
      const form = new FormData();
      form.append("file", file!);
      form.append("metadata", JSON.stringify(metadata));
      return api<{ skill: Skill }>("/uploads", { method: "POST", body: form });
    }, "草稿已保存，提交审核后才能发布");
    if (result)
      navigate(
        existingSkill && existingSkill.owner_user_id !== me.user_id
          ? "/app/skills/" + existing
          : "/app/uploads",
      );
  };
  const toggle = (value: Grant) =>
    setGrants((items) =>
      items.some((g) => g.type === value.type && g.id === value.id)
        ? items.filter((g) => g.type !== value.type || g.id !== value.id)
        : [...items, value],
    );
  return (
    <>
      <PageTitle
        eyebrow="SHARE WHAT WORKS"
        title={existing ? "更新 Skill 版本" : "分享一个好方法"}
        description="只上传你选择并有权共享的文件。所有内容先保存为草稿，审核通过后发布。"
      />
      <Form onSubmit={() => void submit()}>
        <div className="upload-layout">
          <section className="panel upload-main">
            <h2>
              01 <span>上传技能内容</span>
            </h2>
            <Field label="创建或更新">
              <select
                value={existing}
                onChange={(e) => setExisting(e.target.value)}
              >
                <option value="">创建新 Skill（全平台名称唯一）</option>
                {existingSkill &&
                  !mySkills.data?.some((s) => s.skill_id === existing) && (
                    <option value={existing}>
                      {existingSkill.display_name}
                    </option>
                  )}
                {mySkills.data?.map((s) => (
                  <option key={s.skill_id} value={s.skill_id}>
                    更新：{s.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="segmented">
              <button
                type="button"
                className={mode === "file" ? "active" : ""}
                onClick={() => setMode("file")}
              >
                <FileArchive size={15} />
                上传文件
              </button>
              <button
                type="button"
                className={mode === "text" ? "active" : ""}
                onClick={() => setMode("text")}
              >
                <FileText size={15} />
                粘贴 SKILL.md
              </button>
            </div>
            {mode === "file" ? (
              <>
                <input
                  ref={fileInput}
                  className="visually-hidden"
                  type="file"
                  accept=".md,.zip"
                  onChange={(e) => chooseFile(e.target.files?.[0])}
                />
                <button
                  type="button"
                  className={`drop-zone ${drag ? "drag" : ""}`}
                  onClick={() => fileInput.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDrag(true);
                  }}
                  onDragLeave={() => setDrag(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDrag(false);
                    chooseFile(e.dataTransfer.files[0]);
                  }}
                >
                  <span className="upload-cloud">
                    <UploadCloud size={28} />
                  </span>
                  <strong>
                    {file ? file.name : "点击选择文件，或拖放到这里"}
                  </strong>
                  <p>
                    {file
                      ? `${(file.size / 1024).toFixed(1)} KB · 点击重新选择`
                      : "支持 SKILL.md 或 ZIP，文件最大 2 MiB"}
                  </p>
                  <span className="button secondary small">选择文件</span>
                </button>
              </>
            ) : (
              <Field
                label="SKILL.md 内容"
                hint="须包含 name 和 description frontmatter；name 创建后不可直接更名。"
              >
                <textarea
                  className="code-input"
                  rows={16}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  required
                  maxLength={65536}
                />
              </Field>
            )}
            <Notice>
              ZIP 内须有一个有效 SKILL.md，展开总量不超过 10 MiB、文件不超过 100
              个。凭据文件和危险路径会被拒绝。
            </Notice>
          </section>
          <aside className="panel upload-metadata">
            <h2>
              02 <span>配置技能信息</span>
            </h2>
            <Field label="显示名称">
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="留空则使用 Skill name"
                maxLength={100}
              />
            </Field>
            <div className="form-grid">
              <Field label="版本号">
                <input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder="0.1.0"
                  required
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
            </div>
            <Field label="所属团队">
              <select
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                disabled={!!existing}
                required
              >
                {me.teams
                  .filter((t) => !t.archived)
                  .map((t) => (
                    <option key={t.team_id} value={t.team_id}>
                      {t.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="发布后的可见范围">
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
              <div className="grant-picker compact">
                <h4>选择授权对象</h4>
                {targets.data?.teams.map((t) => (
                  <label key={t.id}>
                    <input
                      type="checkbox"
                      checked={grants.some(
                        (g) => g.type === "team" && g.id === t.id,
                      )}
                      onChange={() => toggle({ type: "team", id: t.id })}
                    />
                    {t.name}
                  </label>
                ))}
                {targets.data?.users.map((u) => (
                  <label key={u.id}>
                    <input
                      type="checkbox"
                      checked={grants.some(
                        (g) => g.type === "user" && g.id === u.id,
                      )}
                      onChange={() => toggle({ type: "user", id: u.id })}
                    />
                    {u.name}
                  </label>
                ))}
              </div>
            )}
            <Field label="标签" hint="使用英文逗号分隔，最多 20 个。">
              <input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="例如：review, java, team"
              />
            </Field>
            <button
              className="button primary full"
              disabled={
                busy ||
                !team ||
                (mode === "file" && !file) ||
                (visibility === "custom" && !grants.length)
              }
            >
              <UploadCloud size={16} />
              {busy ? "正在检查并保存…" : "检查并保存草稿"}
            </button>
            <p className="small-text muted">
              保存后可在“我的上传”提交审核。发布版本不可覆盖。
            </p>
          </aside>
        </div>
      </Form>
    </>
  );
}
