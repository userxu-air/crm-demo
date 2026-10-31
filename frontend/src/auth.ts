export interface Me {
  id?: number;
  name: string;
  role: "admin" | "sales" | "boss";
}

export const getToken = () => localStorage.getItem("token");

export const getMe = (): Me | null => {
  const s = localStorage.getItem("me");
  if (!s) return null;
  try {
    return JSON.parse(s) as Me;
  } catch {
    return null;
  }
};

export const setAuth = (token: string, me: Me) => {
  localStorage.setItem("token", token);
  localStorage.setItem("me", JSON.stringify(me));
};

export const updateMe = (patch: Partial<Me>) => {
  const me = getMe();
  if (!me) return;
  localStorage.setItem("me", JSON.stringify({ ...me, ...patch }));
};

export const clearAuth = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("me");
};
