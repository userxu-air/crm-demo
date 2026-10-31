// 客户详情（/customers/:id）：基本信息 + 成交记录卡片（表格/录入/编辑）+ 跟进时间线（编辑/删除）+ 附件卡片
// 数据源：/api/customers/{id} 及其 deals / followups / attachments 子资源

import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Modal,
  DatePicker,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Timeline,
  Typography,
  Upload,
  message,
} from "antd";
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DownloadOutlined,
  EditOutlined,
  PlusOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { ModalForm } from "@ant-design/pro-components";
import dayjs from "dayjs";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  errMsg,
  METHOD_MAP,
  SOURCE_MAP,
  STAGE_MAP,
  PRODUCT_LINE_MAP,
  INVOICE_MAP,
  ACCOUNT_MAP,
} from "../api";
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
}

interface Followup {
  id: number;
  method: string;
  content: string;
  next_followup_at: string | null;
  created_at: string;
  user_id: number;
  user_name: string;
}

interface Deal {
  id: number;
  deal_date: string;
  product: string;
  product_line: string;
  quantity: number;
  unit: string;
  unit_price: number;
  amount: number;
  invoice_type: string;
  account: string;
  sales_no: string;
  repurchase: boolean;
  remark: string;
  user_name: string;
}

interface Attachment {
  id: number;
  filename: string;
  size: number;
  content_type: string;
  created_at: string;
  uploader_name: string;
}

const unitOptions = ["台", "套", "卷", "枚", "个"].map((u) => ({ value: u, label: u }));

