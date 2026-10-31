// 历史数据一键导入卡片（工作台/系统设置共用）
// - sales：数据强制归属本人（后端强制，界面仅提示）
// - admin：可选「按文件销售手机列归属」或「指定账号」
import { useRef, useState } from "react";
import { Alert, Button, Card, Popconfirm, Select, Space, Typography, Upload, message } from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api, errMsg } from "../api";

interface Me {
  id?: number;
  name?: string;
  role?: string;
}

interface ImportResult {
  total_rows: number;
  customers_created: number;
  customers_matched: number;
  deals_created: number;
  skipped: number;
  warnings: string[];
  errors: string[];
}

const KIND_OPTIONS = [
  { value: "deals-flow", label: "成交流水（销售明细表汇总）" },
  { value: "opportunities", label: "商机表（大设备信息表）" },
];

export default function ImportCard({ me }: { me: Me | null }) {
  const [kind, setKind] = useState("deals-flow");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [ownerMode, setOwnerMode] = useState<"column" | "self">("column");
  const [ownerId, setOwnerId] = useState<number | null>(null);
  const usersRef = useRef<{ id: number; name: string; is_active: boolean }[]>([]);
  const [usersLoaded, setUsersLoaded] = useState(false);

  const isAdmin = me?.role === "admin";

  const loadUsers = async () => {
    if (usersLoaded) return;
    try {
      const r = await api.get("/users");
      usersRef.current = r.data.filter((u: any) => u.is_active);
      setUsersLoaded(true);
    } catch {
      /* ignore */
    }
  };

  const run = async (dry: boolean) => {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      let url = `/import/${kind}?dry_run=${dry}`;
      if (isAdmin && ownerMode === "self" && ownerId) url += `&owner_id=${ownerId}`;
      const res = await api.post(url, form);
      if (dry) {
        setResult(res.data);
        message.success("预检完成，请核对结果后确认导入");
      } else {
        message.success(`导入完成：新建客户 ${res.data.customers_created}，成交记录 ${res.data.deals_created}`, 6);
        setResult(null);
        setFile(null);
      }
    } catch (e) {
      message.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const downloadTpl = async () => {
    const res = await api.get(`/import/template/${kind}`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = kind === "deals-flow" ? "销售明细表汇总.xlsx" : "大设备商机.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card size="small" title="历史数据一键导入" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: "100%" }} size={8}>
        <Space size={12} wrap>
          <Select value={kind} onChange={setKind} style={{ width: 220 }} options={KIND_OPTIONS} />
          <Upload
            accept=".xlsx"
            maxCount={1}
            fileList={file ? [{ uid: "import", name: file.name, status: "done" as const }] : []}
            beforeUpload={(f) => {
              setFile(f);
              setResult(null);
              return false;
            }}
            onRemove={() => setFile(null)}
          >
            <Button icon={<UploadOutlined />}>选择 Excel 文件</Button>
          </Upload>
          {isAdmin && (
            <>
              <Select
                value={ownerMode}
                onChange={(v) => {
                  setOwnerMode(v);
                  if (v === "self") loadUsers();
                }}
                style={{ width: 200 }}
                options={[
                  { value: "column", label: "归属：按文件「销售手机」列" },
                  { value: "self", label: "归属：指定账号" },
                ]}
              />
              {ownerMode === "self" && (
                <Select
                  placeholder="选择归属账号"
                  style={{ width: 160 }}
                  showSearch
                  optionFilterProp="label"
                  onDropdownVisibleChange={loadUsers}
                  options={usersRef.current.map((u) => ({ value: u.id, label: u.name }))}
                  value={ownerId}
                  onChange={setOwnerId}
                />
              )}
            </>
          )}
          <Button onClick={() => run(true)} loading={busy} disabled={!file}>
            ① 预检
          </Button>
          <Popconfirm title="确认正式导入？数据将写入系统" onConfirm={() => run(false)} disabled={!result}>
            <Button type="primary" loading={busy} disabled={!result}>
              ② 确认导入
            </Button>
          </Popconfirm>
          <Button icon={<DownloadOutlined />} onClick={downloadTpl}>
            下载模板
          </Button>
        </Space>
        {result && (
          <Alert
            type="info"
            showIcon
            message={`预检结果：共 ${result.total_rows} 行 ｜ 新建客户 ${result.customers_created} ｜ 匹配已有客户 ${result.customers_matched} ｜ 成交记录 ${result.deals_created} ｜ 跳过 ${result.skipped}`}
            description={
              (result.warnings.length > 0 || result.errors.length > 0) && (
                <div style={{ maxHeight: 160, overflow: "auto", fontSize: 12 }}>
                  {result.warnings.map((w, i) => (
                    <div key={"w" + i}>⚠️ {w}</div>
                  ))}
                  {result.errors.map((e, i) => (
                    <div key={"e" + i} style={{ color: "#cf1322" }}>
                      ✖ {e}
                    </div>
                  ))}
                </div>
              )
            }
          />
        )}
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {isAdmin
            ? "说明：默认按文件「销售手机」列归属对应销售账号（匹配不到归管理员并提示）；也可指定全部归属某个账号。客户按名称查重；无电话客户电话显示'-'，拿到真实电话后编辑补上。"
            : "说明：导入的数据将全部归属你自己的账号（当前登录人）。客户按名称查重；无电话客户电话显示'-'，拿到真实电话后编辑补上。"}
        </Typography.Text>
      </Space>
    </Card>
  );
}
