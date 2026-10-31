import axios from "axios";

export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem("token");
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("me");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export const errMsg = (e: unknown): string => {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail || err?.message || "请求失败";
};

export const SOURCE_MAP: Record<string, string> = {
  sales_init: "销售自拓",
  referral: "转介绍",
  aigopo: "爱采购",
  website: "官网",
  wecom: "企微",
  tel: "电话",
  other: "其他",
};

export const STAGE_MAP: Record<string, { text: string; color: string }> = {
  new: { text: "新线索", color: "blue" },
  following: { text: "跟进中", color: "processing" },
  won: { text: "成交", color: "success" },
  lost: { text: "流失", color: "default" },
};

export const METHOD_MAP: Record<string, string> = {
  tel: "电话",
  wechat: "微信",
  visit: "上门",
  email: "邮件",
};

export const PRODUCT_LINE_MAP: Record<string, string> = {
  right_angle: "直角",
  big_right_angle: "大直角",
  flat: "平面",
  high_speed_flat: "高速平面",
  round_bottle: "圆瓶",
  vision: "视觉",
  box_folding: "折盒机",
  roller: "滚贴",
  precision: "高精度吸贴",
  consumable: "标签耗材",
  other: "其他",
};

export const INVOICE_MAP: Record<string, string> = {
  "13%专票": "13%专票",
  专票: "专票",
  普票: "普票",
  开票: "开票",
  不开票: "不开票",
  无票: "无票",
};

export const ACCOUNT_MAP: Record<string, string> = {
  "公账（示例）": "公账（示例）",
  "公账（）": "公账（）",
  "广东钰锋账户转账": "广东钰锋账户转账",
  聚合码: "聚合码",
  "微信转账": "微信转账",
  "私账": "私账",
  其他: "其他",
};
