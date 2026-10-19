import { useState } from "react";
import {
  Check,
  ClipboardCheck,
  MessageSquare,
  Search,
  Share2,
  X,
} from "lucide-react";
import Markdown from "react-markdown";
import { patch, post } from "../api";
import {
  Badge,
  Empty,
  Failure,
  Field,
  Form,
  Loading,
  Modal,
  Notice,
  PageTitle,
  date,
  useApp,
  useData,
  visibilityText,
} from "../ui";
import type { Issue, Review, Targets } from "../types";

export function Reviews() {
  const targets = useData<Targets>("/share-targets");
  const recipient = (grant: { type: string; id: string }) =>
    (grant.type === "team" ? targets.data?.teams : targets.data?.users)?.find(
      (item) => item.id === grant.id,
    )?.name || grant.id;
  const { perform, busy } = useApp(),
    result = useData<Review[]>("/reviews"),
    [selected, setSelected] = useState<Review | null>(null),
    [filter, setFilter] = useState("pending"),
    [reason, setReason] = useState("");
  const decide = async (decision: string) => {
    const value = await perform(
      () =>
        post("/reviews/" + selected!.review_id + "/decision", {
          decision,
          reason,
        }),
      decision === "approved" ? "申请已通过" : "申请已驳回",
    );
    if (value) setSelected(null);
  };
  const rows =
    result.data?.filter((r) => filter === "all" || r.decision === filter) || [];
  return (
    <>
      <PageTitle
        eyebrow="TRUST THROUGH REVIEW"
        title="审核中心"
        description="确认内容和共享边界，让每一份团队经验都可追溯。"
      />
      <div className="tab-bar">
        <button
          className={filter === "pending" ? "active" : ""}
          onClick={() => setFilter("pending")}
        >
          待处理{" "}
          <span>
            {result.data?.filter((r) => r.decision === "pending").length || 0}
          </span>
        </button>
        <button
          className={filter === "all" ? "active" : ""}
          onClick={() => setFilter("all")}
        >
          全部记录
        </button>
      </div>
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : rows.length ? (
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>申请内容</th>
                <th>类型</th>
                <th>申请人</th>
                <th>状态</th>
                <th>申请时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.review_id}>
                  <td>
                    <strong>{r.skill_name}</strong>
                    <small>
                      {r.skill_id} · v{r.version}
                    </small>
                  </td>
                  <td>
                    <Badge tone="neutral">
                      {r.kind === "share" ? "共享范围" : "内容发布"}
                    </Badge>
                  </td>
                  <td>{r.submitter_name}</td>
                  <td>
                    <Badge value={r.decision} />
                  </td>
                  <td>{date(r.created_at)}</td>
                  <td>
                    <button
                      className="button secondary small"
                      onClick={() => {
                        setSelected(r);
                        setReason("");
                      }}
                    >
                      <Search size={13} />
                      {r.can_decide && r.decision === "pending"
                        ? "查看并审核"
                        : "查看详情"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="当前没有待处理申请"
          text="你提交或有权处理的内容审核、共享申请会显示在这里。"
        />
      )}
      {selected && (
        <Modal
          title={selected.kind === "share" ? "共享范围审核" : "Skill 内容审核"}
          subtitle={
            selected.skill_name +
            " · " +
            selected.version +
            " · " +
            selected.submitter_name
          }
          close={() => setSelected(null)}
          wide
        >
          {selected.kind === "share" ? (
            <div className="review-sharing">
              <Share2 size={22} />
              <div>
                <h3>
                  目标范围：{visibilityText[selected.proposed_visibility || ""]}
                </h3>
                {selected.proposed_acl?.map((g) => (
                  <code key={g.type + g.id}>
                    {g.type === "team" ? "团队" : "成员"}：{recipient(g)}
                  </code>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div className="review-summary">
                <span>
                  检查结果：
                  {selected.version_detail?.risk === "low"
                    ? "基础检查通过"
                    : "需人工核对"}
                </span>
                <span>{selected.version_detail?.manifest.length} 个文件</span>
              </div>
              {selected.version_detail?.proposed_metadata && (
                <Notice>
                  本次版本申请的可见范围：
                  {
                    visibilityText[
                      selected.version_detail.proposed_metadata.visibility
                    ]
                  }
                  {selected.version_detail.proposed_metadata.visibility ===
                    "custom" &&
                    " · " +
                      selected.version_detail.proposed_metadata.acl
                        .map(recipient)
                        .join("、")}
                </Notice>
              )}
              {selected.version_detail?.scan.map((warning, i) => (
                <Notice key={i}>
                  {warning.path}：{warning.message}
                </Notice>
              ))}
              <div className="markdown review-markdown">
                <Markdown>
                  {selected.instructions?.replace(
                    /^---\r?\n[\s\S]*?\r?\n---\r?\n/,
                    "",
                  ) || ""}
                </Markdown>
              </div>
              <div className="digest-line">
                SHA-256 <code>{selected.version_detail?.sha256}</code>
              </div>
            </>
          )}
          {selected.reason && <Notice>处理说明：{selected.reason}</Notice>}
          {selected.decision === "pending" && selected.can_decide ? (
            <>
              <Field label="审核说明（驳回时必填）">
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  maxLength={2000}
                  placeholder="记录审核意见，帮助作者完善内容…"
                />
              </Field>
              <div className="modal-actions">
                <button
                  className="button danger-button"
                  disabled={busy || !reason.trim()}
                  onClick={() => void decide("rejected")}
                >
                  <X size={15} />
                  驳回申请
                </button>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void decide("approved")}
                >
                  <Check size={15} />
                  通过申请
                </button>
              </div>
            </>
          ) : selected.decision === "pending" ? (
            <Notice>
              当前账号不能审批此申请。申请人和作者不得自审；企业范围共享需要平台管理员权限。
            </Notice>
          ) : (
            <div className="review-done">
              <ClipboardCheck size={17} />
              <Badge value={selected.decision} />
            </div>
          )}
        </Modal>
      )}
    </>
  );
}

export function Issues() {
  const { perform, busy } = useApp(),
    result = useData<Issue[]>("/issues"),
    [selected, setSelected] = useState<Issue | null>(null),
    [status, setStatus] = useState("in_progress"),
    [resolution, setResolution] = useState(""),
    [filter, setFilter] = useState("all");
  const rows =
    result.data?.filter((i) => filter === "all" || i.status === filter) || [];
  return (
    <>
      <PageTitle
        eyebrow="FEEDBACK LOOP"
        title="让 Skill 变得更好"
        description="跟进你的反馈，或处理你维护的技能中遇到的问题。"
      />
      <div className="tab-bar">
        {[
          ["all", "全部反馈"],
          ["open", "待处理"],
          ["in_progress", "处理中"],
          ["resolved", "已解决"],
          ["closed", "已关闭"],
        ].map(([id, label]) => (
          <button
            key={id}
            className={filter === id ? "active" : ""}
            onClick={() => setFilter(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {result.loading ? (
        <Loading />
      ) : result.error ? (
        <Failure text={result.error} />
      ) : rows.length ? (
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>Skill / 问题</th>
                <th>类型</th>
                <th>状态</th>
                <th>提交时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((issue) => (
                <tr key={issue.issue_id}>
                  <td>
                    <strong>
                      {issue.skill_id} · v{issue.version}
                    </strong>
                    <small className="truncate">{issue.description}</small>
                  </td>
                  <td>
                    {
                      {
                        description: "描述错误",
                        broken: "无法使用",
                        security: "安全问题",
                        other: "其他",
                      }[issue.kind]
                    }
                  </td>
                  <td>
                    <Badge value={issue.status} />
                  </td>
                  <td>{date(issue.created_at)}</td>
                  <td>
                    <button
                      className="button secondary small"
                      onClick={() => {
                        setSelected(issue);
                        setStatus(issue.status);
                        setResolution(issue.resolution);
                      }}
                    >
                      <MessageSquare size={13} />
                      查看反馈
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="暂无相关问题反馈"
          text="在 Skill 详情中提交问题，作者和平台管理员可以跟进处理。"
        />
      )}
      {selected && (
        <Modal
          title="问题反馈详情"
          subtitle={selected.skill_id + " · v" + selected.version}
          close={() => setSelected(null)}
        >
          <blockquote className="issue-description">
            {selected.description}
          </blockquote>
          <Badge value={selected.status} />
          <Form
            onSubmit={() =>
              void perform(
                () =>
                  patch("/issues/" + selected.issue_id, {
                    status,
                    resolution,
                    revision: selected.revision,
                  }),
                "处理状态已保存",
              ).then((value) => {
                if (value) setSelected(null);
              })
            }
          >
            <Field label="处理状态">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="open">待处理</option>
                <option value="in_progress">处理中</option>
                <option value="resolved">已解决</option>
                <option value="closed">已关闭</option>
              </select>
            </Field>
            <Field label="处理说明">
              <textarea
                rows={4}
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                maxLength={2000}
              />
            </Field>
            <Notice>
              仅技能作者和平台管理员可以保存处理结果；提交者可在这里跟进。
            </Notice>
            <button
              className="button primary"
              disabled={busy || !selected.can_manage}
            >
              保存处理结果
            </button>
          </Form>
        </Modal>
      )}
    </>
  );
}
