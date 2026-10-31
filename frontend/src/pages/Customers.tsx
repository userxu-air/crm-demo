// 客户总览（/customers）：ProTable 列表 + 筛选（关键词/来源/阶段/负责人/只看超期）+ 新建客户
// 数据源：GET/POST/PATCH/DELETE /api/customers；sales 仅见本人，boss 只读（无新建按钮）

import { useEffect, useRef, useState } from "react";
import { Button, DatePicker, Form, Input, Modal, Popconfirm, Select, Switch, Tag, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ActionType, ProColumns } from "@ant-design/pro-components";
import { ModalForm, ProTable } from "@ant-design/pro-components";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import { api, errMsg, SOURCE_MAP, STAGE_MAP } from "../api";
import { getMe } from "../auth";

interface Customer {
  id: number;
  company_name: string;
  contact_name: string;
  phone: string;
  wechat: string;
  source: string;
  stage: string;
  owner_id: number;
  owner_name: string;
  region: string;
  demand: string;
  last_contacted_at: string | null;
  next_followup_at: string | null;
  created_at: string;
  import_batch?: string;
}

export default function Customers() {
  const me = getMe();
  const actionRef = useRef<ActionType>(null);
  const nav = useNavigate();
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [ownerFilter, setOwnerFilter] = useState<Record<string, string>>({});
  const isAdmin = me?.role === "admin";
  const isBoss = me?.role === "boss";
  const canWrite = me?.role === "admin" || me?.role === "sales";

  useEffect(() => {
    if (isAdmin) {
      api.get("/users").then((r) => {
        const m: Record<string, string> = {};
        r.data.filter((u: any) => u.is_active).forEach((u: any) => (m[String(u.id)] = u.name));
        setOwnerFilter(m);
      });
    }
  }, []);

  const delCustomer = async (r: Customer) => {
    try {
      await api.delete(`/customers/${r.id}`);
      message.success(`已删除「${r.company_name}」及其跟进记录`);
      actionRef.current?.reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const columns: ProColumns<Customer>[] = [
    { title: "公司名称", dataIndex: "company_name", ellipsis: true, width: 180 },
    { title: "联系人", dataIndex: "contact_name", width: 80 },
    { title: "电话", dataIndex: "phone", width: 130, render: (_, r) => r.phone || "-" },
    {
      title: "来源",
      dataIndex: "import_batch",
      width: 80,
      render: (_, r) => (r.import_batch ? <Tag color="orange">导入</Tag> : <Tag>手工</Tag>),
    },
    {
      title: "来源",
      dataIndex: "source",
      width: 90,
      valueEnum: Object.fromEntries(Object.entries(SOURCE_MAP).map(([k, v]) => [k, { text: v }])),
    },
    {
      title: "阶段",
      dataIndex: "stage",
      width: 90,
      valueEnum: Object.fromEntries(
        Object.entries(STAGE_MAP).map(([k, v]) => [k, { text: v.text }])
      ),
      render: (_, r) => <Tag color={STAGE_MAP[r.stage]?.color}>{STAGE_MAP[r.stage]?.text}</Tag>,
    },
    ...(isAdmin || isBoss
      ? [
          {
            title: "负责人",
            dataIndex: "owner_id",
            width: 90,
            render: (_: unknown, r: Customer) => r.owner_name,
            valueEnum: ownerFilter as unknown as Record<string, { text: string }>,            fieldProps: { placeholder: "按销售筛选" },
          } as ProColumns<Customer>,
        ]
      : []),
    {
      title: "下次跟进",
      dataIndex: "next_followup_at",
      width: 145,
      render: (v: any) => {
        if (!v) return "-";
        const t = dayjs(v);
        const overdue = t.isBefore(dayjs()) && true;
        return (
          <span style={{ color: overdue ? "#cf1322" : undefined }}>
            {t.format("MM-DD HH:mm")}
            {overdue ? " 超期" : ""}
          </span>
        );
      },
    },
    {
      title: "最近联系",
      dataIndex: "last_contacted_at",
      width: 145,
      render: (v: any) => (v ? dayjs(v).format("MM-DD HH:mm") : "未联系"),
    },
    {
      title: "操作",
      valueType: "option",
      width: 110,
      render: (_, r) => [
        <a key="detail" onClick={() => nav(`/customers/${r.id}`)}>
          详情
        </a>,
        ...(isAdmin
          ? [
              <Popconfirm
                key="del"
                title="删除客户"
                description={`确定删除「${r.company_name}」？跟进记录一并删除，不可恢复。`}
                okText="删除"
                okButtonProps={{ danger: true }}
                cancelText="取消"
                onConfirm={() => delCustomer(r)}
              >
                <a style={{ color: "#cf1322" }}>删除</a>
              </Popconfirm>,
            ]
          : []),
      ],
    },
  ];

  const createCustomer = async (v: Record<string, unknown>) => {
    const body: Record<string, unknown> = { ...v };
    if (v.next_followup_at) body.next_followup_at = (v.next_followup_at as dayjs.Dayjs).toISOString();
    else delete body.next_followup_at;
    try {
      await api.post("/customers", body);
      message.success("客户已创建（3 天内回访已自动提醒）");
      actionRef.current?.reload();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  return (
    <ProTable<Customer>
      headerTitle={isAdmin ? "客户总览（全量可管理）" : isBoss ? "客户总览（只读）" : "我的客户"}
      actionRef={actionRef}
      rowKey="id"
      search={{ labelWidth: "auto" }}
      options={{ reload: true, density: false, setting: false }}
      toolBarRender={() => [
        <span key="od" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          只看超期
          <Switch checked={onlyOverdue} onChange={setOnlyOverdue} />
        </span>,
        ...(canWrite
          ? [
              <ModalForm
                key="create"
                title="新建客户"
                trigger={
                  <Button type="primary">
                    <PlusOutlined /> 新建客户
                  </Button>
                }
                width={520}
                modalProps={{ destroyOnClose: true }}
                onFinish={createCustomer}
                initialValues={{ source: "sales_init" }}
              >
                <Form.Item name="company_name" label="公司名称" rules={[{ required: true, message: "必填" }]}>
                  <Input placeholder="如：东莞XX包装制品厂" />
                </Form.Item>
                <Form.Item name="contact_name" label="联系人" rules={[{ required: true, message: "必填" }]}>
                  <Input placeholder="如：客户经理" />
                </Form.Item>
                <Form.Item name="phone" label="手机号" rules={[{ required: true, message: "必填（防撞单）" }]}>
                  <Input placeholder="手机号，系统自动查重" maxLength={30} />
                </Form.Item>
                <Form.Item name="wechat" label="微信">
                  <Input />
                </Form.Item>
                <Form.Item name="source" label="来源" rules={[{ required: true }]}>
                  <Select options={Object.entries(SOURCE_MAP).map(([k, v]) => ({ value: k, label: v }))} />
                </Form.Item>
                <Form.Item name="region" label="地区">
                  <Input placeholder="如：广东东莞" />
                </Form.Item>
                <Form.Item name="demand" label="需求机型 / 备注">
                  <Input.TextArea rows={2} placeholder="如：圆瓶贴标机 2 台，关注精度" />
                </Form.Item>
                <Form.Item name="next_followup_at" label="下次跟进时间" extra="不填则默认 3 天后回访">
                  <DatePicker showTime style={{ width: "100%" }} />
                </Form.Item>
              </ModalForm>,
            ]
          : []),
      ]}
      request={async (params) => {
        const q: Record<string, unknown> = {
          page: params.current || 1,
          page_size: params.pageSize || 20,
        };
        if (params.company_name) q.keyword = params.company_name;
        if (params.source) q.source = params.source;
        if (params.stage) q.stage = params.stage;
        if (params.owner_id) q.owner_id = params.owner_id;
        if (onlyOverdue) q.overdue = true;
        const { data } = await api.get("/customers", { params: q });
        return { data: data.items, total: data.total, success: true };
      }}
      columns={columns}
      pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 家` }}
    />
  );
}