export default function CustomerDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const me = getMe();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [followups, setFollowups] = useState<Followup[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [users, setUsers] = useState<{ id: number; name: string }[]>([]);
  const isAdmin = me?.role === "admin";
  const canWrite = me?.role === "admin" || me?.role === "sales";
  // 编辑状态：null=新建
  const [dealEdit, setDealEdit] = useState<Deal | null | undefined>(undefined);
  const [fuEdit, setFuEdit] = useState<Followup | null | undefined>(undefined);

  const load = async () => {
    const [c, f, d, a] = await Promise.all([
      api.get(`/customers/${id}`),
      api.get(`/customers/${id}/followups`),
      api.get(`/customers/${id}/deals`),
      api.get(`/customers/${id}/attachments`),
    ]);
    setCustomer(c.data);
    setFollowups(f.data);
    setDeals(d.data);
    setAttachments(a.data);
  };

  useEffect(() => {
    load();
    if (isAdmin) {
      api.get("/users").then((r) =>
        setUsers(r.data.filter((u: any) => u.is_active).map((u: any) => ({ id: u.id, name: u.name })))
      );
    }
  }, [id]);

  if (!customer) return null;

  const changeStage = async (stage: string) => {
    try {
      await api.post(`/customers/${customer.id}/stage`, { stage });
      message.success(`已标记为「${STAGE_MAP[stage].text}」`);
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const transfer = async (owner_id: number) => {
    try {
      await api.patch(`/customers/${customer.id}`, { owner_id });
      message.success("客户已交接");
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const addFollowup = async (v: Record<string, unknown>) => {
    const body: Record<string, unknown> = { method: v.method, content: v.content };
    if (typeof v.next_followup_at === "number") {
      body.next_followup_at = dayjs().add(v.next_followup_at, "day").toISOString();
    }
    try {
      await api.post(`/customers/${customer.id}/followups`, body);
      message.success("跟进已记录，滚动 3 天回访");
      load();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  const updateFollowup = async (v: Record<string, unknown>) => {
    if (!fuEdit) return false;
    try {
      const body: Record<string, unknown> = { method: v.method, content: v.content };
      if (v.next_followup_at) {
        body.next_followup_at = (v.next_followup_at as dayjs.Dayjs).toISOString();
      } else if (v.next_followup_at === null) {
        body.next_followup_at = null;
      }
      await api.patch(`/customers/followups/${fuEdit.id}`, body);
      message.success("跟进已更新");
      load();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  const delFollowup = async (f: Followup) => {
    try {
      await api.delete(`/customers/followups/${f.id}`);
      message.success("跟进已删除");
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const saveDeal = async (v: Record<string, unknown>) => {
    const body: Record<string, unknown> = { ...v };
    if (v.deal_date) body.deal_date = (v.deal_date as dayjs.Dayjs).format("YYYY-MM-DD");
    else body.deal_date = dayjs().format("YYYY-MM-DD");
    // 防重复录入：同客户+同日期+同产品+同金额 已存在 → 二次确认
    if (!dealEdit) {
      const amount = Number(body.amount) || Number(body.quantity || 0) * Number(body.unit_price || 0);
      const dup = deals.find(
        (d) =>
          d.product === body.product &&
          d.deal_date.slice(0, 10) === body.deal_date &&
          Math.abs(d.amount - amount) < 0.01
      );
      if (dup && !(await confirmDupDeal(dup))) return false;
    }
    try {
      if (dealEdit) {
        await api.patch(`/deals/${dealEdit.id}`, body);
        message.success("成交记录已更新");
      } else {
        await api.post(`/customers/${customer.id}/deals`, body);
        message.success("成交已记录");
      }
      load();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  const confirmDupDeal = (dup: Deal) =>
    new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: "疑似重复成交",
        content: `该客户 ${dup.deal_date.slice(0, 10)} 已有一笔「${dup.product}」¥${dup.amount} 的记录，确认要再添加一笔吗？`,
        okText: "仍要添加",
        cancelText: "取消",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

  const delDeal = async (d: Deal) => {
    try {
      await api.delete(`/deals/${d.id}`);
      message.success("成交记录已删除");
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const uploadAttachment = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/customers/${customer?.id}/attachments`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      message.success(`「${file.name}」已上传`);
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
    return false; // 阻止 antd 默认上传
  };

  const downloadAttachment = async (a: Attachment) => {
    try {
      const res = await api.get(`/attachments/${a.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = a.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const delAttachment = async (a: Attachment) => {
    try {
      await api.delete(`/attachments/${a.id}`);
      message.success("附件已删除");
      load();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const fmtSize = (n: number) =>
    n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${(n / 1024).toFixed(0)} KB`;

  const totalAmount = deals.reduce((s, d) => s + (d.amount || 0), 0);

  const dealForm = (
    <ModalForm
      key={dealEdit?.id ?? "deal-new"}
      title={dealEdit ? "编辑成交记录" : "添加成交"}
      open={dealEdit !== undefined}
      onOpenChange={(o) => !o && setDealEdit(undefined)}
      width={620}
      modalProps={{ destroyOnClose: true }}
      onFinish={saveDeal}
      initialValues={
        dealEdit
          ? {
              ...dealEdit,
              deal_date: dayjs(dealEdit.deal_date),
            }
          : { product_line: "right_angle", unit: "台", quantity: 1, deal_date: dayjs() }
      }
    >
      <Row gutter={12}>
        <Col span={16}>
          <Form.Item name="product" label="产品名称" rules={[{ required: true, message: "必填" }]}>
            <Input placeholder="如：直角封口贴标机 / 25mm透明圆标" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="deal_date" label="成交日期" rules={[{ required: true, message: "必填" }]}>
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item name="product_line" label="产品线" rules={[{ required: true }]}>
            <Select options={Object.entries(PRODUCT_LINE_MAP).map(([k, v]) => ({ value: k, label: v }))} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="sales_no" label="来源号">
            <Input placeholder="如：示例号（可选）" />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item name="quantity" label="数量" rules={[{ required: true }]}>
            <InputNumber min={0.001} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="unit" label="单位">
            <Select options={unitOptions} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={12}>
          <Form.Item name="unit_price" label="单价（元）" extra="留空金额手填">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="amount" label="金额（元）" extra="留空按数量×单价">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
      </Row>
      <Row gutter={12}>
        <Col span={8}>
          <Form.Item name="invoice_type" label="开票">
            <Select allowClear options={Object.keys(INVOICE_MAP).map((k) => ({ value: k, label: k }))} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="account" label="收款账户">
            <Select allowClear options={Object.keys(ACCOUNT_MAP).map((k) => ({ value: k, label: k }))} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="repurchase" label="复购" valuePropName="checked">
            <Switch checkedChildren="是" unCheckedChildren="否" />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item name="remark" label="备注">
        <Input.TextArea rows={2} placeholder="回扣 / 赠品 / 付款方式等" />
      </Form.Item>
    </ModalForm>
  );

  const followupForm = (
    <ModalForm
      key={fuEdit?.id ?? "fu-new"}
      title={fuEdit ? "编辑跟进" : "添加跟进"}
      open={fuEdit !== undefined}
      onOpenChange={(o) => !o && setFuEdit(undefined)}
      width={480}
      modalProps={{ destroyOnClose: true }}
      onFinish={fuEdit ? updateFollowup : addFollowup}
      initialValues={
        fuEdit
          ? {
              method: fuEdit.method,
              content: fuEdit.content,
              next_followup_at: fuEdit.next_followup_at ? dayjs(fuEdit.next_followup_at) : undefined,
            }
          : { method: "tel" }
      }
    >
      <Form.Item name="method" label="跟进方式" rules={[{ required: true }]}>
        <Select options={Object.entries(METHOD_MAP).map(([k, v]) => ({ value: k, label: v }))} />
      </Form.Item>
      <Form.Item name="content" label="跟进内容" rules={[{ required: true, message: "请填写内容" }]}>
        <Input.TextArea rows={4} placeholder="沟通了什么、对方关注什么、下一步动作" />
      </Form.Item>
      {fuEdit ? (
        <Form.Item name="next_followup_at" label="下次跟进" extra="清空则不再提醒">
          <DatePicker showTime style={{ width: "100%" }} />
        </Form.Item>
      ) : (
        <Form.Item name="next_followup_at" label="下次跟进" extra="不填默认 3 天后滚动回访">
          <Select
            allowClear
            placeholder="默认 3 天后"
            options={[
              { value: 1, label: "明天" },
              { value: 3, label: "3 天后（默认）" },
              { value: 7, label: "一周后" },
            ]}
          />
        </Form.Item>
      )}
    </ModalForm>
  );

  const fuCanEdit = (f: Followup) => isAdmin || f.user_id === me?.id;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav("/customers")}>
          返回
        </Button>
        {canWrite && customer.stage !== "won" && customer.stage !== "lost" && (
          <>
            <Button icon={<CheckCircleOutlined />} onClick={() => changeStage("won")} style={{ color: "#389e0d" }}>
              标记成交
            </Button>
            <Button icon={<CloseCircleOutlined />} onClick={() => changeStage("lost")}>
              标记流失
            </Button>
          </>
        )}
        {canWrite && (customer.stage === "won" || customer.stage === "lost") && (
          <Button onClick={() => changeStage("following")}>恢复跟进</Button>
        )}
      </Space>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions
          size="small"
          column={{ xs: 1, sm: 2, md: 4 }}
          items={[
            { key: "company", label: "公司名称", children: <b>{customer.company_name}</b> },
            { key: "contact", label: "联系人", children: customer.contact_name || "-" },
            { key: "phone", label: "电话", children: customer.phone || "-" },
            { key: "wechat", label: "微信", children: customer.wechat || "-" },
            { key: "source", label: "来源", children: SOURCE_MAP[customer.source] || customer.source },
            {
              key: "stage",
              label: "阶段",
              children: <Tag color={STAGE_MAP[customer.stage]?.color}>{STAGE_MAP[customer.stage]?.text}</Tag>,
            },
            { key: "owner", label: "负责人", children: customer.owner_name },
            {
              key: "next",
              label: "下次跟进",
              children: customer.next_followup_at
                ? dayjs(customer.next_followup_at).format("YYYY-MM-DD HH:mm")
                : "无（已结束）",
            },
            { key: "region", label: "地区", children: customer.region || "-" },
            { key: "demand", label: "需求备注", children: customer.demand || "-" },
            {
              key: "last",
              label: "最近联系",
              children: customer.last_contacted_at ? dayjs(customer.last_contacted_at).format("MM-DD HH:mm") : "未联系",
            },
            { key: "created", label: "入库时间", children: dayjs(customer.created_at).format("YYYY-MM-DD") },
          ]}
        />
        {isAdmin && (
          <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
            <Typography.Text type="secondary">转移负责人（客户交接）：</Typography.Text>
            <Select
              size="small"
              style={{ width: 160 }}
              value={customer.owner_id}
              onChange={transfer}
              options={users.map((u) => ({ value: u.id, label: u.name }))}
            />
          </div>
        )}
      </Card>

      <Card
        size="small"
        title={`成交记录（累计 ¥${totalAmount.toLocaleString()}）`}
        style={{ marginBottom: 16 }}
        extra={
          canWrite ? (
            <Space>
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={() => {
                  setFuEdit(undefined);
                  setDealEdit(null);
                }}
              >
                添加成交
              </Button>
              {dealForm}
            </Space>
          ) : null
        }
      >
        {deals.length === 0 ? (
          <Typography.Text type="secondary">暂无成交记录</Typography.Text>
        ) : (
          <Table<Deal>
            rowKey="id"
            size="small"
            pagination={false}
            dataSource={deals}
            columns={[
              { title: "日期", dataIndex: "deal_date", width: 100, render: (v) => v?.slice(0, 10) },
              { title: "产品", dataIndex: "product", ellipsis: true },
              {
                title: "产品线",
                dataIndex: "product_line",
                width: 90,
                render: (v) => <Tag>{PRODUCT_LINE_MAP[v] || v}</Tag>,
              },
              { title: "数量", dataIndex: "quantity", width: 90, render: (_, r) => `${r.quantity} ${r.unit}` },
              {
                title: "金额",
                dataIndex: "amount",
                width: 110,
                render: (v) => <b>¥{(v || 0).toLocaleString()}</b>,
              },
              { title: "开票", dataIndex: "invoice_type", width: 80, render: (v) => v || "-" },
              { title: "收款", dataIndex: "account", width: 110, render: (v) => v || "-" },
              {
                title: "复购",
                dataIndex: "repurchase",
                width: 60,
                render: (v) => (v ? <Tag color="orange">复购</Tag> : "-"),
              },
              ...(canWrite
                ? [
                    {
                      title: "操作",
                      key: "op",
                      width: 100,
                      render: (_: unknown, r: Deal) => (
                        <Space size={8}>
                          <a onClick={() => setDealEdit(r)}>编辑</a>
                          {isAdmin && (
                            <Popconfirm
                              title="删除这条成交记录？"
                              okText="删除"
                              okButtonProps={{ danger: true }}
                              cancelText="取消"
                              onConfirm={() => delDeal(r)}
                            >
                              <a style={{ color: "#cf1322" }}>删除</a>
                            </Popconfirm>
                          )}
                        </Space>
                      ),
                    } as const,
                  ]
                : []),
            ]}
          />
        )}
      </Card>

      <Card
        size="small"
        title="附件（合同 / 交易明细）"
        style={{ marginBottom: 16 }}
        extra={
          canWrite ? (
            <Upload
              showUploadList={false}
              beforeUpload={(f) => {
                uploadAttachment(f);
                return false;
              }}
            >
              <Button type="primary" size="small" icon={<UploadOutlined />}>
                上传附件
              </Button>
            </Upload>
          ) : null
        }
      >
        {attachments.length === 0 ? (
          <Typography.Text type="secondary">
            暂无附件，可上传合同 PDF、交易明细 Excel 等（≤20MB）
          </Typography.Text>
        ) : (
          <Table<Attachment>
            rowKey="id"
            size="small"
            pagination={false}
            dataSource={attachments}
            columns={[
              { title: "文件名", dataIndex: "filename", ellipsis: true },
              { title: "大小", dataIndex: "size", width: 80, render: (v) => fmtSize(v) },
              { title: "上传人", dataIndex: "uploader_name", width: 80 },
              {
                title: "上传时间",
                dataIndex: "created_at",
                width: 130,
                render: (v) => dayjs(v).format("YYYY-MM-DD HH:mm"),
              },
              {
                title: "操作",
                key: "op",
                width: 120,
                render: (_: unknown, r: Attachment) => (
                  <Space size={10}>
                    <a onClick={() => downloadAttachment(r)}>
                      <DownloadOutlined /> 下载
                    </a>
                    {(isAdmin || r.uploader_name === me?.name) && (
                      <Popconfirm
                        title="删除这个附件？"
                        okText="删除"
                        okButtonProps={{ danger: true }}
                        cancelText="取消"
                        onConfirm={() => delAttachment(r)}
                      >
                        <a style={{ color: "#cf1322" }}>删除</a>
                      </Popconfirm>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      <Card
        size="small"
        title="跟进时间线"
        extra={
          canWrite ? (
            <Space>
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={() => {
                  setDealEdit(undefined);
                  setFuEdit(null);
                }}
              >
                添加跟进
              </Button>
              {followupForm}
            </Space>
          ) : null
        }
      >
        {followups.length === 0 ? (
          <Typography.Text type="secondary">暂无跟进记录{canWrite ? "，点右上角添加第一条" : ""}</Typography.Text>
        ) : (
          <Timeline
            items={followups.map((f) => ({
              children: (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Tag color="blue">{METHOD_MAP[f.method] || f.method}</Tag>
                    <Typography.Text strong>{f.user_name}</Typography.Text>
                    <Typography.Text type="secondary">
                      {dayjs(f.created_at).format("YYYY-MM-DD HH:mm")}
                    </Typography.Text>
                    {canWrite && fuCanEdit(f) && (
                      <Space size={8}>
                        <a onClick={() => setFuEdit(f)}>编辑</a>
                        {isAdmin && (
                          <Popconfirm title="删除这条跟进？" okText="删除" okButtonProps={{ danger: true }} cancelText="取消" onConfirm={() => delFollowup(f)}>
                            <a style={{ color: "#cf1322" }}>删除</a>
                          </Popconfirm>
                        )}
                      </Space>
                    )}
                  </div>
                  <div style={{ marginTop: 4 }}>{f.content}</div>
                  {f.next_followup_at && (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      下次跟进：{dayjs(f.next_followup_at).format("MM-DD HH:mm")}
                    </Typography.Text>
                  )}
                </div>
              ),
            }))}
          />
        )}
      </Card>
    </div>
  );
}
