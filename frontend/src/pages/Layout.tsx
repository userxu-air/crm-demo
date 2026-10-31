// 全局布局：侧边菜单（按角色显隐）+ 顶栏（角色 Tag/改密码/退出）
// 改密码弹窗走 PATCH /api/users/me/password

import { Button, Form, Input, Modal, Tag, message } from "antd";
import { KeyOutlined, LogoutOutlined } from "@ant-design/icons";
import { AppstoreOutlined, SettingOutlined, TeamOutlined } from "@ant-design/icons";
import { ProLayout } from "@ant-design/pro-components";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, errMsg } from "../api";
import { clearAuth, getMe } from "../auth";

const ROLE_TEXT: Record<string, string> = {
  admin: "管理员",
  sales: "销售",
  boss: "老板（只读）",
};

export default function Layout() {
  const me = getMe();
  const nav = useNavigate();
  const loc = useLocation();
  const [pwdOpen, setPwdOpen] = useState(false);
  const [pwdForm] = Form.useForm();

  const logout = () => {
    clearAuth();
    nav("/login");
  };

  const changePwd = async (v: { old_password: string; new_password: string }) => {
    try {
      await api.post("/auth/change-password", v);
      message.success("密码已修改");
      setPwdOpen(false);
      pwdForm.resetFields();
    } catch (e) {
      message.error(errMsg(e));
    }
  };

  const menu = [
    { path: "/", name: "工作台", icon: <AppstoreOutlined /> },
    ...(me?.role !== "sales" ? [{ path: "/customers", name: me?.role === "admin" ? "客户总览" : "客户总览（只读）", icon: <TeamOutlined /> }] : []),
    ...(me?.role === "admin" ? [{ path: "/settings", name: "系统设置", icon: <SettingOutlined /> }] : []),
  ];

  return (
    <ProLayout
      title={`示例 CRM · ${me?.name || ""}`}
      layout="mix"
      location={{ pathname: loc.pathname }}
      route={{ path: "/", routes: menu }}
      menuItemRender={(item, dom) => (
        <div onClick={() => item.path && nav(item.path)}>{dom}</div>
      )}
      actionsRender={() => [
        <Tag key="role" color={me?.role === "admin" ? "purple" : me?.role === "boss" ? "gold" : "blue"}>
          {ROLE_TEXT[me?.role || ""]}
        </Tag>,
        <Button key="pwd" type="text" icon={<KeyOutlined />} onClick={() => setPwdOpen(true)}>
          改密码
        </Button>,
        <Button key="logout" type="text" danger icon={<LogoutOutlined />} onClick={logout}>
          退出
        </Button>,
      ]}
      token={{ header: { colorBgHeader: "#fff" } }}
    >
      <Outlet />
      <Modal
        title="修改密码"
        open={pwdOpen}
        onCancel={() => setPwdOpen(false)}
        onOk={() => pwdForm.submit()}
        destroyOnClose
      >
        <Form form={pwdForm} layout="vertical" onFinish={changePwd}>
          <Form.Item name="old_password" label="原密码" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[{ required: true }, { min: 6, message: "至少 6 位" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </ProLayout>
  );
}
