// 工作台（/）：统计卡 + Excel报表导出（仅 admin）+ 待回访清单 + 本月业绩排行
// 数据源：GET /api/dashboard/summary；导出走 GET /api/exports/deals（blob 下载）

import { useEffect, useState } from "react";
import { Button, Card, Col, DatePicker, Row, Space, Statistic, Table, Tag, Typography, message } from "antd";
import { FileExcelOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import { api, errMsg } from "../api";
import { SOURCE_MAP, STAGE_MAP } from "../api";
import { getMe } from "../auth";
import ImportCard from "./ImportCard";

interface DueItem {
  id: number;
  company_name: string;
  contact_name: string;
  phone: string;
  stage: string;
  owner_name: string;
  next_followup_at: string | null;
  overdue: boolean;
}

interface Summary {
  scope: string;
  overdue: number;
  today_due: number;
  week_new: number;
  month_amount: number;
  month_units: number;
  deal_ranking: { name: string; amount: number }[];
  by_source: { source: string; count: number }[];
  funnel: { stage: string; count: number }[];
  due_list: DueItem[];
}

export default function Dashboard() {
  const [data, setData] = useState<Summary | null>(null);
  const me = getMe();
  const nav = useNavigate();
  const [reportMonth, setReportMonth] = useState<dayjs.Dayjs>(dayjs());
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setData(r.data));
  }, []);

  const doExport = async (type: "detail" | "report") => {
    setExporting(type);
    try {
      const res = await api.get("/exports/deals", {
        params: { type, year: reportMonth.year(), month: reportMonth.month() + 1 },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = type === "detail" ? "销售明细表汇总.xlsx" : "业绩汇总.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setExporting(null);
    }
  };

  if (!data) return null;

  return (
    <div>
      {me?.role !== "boss" && <ImportCard me={me} />}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic title="今日待跟进" value={data.today_due} suffix="家" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已超期未回访"
              value={data.overdue}
              suffix="家"
              valueStyle={{ color: data.overdue > 0 ? "#cf1322" : undefined }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="本周新建客户" value={data.week_new} suffix="家" />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月成交"
              value={data.month_amount}
              precision={2}
              prefix="¥"
              valueStyle={{ color: "#0c8c5c" }}
              suffix={
                <span style={{ fontSize: 14, color: "#999" }}>
                  {" "}
                  / {data.month_units} 台
                </span>
              }
            />
          </Card>
        </Col>
      </Row>

      {me?.role === "admin" && (
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="Excel报表导出" size="small">
            <Space size={12} wrap align="center">
              <DatePicker
                picker="month"
                value={reportMonth}
                onChange={(v) => setReportMonth(v)}
                allowClear={false}
                style={{ width: 140 }}
              />
              <Button icon={<FileExcelOutlined />} loading={exporting === "detail"} onClick={() => doExport("detail")}>
                销售明细表汇总
              </Button>
              <Button icon={<FileExcelOutlined />} loading={exporting === "report"} onClick={() => doExport("report")}>
                业绩汇总（含数据分类）
              </Button>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                全量数据（仅管理员可导出）
              </Typography.Text>
            </Space>
          </Card>
        </Col>
      </Row>
      )}

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={14}>
          <Card title="待回访清单（含超期）" size="small">
            <Table<DueItem>
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
              dataSource={data.due_list}
              onRow={(r) => ({ onClick: () => nav(`/customers/${r.id}`), style: { cursor: "pointer" } })}
              columns={[
                { title: "公司", dataIndex: "company_name", ellipsis: true },
                { title: "联系人", dataIndex: "contact_name", width: 90 },
                { title: "电话", dataIndex: "phone", width: 130 },
                ...(data.scope === "all" ? [{ title: "负责人", dataIndex: "owner_name", width: 80 }] : []),
                {
                  title: "下次跟进",
                  dataIndex: "next_followup_at",
                  width: 150,
                  render: (v: string) => (v ? v.replace("T", " ").slice(0, 16) : "-"),
                },
                {
                  title: "状态",
                  dataIndex: "overdue",
                  width: 80,
                  render: (v: boolean) =>
                    v ? <Tag color="red">超期</Tag> : <Tag color="green">待办</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="来源分布" size="small" style={{ marginBottom: 16 }}>
            {data.by_source.map((s) => (
              <div key={s.source} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <Typography.Text>{SOURCE_MAP[s.source] || s.source}</Typography.Text>
                <Typography.Text strong>{s.count}</Typography.Text>
              </div>
            ))}
          </Card>
          <Card title="阶段漏斗" size="small" style={{ marginBottom: 16 }}>
            {data.funnel.map((s) => (
              <div key={s.stage} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                <Tag color={STAGE_MAP[s.stage]?.color}>{STAGE_MAP[s.stage]?.text || s.stage}</Tag>
                <Typography.Text strong>{s.count}</Typography.Text>
              </div>
            ))}
          </Card>
          {data.scope === "all" && data.deal_ranking.length > 0 && (
            <Card title="本月业绩排行" size="small">
              {data.deal_ranking.map((r, i) => (
                <div key={r.name} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
                  <Typography.Text>
                    {i + 1}. {r.name}
                  </Typography.Text>
                  <Typography.Text strong style={{ color: "#0c8c5c" }}>
                    ¥{r.amount.toLocaleString()}
                  </Typography.Text>
                </div>
              ))}
            </Card>
          )}
        </Col>
      </Row>
      {me?.role === "boss" && (
        <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
          老板账号为只读模式：可查看全部数据，操作类功能请联系管理员。
        </Typography.Text>
      )}
    </div>
  );
}
