import { useEffect, useState } from "react";
import {
  Archive,
  ArrowRight,
  BookOpen,
  Boxes,
  FolderHeart,
  Network,
  Pencil,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { patch, post, remove } from "../api";
import {
  Badge,
  Empty,
  Failure,
  Field,
  Form,
  Loading,
  Modal,
  PageTitle,
  SkillGrid,
  useApp,
  useData,
} from "../ui";
import type { Category, Collection, Page, Skill, Team } from "../types";

export function Favorites() {
  const result = useData<Skill[]>("/favorites"),
    { perform, navigate } = useApp();
  return (
    <>
      <PageTitle
        eyebrow="YOUR TOOLKIT"
        title="我的收藏"
        description="把常用方法放在手边，在需要时快速找到。"
        action={
          <button className="button secondary" onClick={() => navigate("/app")}>
            发现更多 Skills
            <ArrowRight size={15} />
          </button>
        }
      />
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : result.data?.length ? (
        <SkillGrid
          skills={result.data}
          favorite={(s) =>
            void perform(() => remove("/favorites/" + s.skill_id), "已取消收藏")
          }
        />
      ) : (
        <Empty
          title="收藏你的第一个 Skill"
          text="在技能卡片点击星标，它就会出现在这里。"
          action={
            <button className="button primary" onClick={() => navigate("/app")}>
              <Star size={15} />
              发现 Skills
            </button>
          }
        />
      )}
    </>
  );
}

