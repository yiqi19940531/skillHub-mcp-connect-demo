import { useState } from "react";
import { Empty, Failure, Loading, Notice, useData } from "../ui";

type Counts = {
  detail_views: number;
  content_fetches: number;
  downloads: number;
  installations: number;
  discoveries: number;
  favorites: number;
};
type Row = Counts & {
  skill_id: string;
  display_name: string;
  team_name: string;
};
type Stats = { totals: Counts; items: Row[] };
const columns: [keyof Counts, string, string][] = [
  ["detail_views", "详情访问", "成功读取详情的请求数"],
  ["content_fetches", "内容获取", "成功获取正文或文本附件"],
  ["downloads", "归档下载", "下载票据成功兑换次数"],
  ["installations", "安装完成上报", "按安装记录去重的写入上报"],
  ["discoveries", "客户端发现", "Agent 上报已被客户端发现"],
  ["favorites", "当前收藏", "当前有效收藏数量"],
];

export default function Usage() {
  const [days, setDays] = useState(30);
  const stats = useData<Stats>(`/analytics?days=${days}`);
  return (
    <>
      <div className="section-heading">
        <div>
          <h2>技能使用与下载</h2>
          <p className="muted">仅汇总你当前有权访问的已发布技能。</p>
        </div>
        <label className="field">
          统计时间范围
          <select
            aria-label="统计时间范围"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>最近 7 天</option>
            <option value={30}>最近 30 天</option>
            <option value={90}>最近 90 天</option>
          </select>
        </label>
      </div>
      <Notice>
        使用量以平台侧详情访问、内容获取和 Agent 上报为依据。Agent 离线执行
        Skill
        的次数需要客户端另行上报。收藏数展示当前值，其余按所选时间范围统计。
      </Notice>
      {stats.loading ? (
        <Loading />
      ) : stats.error ? (
        <Failure text={stats.error} />
      ) : (
        stats.data && (
          <>
            <div className="usage-grid">
              {columns.map(([key, label, hint]) => (
                <section className="panel usage-card" key={key}>
                  <span>{label}</span>
                  <strong>{stats.data!.totals[key]}</strong>
                  <small className="muted">{hint}</small>
                </section>
              ))}
            </div>
            {stats.data.items.length ? (
              <div className="panel table-panel">
                <table>
                  <thead>
                    <tr>
                      <th>Skill</th>
                      <th>所属团队</th>
                      {columns.map(([key, label]) => (
                        <th key={key}>{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stats.data.items.map((row) => (
                      <tr key={row.skill_id}>
                        <td>
                          <strong>{row.display_name}</strong>
                          <br />
                          <small className="muted">{row.skill_id}</small>
                        </td>
                        <td>{row.team_name}</td>
                        {columns.map(([key]) => (
                          <td key={key}>{row[key]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title="暂无可统计的技能"
                text="获得技能访问权限后，可在此查看平台使用情况。"
              />
            )}
          </>
        )
      )}
    </>
  );
}
