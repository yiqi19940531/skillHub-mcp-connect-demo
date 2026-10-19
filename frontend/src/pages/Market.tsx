import { useEffect, useState } from "react";
import {
  ArrowRight,
  Code2,
  Layers3,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { post, remove } from "../api";
import {
  Badge,
  Empty,
  Failure,
  Loading,
  SectionLink,
  SkillGrid,
  useApp,
  useData,
} from "../ui";
import type { Category, Page, Skill } from "../types";

export default function Market() {
  const { me, navigate, perform } = useApp();
  const params = new URLSearchParams(window.location.search);
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [category, setCategory] = useState(params.get("category") || ""),
    [team, setTeam] = useState(params.get("team") || ""),
    [sort, setSort] = useState("recent"),
    [tags, setTags] = useState(""),
    [filters, setFilters] = useState(false),
    [cursor, setCursor] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setCursor("");
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  const filter = new URLSearchParams({ query: search, limit: "12", sort });
  if (category) filter.set("category", category);
  if (team) filter.set("team_id", team);
  if (cursor) filter.set("cursor", cursor);
  tags
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .forEach((t) => filter.append("tags", t));
  const result = useData<Page<Skill>>("/skills?" + filter),
    categories = useData<Category[]>("/categories"),
    favorites = useData<Skill[]>("/favorites"),
    recommended = useData<(Skill & { recommendation_reason: string })[]>(
      "/recommendations?limit=3",
    );
  const allCount = (categories.data || []).reduce((sum, c) => sum + c.count, 0);
  const favorite = (s: Skill) =>
    void perform(
      () =>
        s.favorite
          ? remove("/favorites/" + s.skill_id)
          : post("/favorites", { skill_id: s.skill_id }),
      s.favorite ? "已取消收藏" : "已加入我的收藏",
    );
  return (
    <>
      <section className="market-hero">
        <div className="hero-copy">
          <span className="hero-eyebrow">
            <Sparkles size={14} /> YOUR TEAM'S KNOW-HOW, READY TO USE
          </span>
          <h1>
            好经验，<span>值得被复用。</span>
          </h1>
          <p>发现经过验证的团队 Skills，让你的 Agent 更懂工作。</p>
          <button
            className="hero-link"
            onClick={() => navigate("/app/settings")}
          >
            连接你的 Agent
            <ArrowRight size={15} />
          </button>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="art-card art-back">
            <Code2 size={26} />
            <span>knowledge.md</span>
            <div />
            <div />
          </div>
          <div className="art-card art-front">
            <span className="art-logo">
              <Layers3 size={28} />
            </span>
            <strong>SKILL.md</strong>
            <div />
            <div />
            <span className="art-status">
              <span /> READY FOR YOUR AGENT
            </span>
          </div>
          <span className="art-spark spark-one">✦</span>
          <span className="art-spark spark-two">✧</span>
        </div>
      </section>
      <div className="metrics-row">
        <div>
          <span className="metric-icon violet">
            <Layers3 size={19} />
          </span>
          <span>
            <strong>
              {allCount}
              <small>个</small>
            </strong>
            <label>可访问的 Skills</label>
          </span>
        </div>
        <div>
          <span className="metric-icon amber">
            <Sparkles size={19} />
          </span>
          <span>
            <strong>
              {favorites.data?.length ?? "—"}
              <small>个</small>
            </strong>
            <label>我的收藏</label>
          </span>
        </div>
        <div>
          <span className="metric-icon blue">
            <Code2 size={19} />
          </span>
          <span>
            <strong>
              {me.teams.filter((t) => !t.internal).length}
              <small>个</small>
            </strong>
            <label>所属业务团队</label>
          </span>
        </div>
        <div className="permission-metric">
          <ShieldCheck size={22} />
          <span>
            <strong>按身份安全共享</strong>
            <label>仅展示你有权访问的技能</label>
          </span>
        </div>
      </div>
      <section className="market-section">
        <div className="section-heading">
          <div>
            <h2>
              发现 Skills{" "}
              <span className="count">{result.data?.total ?? allCount}</span>
            </h2>
            <p>把团队积累，带进下一次任务</p>
          </div>
          <button
            className="button primary"
            onClick={() => navigate("/app/upload")}
          >
            <Plus size={16} />
            上传 Skill
          </button>
        </div>
        <div className="search-toolbar">
          <div className="search-box">
            <Search size={18} />
            <input
              aria-label="搜索 Skills"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索技能名称、描述或标签…"
            />
            {query && (
              <button aria-label="清空搜索" onClick={() => setQuery("")}>
                <X size={15} />
              </button>
            )}
            <kbd>⌕</kbd>
          </div>
          <select
            aria-label="排序方式"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setCursor("");
            }}
          >
            <option value="recent">最近发布</option>
            <option value="popular">最多收藏</option>
            <option value="relevance">相关程度</option>
          </select>
          <button
            className={`button secondary ${filters ? "selected" : ""}`}
            onClick={() => setFilters(!filters)}
          >
            <SlidersHorizontal size={15} />
            筛选
          </button>
        </div>
        {filters && (
          <div className="advanced-filters">
            <label>
              所属团队
              <select
                value={team}
                onChange={(e) => {
                  setTeam(e.target.value);
                  setCursor("");
                }}
              >
                <option value="">全部授权范围</option>
                {me.teams.map((t) => (
                  <option key={t.team_id} value={t.team_id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              标签
              <input
                placeholder="多个标签用逗号分隔"
                value={tags}
                onChange={(e) => {
                  setTags(e.target.value);
                  setCursor("");
                }}
              />
            </label>
            <button
              className="text-button"
              onClick={() => {
                setTeam("");
                setTags("");
                setCategory("");
                setQuery("");
                setCursor("");
              }}
            >
              重置筛选
            </button>
          </div>
        )}
        <div className="category-tabs">
          <button
            className={!category ? "active" : ""}
            onClick={() => {
              setCategory("");
              setCursor("");
            }}
          >
            全部技能<span>{allCount}</span>
          </button>
          {categories.data?.map((c) => (
            <button
              key={c.category_id}
              className={category === c.category_id ? "active" : ""}
              onClick={() => {
                setCategory(c.category_id);
                setCursor("");
              }}
            >
              {c.name.split(" / ")[0]}
              <span>{c.count}</span>
            </button>
          ))}
        </div>
        {result.loading ? (
          <Loading />
        ) : result.error ? (
          <Failure text={result.error} />
        ) : result.data?.items.length ? (
          <SkillGrid skills={result.data.items} favorite={favorite} />
        ) : (
          <Empty
            title="没有找到匹配的 Skill"
            text="试试其他关键词，或调整分类、团队和标签。"
          />
        )}
        <div className="list-bottom">
          <span>
            {result.data
              ? `当前展示 ${result.data.items.length} 个，共 ${result.data.total} 个已授权技能`
              : ""}
          </span>
          <div>
            {cursor && (
              <button
                className="button secondary small"
                onClick={() => setCursor("")}
              >
                返回首页
              </button>
            )}
            {result.data?.next_cursor && (
              <button
                className="button secondary small"
                onClick={() => setCursor(result.data!.next_cursor!)}
              >
                下一页
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      </section>
      {recommended.data && recommended.data.length > 0 && (
        <section className="recommendation-section">
          <div className="section-heading">
            <div>
              <h2>
                <Sparkles size={18} />
                值得一试
              </h2>
              <p>从你有权访问的技能中发现更多可能</p>
            </div>
            <SectionLink onClick={() => navigate("/app/categories")}>
              浏览全部分类
            </SectionLink>
          </div>
          <div className="recommendation-grid">
            {recommended.data.map((s) => (
              <button
                key={s.skill_id}
                className="recommendation"
                onClick={() => navigate("/app/skills/" + s.skill_id)}
              >
                <span className="skill-symbol small-symbol blue">
                  <Code2 size={20} />
                </span>
                <span>
                  <strong>{s.display_name}</strong>
                  <small>{s.tags.join(" · ")}</small>
                </span>
                <Badge tone="neutral">v{s.current_version}</Badge>
                <ArrowRight size={16} />
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