export function Categories() {
  const result = useData<Category[]>("/categories"),
    { navigate } = useApp();
  return (
    <>
      <PageTitle
        eyebrow="EXPLORE BY CATEGORY"
        title="按领域，发现好方法"
        description="从代码到创作，找到适合当前任务的团队能力。"
      />
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : (
        <div className="category-grid">
          {result.data?.map((c, i) => (
            <button
              className="category-card"
              key={c.category_id}
              onClick={() => navigate("/app?category=" + c.category_id)}
            >
              <span
                className={`skill-symbol ${["violet", "green", "orange", "blue", "pink", "teal", "blue"][i]}`}
              >
                <Boxes size={24} />
              </span>
              <h2>{c.name}</h2>
              <p>
                <strong>{c.count}</strong> 个已授权技能
              </p>
              <span className="category-cta">
                浏览分类
                <ArrowRight size={16} />
              </span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export function Teams() {
  const result = useData<Team[]>("/teams"),
    { navigate } = useApp();
  return (
    <>
      <PageTitle
        eyebrow="TEAM KNOWLEDGE"
        title="团队技能库"
        description="在团队中沉淀实践，让协作从已有经验出发。"
      />
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : (
        <div className="team-grid">
          {result.data?.map((team) => (
            <article className="panel team-card" key={team.team_id}>
              <div className="team-card-top">
                <span className="team-avatar">
                  <Network size={24} />
                </span>
                <Badge tone={team.archived ? "neutral" : "team"}>
                  {team.archived
                    ? "已归档"
                    : team.membership_role === "owner"
                      ? "团队负责人"
                      : team.membership_role === "admin"
                        ? "平台管理"
                        : "团队成员"}
                </Badge>
              </div>
              <h2>{team.name}</h2>
              <p>{team.description}</p>
              <div className="team-card-actions">
                <button
                  className="button secondary"
                  onClick={() => navigate("/app?team=" + team.team_id)}
                >
                  查看团队技能
                  <ArrowRight size={14} />
                </button>
                <button
                  className="text-button"
                  onClick={() =>
                    navigate("/app/collections?team=" + team.team_id)
                  }
                >
                  收藏集
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}

export function Collections() {
  const { me, perform, busy, navigate } = useApp(),
    list = useData<Collection[]>(
      "/collections" +
        (new URLSearchParams(window.location.search).get("team")
          ? "?team_id=" +
            new URLSearchParams(window.location.search).get("team")
          : ""),
    );
  const [selected, setSelected] = useState<Collection | null>(null),
    [mode, setMode] = useState<"create" | "edit" | "add" | null>(null),
    [name, setName] = useState(""),
    [team, setTeam] = useState(
      me.teams.find(
        (t) => t.membership_role === "owner" || t.membership_role === "admin",
      )?.team_id || "",
    ),
    [skillId, setSkillId] = useState("");
  const contents = useData<Skill[]>(
      selected ? "/collections/" + selected.collection_id + "/skills" : null,
    ),
    skills = useData<Page<Skill>>(mode === "add" ? "/skills?limit=100" : null);
  const manageable = me.teams.filter(
    (t) => !t.archived && ["owner", "admin"].includes(t.membership_role || ""),
  );
  useEffect(() => {
    if (!selected || !list.data) return;
    const current = list.data.find(
      (item) => item.collection_id === selected.collection_id,
    );
    if (current && current.revision !== selected.revision) setSelected(current);
  }, [list.data]);
  const save = async () => {
    const res =
      mode === "create"
        ? await perform(
            () => post("/collections", { team_id: team, name }),
            "收藏集已创建",
          )
        : await perform(
            () =>
              patch("/collections/" + selected!.collection_id, {
                name,
                revision: selected!.revision,
              }),
            "收藏集已更新",
          );
    if (res) {
      setMode(null);
      setSelected(null);
    }
  };
  return (
    <>
      <PageTitle
        eyebrow="CURATED TOGETHER"
        title="团队收藏集"
        description="把相关技能组织成工具箱，团队成员可以直接发现和使用。"
        action={
          manageable.length > 0 && (
            <button
              className="button primary"
              onClick={() => {
                setName("");
                setMode("create");
              }}
            >
              <Plus size={16} />
              新建收藏集
            </button>
          )
        }
      />
      {list.loading ? (
        <Loading />
      ) : list.error ? (
        <Failure text={list.error} />
      ) : list.data?.length ? (
        <>
          <div className="collection-grid">
            {list.data.map((collection) => (
              <button
                className={`collection-card ${selected?.collection_id === collection.collection_id ? "selected" : ""}`}
                key={collection.collection_id}
                onClick={() => setSelected(collection)}
              >
                <span className="folder-symbol">
                  <FolderHeart size={29} />
                </span>
                <h3>{collection.name}</h3>
                <p>
                  {me.teams.find((t) => t.team_id === collection.owner_team_id)
                    ?.name || "授权团队"}
                  <span>·</span>
                  {collection.count} 个技能
                </p>
                <span className="collection-open">
                  打开收藏集
                  <ArrowRight size={15} />
                </span>
                {collection.can_manage && <Badge tone="neutral">可管理</Badge>}
              </button>
            ))}
          </div>
          {selected && (
            <section className="panel collection-content">
              <div className="section-heading">
                <div>
                  <h2>
                    <BookOpen size={19} />
                    {selected.name}
                  </h2>
                  <p>集合仅组织技能，不改变技能本身的访问权限。</p>
                </div>
                <div className="button-row">
                  {selected.can_manage && (
                    <>
                      <button
                        className="button secondary small"
                        onClick={() => {
                          setName(selected.name);
                          setMode("edit");
                        }}
                      >
                        <Pencil size={14} />
                        编辑
                      </button>
                      <button
                        className="button primary small"
                        onClick={() => {
                          setSkillId("");
                          setMode("add");
                        }}
                      >
                        <Plus size={14} />
                        添加 Skill
                      </button>
                    </>
                  )}
                </div>
              </div>
              {contents.loading ? (
                <Loading />
              ) : contents.error ? (
                <Failure text={contents.error} />
              ) : contents.data?.length ? (
                <div className="compact-list">
                  {contents.data.map((skill) => (
                    <div className="compact-row" key={skill.skill_id}>
                      <span className="skill-symbol small-symbol violet">
                        {skill.name.slice(0, 2).toUpperCase()}
                      </span>
                      <button
                        className="compact-main"
                        onClick={() =>
                          navigate("/app/skills/" + skill.skill_id)
                        }
                      >
                        <strong>{skill.display_name}</strong>
                        <small>{skill.description}</small>
                      </button>
                      <Badge tone="neutral">v{skill.current_version}</Badge>
                      {selected.can_manage && (
                        <button
                          className="icon-button danger"
                          aria-label={"移除 " + skill.display_name}
                          onClick={() =>
                            void perform(
                              () =>
                                remove(
                                  "/collections/" +
                                    selected.collection_id +
                                    "/skills/" +
                                    skill.skill_id,
                                ),
                              "已从收藏集移除",
                            )
                          }
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <Empty
                  title="收藏集暂无可访问技能"
                  text="负责人可以添加所有集合成员都有权访问的 Skill。"
                />
              )}
            </section>
          )}
        </>
      ) : (
        <Empty
          title="还没有团队收藏集"
          text="团队负责人可以创建并维护收藏集。"
        />
      )}
      {(mode === "create" || mode === "edit") && (
        <Modal
          title={mode === "create" ? "新建团队收藏集" : "编辑收藏集"}
          close={() => setMode(null)}
        >
          <Form onSubmit={() => void save()}>
            <Field label="收藏集名称">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                required
              />
            </Field>
            {mode === "create" && (
              <Field label="所属团队">
                <select value={team} onChange={(e) => setTeam(e.target.value)}>
                  {manageable.map((t) => (
                    <option key={t.team_id} value={t.team_id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <div className="modal-actions">
              {mode === "edit" && (
                <button
                  type="button"
                  className="button danger-button"
                  disabled={busy}
                  onClick={() =>
                    void perform(
                      () =>
                        patch("/collections/" + selected!.collection_id, {
                          revision: selected!.revision,
                          archived: true,
                        }),
                      "收藏集已归档",
                    ).then((res) => {
                      if (res) {
                        setMode(null);
                        setSelected(null);
                      }
                    })
                  }
                >
                  <Archive size={14} />
                  归档
                </button>
              )}
              <button
                className="button primary"
                disabled={busy || !name.trim()}
              >
                保存收藏集
              </button>
            </div>
          </Form>
        </Modal>
      )}
      {mode === "add" && selected && (
        <Modal
          title="添加 Skill 到收藏集"
          subtitle="所有集合成员都必须具备该 Skill 的访问权限。"
          close={() => setMode(null)}
        >
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  post("/collections/" + selected.collection_id + "/skills", {
                    skill_id: skillId,
                  }),
                "Skill 已加入收藏集",
              ).then((res) => {
                if (res) setMode(null);
              })
            }
          >
            <Field label="选择 Skill">
              <select
                required
                value={skillId}
                onChange={(e) => setSkillId(e.target.value)}
              >
                <option value="">请选择</option>
                {skills.data?.items.map((s) => (
                  <option key={s.skill_id} value={s.skill_id}>
                    {s.display_name} · {s.team_name}
                  </option>
                ))}
              </select>
            </Field>
            <button className="button primary" disabled={busy || !skillId}>
              添加到收藏集
            </button>
          </Form>
        </Modal>
      )}
    </>
  );
}
