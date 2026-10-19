import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Boxes,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Code2,
  Compass,
  Layers3,
  LogOut,
  MessageSquare,
  Network,
  Search,
  Settings2,
  ShieldCheck,
  Star,
  Users,
  X,
} from "lucide-react";
import { api, post } from "./api";
import type { Me } from "./types";
import { AppContext } from "./ui";
import Market from "./pages/Market";
import SkillDetail from "./pages/SkillDetail";
import { Categories, Collections, Favorites, Teams } from "./pages/Library";
import { MyUploads, Upload } from "./pages/Uploads";
import { Issues, Reviews } from "./pages/Reviews";
import Administration from "./pages/Administration";
import Settings from "./pages/Settings";

const accounts = [
  {
    username: "zhangsan",
    name: "张三",
    password: "ZhangSan@123456",
    team: "研发一组",
  },
  { username: "lisi", name: "李四", password: "LiSi@123456", team: "研发二组" },
  {
    username: "admin",
    name: "管理员",
    password: "Admin@123456",
    team: "平台管理",
  },
  {
    username: "wangwu",
    name: "王五",
    password: "WangWu@123456",
    team: "运维组",
  },
  {
    username: "zhaoliu",
    name: "赵六",
    password: "ZhaoLiu@123456",
    team: "AI 应用组",
  },
];

