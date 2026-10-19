import {
  cloneElement,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { FormEvent, ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Copy,
  LoaderCircle,
  Package,
  Star,
  X,
} from "lucide-react";
import { api } from "./api";
import type { Me, Skill } from "./types";

type Context = {
  me: Me;
  path: string;
  revision: number;
  busy: boolean;
  navigate: (path: string) => void;
  notify: (text: string, error?: boolean) => void;
  refresh: () => void;
  perform: <T>(
    fn: () => Promise<T>,
    message?: string,
  ) => Promise<T | undefined>;
};
export const AppContext = createContext<Context>(null!);
export const useApp = () => useContext(AppContext);

export function useData<T>(path: string | null) {
  const { revision } = useApp();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    if (!path) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api<T>(path, { signal: controller.signal })
      .then((value) => {
        setData(value);
        setLoading(false);
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setError(error.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [path, revision]);
  return { data, error, loading };
}

export const statusText: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审核",
  published: "已发布",
  rejected: "已驳回",
  deprecated: "已废弃",
  revoked: "已撤回",
  pending: "待处理",
  approved: "已通过",
  open: "待处理",
  in_progress: "处理中",
  resolved: "已解决",
  closed: "已关闭",
  agent_action_required: "等待 Agent 执行",
  written: "文件已写入",
  discovered: "客户端已发现",
  failed: "执行失败",
  cancelled: "已取消",
  uninstalled: "已卸载",
  superseded: "已被新记录替代",
};
export const visibilityText: Record<string, string> = {
  private: "仅自己",
  team: "所属团队",
  enterprise: "企业共享",
  custom: "指定团队 / 成员",
};
export const date = (value?: string | null) =>
  value
    ? new Date(value).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
export const bytes = (value: number) =>
  value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KB`;

export function Badge({
  value,
  children,
  tone,
}: {
  value?: string;
  children?: ReactNode;
  tone?: string;
}) {
  return (
    <span className={`badge ${tone || value || ""}`}>
      {children || statusText[value || ""] || value}
    </span>
  );
}
export function Loading() {
  return (
    <div className="state loading">
      <LoaderCircle className="spin" size={23} />
      <span>正在加载技能库…</span>
    </div>
  );
}
export function Empty({
  title = "这里还没有内容",
  text = "试试调整筛选条件，或添加你的第一个 Skill。",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="state empty">
      <span className="empty-icon">
        <Package size={27} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Failure({ text }: { text: string }) {
  return (
    <div className="state error-state">
      <AlertCircle size={25} />
      <h3>暂时无法读取内容</h3>
      <p>{text}</p>
    </div>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {isValidElement<Record<string, unknown>>(children)
        ? cloneElement(children, { "aria-label": label })
        : children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Form({
  children,
  onSubmit,
}: {
  children: ReactNode;
  onSubmit: () => void;
}) {
  return (
    <form
      className="form-stack"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      {children}
    </form>
  );
}

export function Modal({
  title,
  subtitle,
  children,
  close,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key === "Tab") {
        const nodes = Array.from(
          ref.current?.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input,textarea,select,a[href]",
          ) || [],
        );
        const first = nodes[0],
          last = nodes.at(-1);
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, []); // The modal owns focus for its lifetime.
  return (
    <div
      className="modal-scrim"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <div className="modal-heading">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={close} aria-label="关闭">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function CopyButton({
  text,
  label = "复制",
  className = "button secondary",
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const { notify } = useApp();
  const [copied, setCopied] = useState(false);
  return (
    <button
      className={className}
      onClick={() => {
        navigator.clipboard
          .writeText(text)
          .then(() => {
            setCopied(true);
            notify("已复制到剪贴板");
            setTimeout(() => setCopied(false), 1800);
          })
          .catch(() => notify("复制失败，请手动选择内容", true));
      }}
    >
      {copied ? <Check size={15} /> : <Copy size={15} />}{" "}
      {copied ? "已复制" : label}
    </button>
  );
}

const palette: Record<string, string> = {
  "ai-coding": "violet",
  testing: "green",
  devops: "orange",
  data: "blue",
  aigc: "pink",
  "api-mcp": "teal",
  office: "blue",
};
export function SkillCard({
  skill,
  favorite,
}: {
  skill: Skill;
  favorite: (s: Skill) => void;
}) {
  const { navigate } = useApp();
  return (
    <article className="skill-card">
      <div className="card-top">
        <span
          className={`skill-symbol ${palette[skill.category_id] || "blue"}`}
        >
          {skill.category_id === "api-mcp"
            ? "mcp"
            : skill.name
                .split("-")
                .map((part) => part[0])
                .slice(0, 2)
                .join("")
                .toUpperCase()}
        </span>
        <button
          className={`icon-button star ${skill.favorite ? "selected" : ""}`}
          onClick={() => favorite(skill)}
          aria-label={
            skill.favorite
              ? "取消收藏 " + skill.display_name
              : "收藏 " + skill.display_name
          }
        >
          <Star size={18} fill={skill.favorite ? "currentColor" : "none"} />
        </button>
      </div>
      <button
        className="card-link"
        onClick={() => navigate("/app/skills/" + skill.skill_id)}
      >
        <h3>
          {skill.display_name}
          <ArrowUpRight size={15} />
        </h3>
        <code>{skill.name}</code>
        <p>{skill.description}</p>
      </button>
      <div className="tags">
        {skill.tags.slice(0, 3).map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="card-foot">
        <span className="author">
          <span className="mini-avatar">{skill.author_name[0]}</span>
          {skill.author_name}
          <i>·</i>
          <span>
            {skill.visibility === "enterprise" ? "企业共享" : skill.team_name}
          </span>
        </span>
        <span className="version">v{skill.current_version}</span>
      </div>
    </article>
  );
}
export function SkillGrid({
  skills,
  favorite,
}: {
  skills: Skill[];
  favorite: (s: Skill) => void;
}) {
  return (
    <div className="skill-grid">
      {skills.map((skill) => (
        <SkillCard key={skill.skill_id} skill={skill} favorite={favorite} />
      ))}
    </div>
  );
}
export function Notice({
  children,
  good = false,
}: {
  children: ReactNode;
  good?: boolean;
}) {
  return (
    <div className={`notice ${good ? "good" : ""}`}>
      {good ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
      <div>{children}</div>
    </div>
  );
}
export function SectionLink({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-button" onClick={onClick}>
      {children}
      <ChevronRight size={15} />
    </button>
  );
}
