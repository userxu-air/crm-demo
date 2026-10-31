// 登录页（/login）：glitch 字符雨 + Perlin 粒子 + 光波特效背景（effects.ts）
// 登录成功写 localStorage（token+me）后跳 /

import { useEffect, useRef, useState } from "react";
import { Button, Form, Input, message } from "antd";
import { useNavigate } from "react-router-dom";
import { api, errMsg } from "../api";
import { setAuth } from "../auth";
import { initGlitchBg, initSwarmCursor, initParticleText, LIGHT_PALETTE } from "./effects";
import "./login.css";

export default function Login() {
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();
  const glitchRef = useRef<HTMLCanvasElement>(null);
  const swarmRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const p = LIGHT_PALETTE;
    const clean1 = glitchRef.current ? initGlitchBg(glitchRef.current, p) : undefined;
    const clean2 = swarmRef.current ? initSwarmCursor(swarmRef.current, p) : undefined;
    // 粒子文字：深青色系与 light 版一致（浅底上深色粒子清晰）
    const clean3 = textRef.current
      ? initParticleText(textRef.current, {
          text: "YZ CRM",
          color: "#0369a1",
          highlightColor: "#0ea5e9",
        })
      : undefined;
    return () => {
      clean1?.();
      clean2?.();
      clean3?.();
    };
  }, []);

  const onFinish = async (v: { phone: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", v);
      setAuth(data.access_token, { id: data.id, name: data.name, role: data.role });
      message.success(`欢迎，${data.name}`);
      nav("/");
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <canvas ref={glitchRef} className="fx-canvas" />
      <canvas ref={swarmRef} className="fx-canvas fx-swarm" />

      <div className="login-center">
        <canvas ref={textRef} className="particle-text" />

        <Form className="login-form" layout="vertical" onFinish={onFinish}>
          <Form.Item name="phone" rules={[{ required: true, message: "请输入手机号" }]}>
            <Input size="large" placeholder="手机号" maxLength={20} />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password size="large" placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block loading={loading}>
            登 录
          </Button>
          <div className="login-hint">密码由管理员 · AI 部门设置</div>
        </Form>
      </div>
    </div>
  );
}