function Login({ loggedIn }: { loggedIn: (me: Me) => void }) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const me = await post<Me>("/auth/login", { username, password });
      loggedIn(me);
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="login-layout">
      <section className="login-story">
        <div className="brand">
          <span className="brand-icon">
            <Layers3 size={23} />
          </span>
          <span>
            Skill Hub<small>企业技能中心</small>
          </span>
        </div>
        <div className="story-content">
          <span className="story-label">
            <span /> BUILT FOR YOUR TEAM
          </span>
          <h1>
            让团队经验，
            <br />
            成为每一次工作
            <br />的<span>起点。</span>
          </h1>
          <p>
            将经过验证的方法沉淀为 Skill。
            <br />
            连接你的 Agent，让好的工作方式在团队中流动。
          </p>
          <div className="story-features">
            <span>
              <Search size={17} />
              发现团队知识
            </span>
            <span>
              <ShieldCheck size={17} />
              按身份安全共享
            </span>
            <span>
              <Code2 size={17} />
              连接你的 Agent
            </span>
          </div>
        </div>
        <div className="story-bottom">
          <span>LOCAL FIRST. KNOWLEDGE SHARED.</span>
          <span>01 / SKILL HUB</span>
        </div>
        <div className="story-art" aria-hidden="true">
          <div />
          <div />
          <div />
        </div>
      </section>
      <section className="login-form-area">
        <div className="login-card">
          <div className="eyebrow">WELCOME BACK</div>
          <h2>登录你的技能空间</h2>
          <p className="muted">使用团队账号，访问你有权使用的 Skills。</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <label className="field">
              <span>账号</span>
              <input
                autoComplete="username"
                placeholder="请输入账号"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>密码</span>
              <input
                type="password"
                autoComplete="current-password"
                placeholder="请输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </label>
            {error && (
              <div className="inline-error" role="alert">
                {error}
              </div>
            )}
            <button className="button primary full" disabled={busy}>
              {busy ? "正在登录…" : "登录 Skill Hub"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="demo-accounts">
            <div className="divider">
              <span>快速体验 · 仅供本机演示</span>
            </div>
            <div className="account-options">
              {accounts.map((account) => (
                <button
                  key={account.username}
                  type="button"
                  onClick={() => {
                    setUsername(account.username);
                    setPassword(account.password);
                    setError("");
                  }}
                >
                  <span className="mini-avatar">{account.name[0]}</span>
                  <span>
                    {account.name}
                    <small>{account.team}</small>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <p className="login-footer">
          <ShieldCheck size={14} />
          身份隔离 · 文件持久化 · 本机运行
        </p>
      </section>
    </div>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null),
    [initial, setInitial] = useState(true),
    [path, setPath] = useState(
      window.location.pathname + window.location.search,
    ),
    [revision, setRevision] = useState(0),
    [pending, setPending] = useState(0),
    [toast, setToast] = useState<{ text: string; error: boolean } | null>(null);
  const navigate = (next: string) => {
    window.history.pushState({}, "", next);
    setPath(next);
    window.scrollTo(0, 0);
  };
  const notify = (text: string, error = false) => setToast({ text, error });
  useEffect(() => {
    const pop = () =>
      setPath(window.location.pathname + window.location.search);
    const expired = () => {
      setMe(null);
      notify("会话已失效，请重新登录", true);
    };
    window.addEventListener("popstate", pop);
    window.addEventListener("session-expired", expired);
    api<Me>("/me", {}, true)
      .then(setMe)
      .catch(() => {})
      .finally(() => setInitial(false));
    return () => {
      window.removeEventListener("popstate", pop);
      window.removeEventListener("session-expired", expired);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  const refresh = () => setRevision((value) => value + 1);
  useEffect(() => {
    if (revision > 0 && me)
      api<Me>("/me")
        .then(setMe)
        .catch(() => {});
    // Re-read effective roles after a mutation, including changes to this account.
  }, [revision]);
  async function perform<T>(
    fn: () => Promise<T>,
    message?: string,
  ): Promise<T | undefined> {
    setPending((value) => value + 1);
    try {
      const result = await fn();
      if (message) notify(message);
      refresh();
      return result;
    } catch (error) {
      notify((error as Error).message, true);
      return undefined;
    } finally {
      setPending((value) => value - 1);
    }
  }
  const loggedIn = (user: Me) => {
    setToast(null);
    setMe(user);
    const next = new URLSearchParams(window.location.search).get("next");
    if (next?.startsWith("/oauth/authorize?request_id=")) {
      window.location.assign(next);
      return;
    }
    navigate("/app");
    refresh();
  };
  if (initial)
    return (
      <div className="boot">
        <Layers3 size={30} />
        <span>正在连接 Skill Hub…</span>
      </div>
    );
  if (!me) return <Login loggedIn={loggedIn} />;
  const isAdmin = me.roles.includes("PlatformAdmin"),
    canReview =
      isAdmin ||
      me.roles.includes("Reviewer") ||
      me.teams.some((t) => t.membership_role === "owner");
  const route = path.split("?")[0],
    nav = [
      { label: "发现 Skills", path: "/app", icon: Compass },
      { label: "分类浏览", path: "/app/categories", icon: Boxes },
      { label: "我的收藏", path: "/app/favorites", icon: Star },
      { label: "团队技能库", path: "/app/teams", icon: Network },
      { label: "团队收藏集", path: "/app/collections", icon: BookOpen },
      { label: "我的上传", path: "/app/uploads", icon: Layers3 },
      ...(canReview
        ? [{ label: "审核中心", path: "/app/reviews", icon: ClipboardCheck }]
        : []),
      { label: "问题反馈", path: "/app/issues", icon: MessageSquare },
      ...(isAdmin
        ? [{ label: "成员与团队", path: "/app/admin", icon: Users }]
        : []),
    ];
  let content;
  if (route.startsWith("/app/skills/"))
    content = (
      <SkillDetail skillId={decodeURIComponent(route.split("/").at(-1)!)} />
    );
  else if (route === "/app/categories") content = <Categories />;
  else if (route === "/app/favorites") content = <Favorites />;
  else if (route === "/app/teams") content = <Teams />;
  else if (route === "/app/collections") content = <Collections />;
  else if (route === "/app/uploads") content = <MyUploads />;
  else if (route === "/app/upload") content = <Upload />;
  else if (route === "/app/reviews") content = <Reviews />;
  else if (route === "/app/issues") content = <Issues />;
  else if (route === "/app/admin") content = <Administration />;
  else if (route === "/app/settings") content = <Settings />;
  else content = <Market key={path} />;
  return (
    <AppContext.Provider
      value={{
        me,
        path,
        revision,
        busy: pending > 0,
        navigate,
        notify,
        refresh,
        perform,
      }}
    >
      <div className="app-shell">
        <aside className="sidebar">
          <button
            className="brand"
            aria-label="Skill Hub 首页"
            onClick={() => navigate("/app")}
          >
            <span className="brand-icon">
              <Layers3 size={23} />
            </span>
            <span>
              Skill Hub<small>企业技能中心</small>
            </span>
          </button>
          <div className="workspace">
            <span className="workspace-avatar">D</span>
            <span>
              Demo Company
              <small>
                <span className="live-dot" />
                本机演示空间
              </small>
            </span>
            <ShieldCheck size={15} />
          </div>
          <div className="nav-label">工作空间</div>
          <nav>
            {nav.map((item) => (
              <button
                key={item.path}
                aria-label={item.label}
                className={route === item.path ? "active" : ""}
                onClick={() => navigate(item.path)}
              >
                <item.icon size={18} />
                <span>{item.label}</span>
                {route === item.path && <span className="nav-active-dot" />}
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="connect-card">
              <span className="connect-icon">
                <Code2 size={20} />
              </span>
              <strong>让 Agent 用上团队经验</strong>
              <p>通过 MCP 连接 Qoder 和 Codex</p>
              <button onClick={() => navigate("/app/settings")}>
                查看接入指南
                <ArrowRight size={14} />
              </button>
            </div>
            <button
              aria-label="设置与接入"
              className={
                route === "/app/settings"
                  ? "side-settings active"
                  : "side-settings"
              }
              onClick={() => navigate("/app/settings")}
            >
              <Settings2 size={18} />
              设置与接入
              <ChevronRight size={15} />
            </button>
            <div className="sidebar-build">
              <span className="live-dot" />
              LOCAL PoC <span>v1.1</span>
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              工作空间
              <ChevronRight size={14} />
              <span>
                {route.startsWith("/app/skills/")
                  ? "Skill 详情"
                  : route === "/app/upload"
                    ? "上传 Skill"
                    : nav.find((n) => n.path === route)?.label || "设置与接入"}
              </span>
            </div>
            <div className="topbar-actions">
              <span className="local-pill">
                <span className="live-dot" />
                本机服务已连接
              </span>
              <button
                className="icon-button"
                aria-label="MCP 接入帮助"
                onClick={() => navigate("/app/settings")}
              >
                <CircleHelp size={18} />
              </button>
              <div className="topbar-divider" />
              <button
                className="profile"
                onClick={() => navigate("/app/settings")}
              >
                <span className="avatar">{me.display_name[0]}</span>
                <span>
                  {me.display_name}
                  <small>
                    {isAdmin
                      ? "平台管理员"
                      : me.teams
                          .filter((t) => !t.internal)
                          .map((t) => t.name)
                          .join(" / ") || "团队成员"}
                  </small>
                </span>
              </button>
              <button
                className="icon-button"
                aria-label="退出登录"
                onClick={() =>
                  void perform(async () => {
                    await post("/auth/logout", {});
                    setMe(null);
                    navigate("/app/login");
                  })
                }
              >
                <LogOut size={16} />
              </button>
            </div>
          </header>
          <main className="main-content">{content}</main>
          <footer className="page-footer">
            <span>Skill Hub · 将经验沉淀为团队能力</span>
            <span>
              你的访问范围由服务端权限控制
              <ShieldCheck size={12} />
            </span>
          </footer>
        </div>
      </div>
      {toast && (
        <div
          className={`toast ${toast.error ? "error" : ""}`}
          role={toast.error ? "alert" : "status"}
        >
          {toast.error ? <X size={17} /> : <Check size={17} />}
          <span>{toast.text}</span>
          <button aria-label="关闭提示" onClick={() => setToast(null)}>
            <X size={14} />
          </button>
        </div>
      )}
    </AppContext.Provider>
  );
}
