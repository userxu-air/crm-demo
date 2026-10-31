// 系统设置（/settings，仅 admin）：账号管理表格（增删改/重置密码/停用/参与业绩开关）
// 数据源：/api/users；in_sales_report 控制导出名单是否含此人

import { useEffect, useRef, useState } from "react";
import { Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Select, Switch, Tag, Typography, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ActionType, ProColumns } from "@ant-design/pro-components";
import { ModalForm, ProTable } from "@ant-design/pro-components";
import { api, errMsg } from "../api";
import ImportCard from "./ImportCard";
import { getMe, updateMe } from "../auth";

interface UserRow {
  id: number;
  name: string;
  phone: string;
  role: string;
  is_active: boolean;
  monthly_target: number;
  in_sales_report: boolean;
  created_at: string;
}

const ROLE_TEXT: Record<string, { text: string; color: string }> = {
  admin: { text: "管理员", color: "purple" },
  sales: { text: "销售", color: "blue" },
  boss: { text: "老板（只读）", color: "gold" },
};

export default function Settings() {
  const actionRef = useRef<ActionType>(null);
  const [me, setMe] = useState(getMe());
  const [resetUser, setResetUser] = useState<UserRow | null>(null);
  const [editUser, setEditUser] = useState<UserRow | null>(null);
  const [form] = Form.useForm();
  const [pwdForm] = Form.useForm();
  const [nameForm] = Form.useForm();


  useEffect(() => {
    // 自愈旧会话：拉取当前用户最新 id/昵称（登录响应早期版本未存 id）
    api
      .get("/auth/me")
      .then((r) => {
        const u = r.data;
        updateMe({ id: u.id, name: u.name, role: u.role });
        setMe({ id: u.id, name: u.name, role: u.role });
        nameForm.setFieldsValue({ name: u.name });
      })
      .catch(() => {});
  }, []);

  const changeMyName = async (v: { name: string }) => {
    if (!me?.id) {
      message.error("会话异常，请重新登录后再试");
      return;
    }
    try {
      await api.patch(`/users/${me.id}`, { name: v.name });
      updateMe({ name: v.name });
      message.success("账户名已修改");
      window.location.reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const changeMyPwd = async (v: { old_password: string; new_password: string }) => {
    try {
      await api.post("/auth/change-password", v);
      message.success("密码已修改");
      pwdForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const createUser = async (v: Record<string, unknown>) => {
    try {
      await api.post("/users", v);
      message.success("账号已创建，请将初始密码告知本人并提醒首次登录后修改");
      actionRef.current?.reload();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  const toggleSalesReport = async (row: UserRow, v: boolean) => {
    try {
      await api.patch(`/users/${row.id}`, { in_sales_report: v });
      message.success(v ? "已加入业绩汇总名单" : "已移出业绩汇总名单");
      actionRef.current?.reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const toggleActive = async (row: UserRow) => {
    try {
      await api.patch(`/users/${row.id}`, { is_active: !row.is_active });
      message.success(row.is_active ? "已停用" : "已启用");
      actionRef.current?.reload();
      actionRef.current?.reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const resetPwd = async (v: { password: string }) => {
    if (!resetUser) return;
    try {
      await api.patch(`/users/${resetUser.id}`, { password: v.password });
      message.success(`已重置 ${resetUser.name} 的密码`);
      setResetUser(null);
      form.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const updateUser = async (v: Record<string, unknown>) => {
    if (!editUser) return false;
    try {
      await api.patch(`/users/${editUser.id}`, v);
      message.success("账号已更新");
      setEditUser(null);
      actionRef.current?.reload();
      return true;
    } catch (e) {
      message.error(errMsg(e));
      return false;
    }
  };

  const delUser = async (row: UserRow) => {
    try {
      await api.delete(`/users/${row.id}`);
      message.success(`已删除账号「${row.name}」`);
      actionRef.current?.reload();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const columns: ProColumns<UserRow>[] = [
    { title: "姓名", dataIndex: "name", width: 100 },
    { title: "手机号（登录账号）", dataIndex: "phone", width: 150 },
    {
      title: "角色",
      dataIndex: "role",
      width: 110,
      render: (_, r) => <Tag color={ROLE_TEXT[r.role]?.color}>{ROLE_TEXT[r.role]?.text}</Tag>,
    },
    {
      title: "参与业绩汇总",
      dataIndex: "in_sales_report",
      width: 120,
      render: (_, r) => (
        <Switch
          checked={r.in_sales_report}
          checkedChildren="参与"
          unCheckedChildren="不参与"
          onChange={(v) => toggleSalesReport(r, v)}
        />
      ),
    },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 80,
      render: (_, r) => (r.is_active ? <Tag color="green">正常</Tag> : <Tag>已停用</Tag>),
    },
    {
      title: "操作",
      valueType: "option",
      width: 250,
      render: (_, r) => [
        <a key="edit" onClick={() => setEditUser(r)}>
          编辑
        </a>,
        <a key="reset" onClick={() => setResetUser(r)}>
          重置密码
        </a>,
        <a key="toggle" style={{ color: r.is_active ? "#cf1322" : "#389e0d" }} onClick={() => toggleActive(r)}>
          {r.is_active ? "停用" : "启用"}
        </a>,
        <Popconfirm
          key="del"
          title="删除账号"
          description={
            <>
              确定删除「{r.name}」？
              <br />
              名下有客户时需先转移，不能删除自己。
            </>
          }
          okText="删除"
          okButtonProps={{ danger: true }}
          cancelText="取消"
          onConfirm={() => delUser(r)}
        >
          <a style={{ color: "#cf1322" }}>删除</a>
        </Popconfirm>,
      ],
    },
  ];

  return (
    <>
      <ImportCard me={me} />

      <Card size="small" title="修改账号（当前登录账号）" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 64, flexWrap: "wrap" }}>
          <Form form={nameForm} layout="inline" onFinish={changeMyName} initialValues={{ name: me?.name }}>
            <Form.Item name="name" label="账户名" rules={[{ required: true, message: "请输入账户名" }]}>
              <Input placeholder="账户名" maxLength={50} />
            </Form.Item>
            <Form.Item>
              <Button htmlType="submit">保存账户名</Button>
            </Form.Item>
          </Form>
          <Form form={pwdForm} layout="inline" onFinish={changeMyPwd}>
            <Form.Item name="old_password" label="原密码" rules={[{ required: true }]}>
              <Input.Password placeholder="原密码" />
            </Form.Item>
            <Form.Item
              name="new_password"
              label="新密码"
              rules={[{ required: true }, { min: 6, message: "至少 6 位" }]}
            >
              <Input.Password placeholder="新密码（至少 6 位）" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit">
                修改密码
              </Button>
            </Form.Item>
          </Form>
        </div>
      </Card>
      <ProTable<UserRow>
        headerTitle="账号管理"
        actionRef={actionRef}
        rowKey="id"
        search={false}
        options={{ reload: true, density: false, setting: false }}
        toolBarRender={() => [
          <ModalForm
            key="create"
            title="新建账号"
            trigger={
              <Button type="primary">
                <PlusOutlined /> 新建账号
              </Button>
            }
            width={440}
            modalProps={{ destroyOnClose: true }}
            onFinish={createUser}
            initialValues={{ role: "sales", in_sales_report: true }}
          >
            <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
              <Input placeholder="如：张三" />
            </Form.Item>
            <Form.Item name="phone" label="手机号（登录账号）" rules={[{ required: true }]}>
              <Input maxLength={20} />
            </Form.Item>
            <Form.Item
              name="password"
              label="初始密码"
              rules={[{ required: true }, { min: 6, message: "至少 6 位" }]}
            >
              <Input.Password placeholder="至少 6 位" />
            </Form.Item>
            <Form.Item name="role" label="角色" rules={[{ required: true }]}>
              <Select
                options={Object.entries(ROLE_TEXT).map(([k, v]) => ({ value: k, label: v.text }))}
              />
            </Form.Item>
            <Form.Item name="monthly_target" label="月度业绩目标（元）" extra="用于导出业绩汇总的达成占比列">
              <InputNumber min={0} style={{ width: "100%" }} placeholder="如 175000，不填为 0" />
            </Form.Item>
          </ModalForm>,
        ]}
        request={async () => {
          const { data } = await api.get("/users");
          return { data, success: true };
        }}
        columns={columns}
        pagination={false}
      />
      <Typography.Text type="secondary" style={{ display: "block", marginTop: 8 }}>
        提示：销售离职时先「停用」账号，再在客户详情页将其客户转移给其他销售。
      </Typography.Text>
      <ModalForm
        key={editUser?.id || "edit-none"}
        title={`编辑账号：${editUser?.name || ""}`}
        open={!!editUser}
        onOpenChange={(o) => !o && setEditUser(null)}
        width={440}
        modalProps={{ destroyOnClose: true }}
        onFinish={updateUser}
        initialValues={editUser || undefined}
      >
        <Form.Item name="name" label="姓名" rules={[{ required: true, message: "请输入姓名" }]}>
          <Input placeholder="如：张三" maxLength={50} />
        </Form.Item>
        <Form.Item
          name="phone"
          label="手机号（登录账号）"
          rules={[{ required: true, message: "请输入手机号" }]}
        >
          <Input maxLength={20} placeholder="登录用手机号" />
        </Form.Item>
        <Form.Item name="role" label="角色" rules={[{ required: true }]}>
          <Select
            options={Object.entries(ROLE_TEXT).map(([k, v]) => ({ value: k, label: v.text }))}
          />
        </Form.Item>
        <Form.Item name="monthly_target" label="月度业绩目标（元）" extra="用于导出业绩汇总的达成占比列">
          <InputNumber min={0} style={{ width: "100%" }} placeholder="如 175000，不填为 0" />
        </Form.Item>
        <Form.Item name="in_sales_report" label="参与业绩汇总" valuePropName="checked" extra="关掉后不出现在业绩汇总/数据分类名单">
          <Switch checkedChildren="参与" unCheckedChildren="不参与" />
        </Form.Item>
      </ModalForm>
      <Modal
        title={`重置密码：${resetUser?.name || ""}`}
        open={!!resetUser}
        onCancel={() => setResetUser(null)}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={resetPwd}>
          <Form.Item
            name="password"
            label="新密码"
            rules={[{ required: true }, { min: 6, message: "至少 6 位" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
