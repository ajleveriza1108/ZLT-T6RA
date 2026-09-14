import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Antenna,
  Database,
  Download,
  FileJson,
  Gauge,
  Globe2,
  History,
  Network,
  Play,
  Radio,
  RefreshCw,
  Save,
  Settings as SettingsIcon,
  Signal,
  TerminalSquare,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api } from "./api";
import { BoolPill, NAV_ITEMS, Panel, SafetyStrip, StatCard, statIcons } from "./components";
import type {
  DeviceSummary,
  FirmwareStatus,
  InternetResult,
  Mode,
  NetworkResult,
  TelemetrySample,
} from "./types";

type Page = (typeof NAV_ITEMS)[number][0];

function fmt(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function Dashboard({ data }: { data: DeviceSummary | null }) {
  const csqPercent =
    data?.csq == null ? 0 : Math.max(0, Math.min(100, (data.csq / 31) * 100));

  return (
    <>
      <div className="summary-grid">
        <StatCard label="Operator" value={fmt(data?.operator)} icon={statIcons.operator} />
        <StatCard label="RAT" value={fmt(data?.rat)} icon={statIcons.rat} />
        <StatCard label="CFUN" value={fmt(data?.cfun)} icon={statIcons.cfun} />
        <StatCard label="SIM" value={fmt(data?.sim_status)} icon={statIcons.sim} />
        <StatCard label="APN" value={fmt(data?.apn)} icon={statIcons.apn} />
        <StatCard label="IPv4 / PDP" value={fmt(data?.ipv4)} icon={statIcons.ipv4} />
      </div>

      <div className="dashboard-grid">
        <Panel title="Registration" eyebrow="Cellular state" icon={<Antenna size={22} />}>
          <div className="status-list">
            <div><span>SIM ready</span><BoolPill value={data?.sim_status === "READY"} /></div>
            <div><span>Network registered</span><BoolPill value={Boolean(data?.registered)} /></div>
            <div><span>Packet attached</span><BoolPill value={Boolean(data?.packet_attached)} /></div>
            <div><span>Any PDP active</span><BoolPill value={Boolean(data?.pdp_active)} /></div>
            <div><span>PCUI port</span><strong>{fmt(data?.port)}</strong></div>
          </div>
        </Panel>

        <Panel title="Signal" eyebrow="Radio" icon={<Signal size={22} />}>
          <div className="signal-hero">
            <div>
              <span>CSQ</span>
              <strong>{data?.csq ?? "—"}{data?.csq == null ? "" : " / 31"}</strong>
            </div>
            <div className="signal-meter">
              <span style={{ width: `${csqPercent}%` }} />
            </div>
          </div>
          <div className="status-list compact">
            <div><span>HCSQ RAT</span><strong>{fmt(data?.hcsq?.rat)}</strong></div>
            <div><span>Vendor values</span><strong>{data?.hcsq?.raw_values?.join(", ") || "—"}</strong></div>
          </div>
          <p className="hint">Balong vendor values remain raw until exact conversion semantics are verified.</p>
        </Panel>

        <Panel title="APN / PDP Contexts" eyebrow="Packet data" icon={<Network size={22} />} wide>
          <PdpTable data={data} />
        </Panel>
      </div>
    </>
  );
}

function PdpTable({ data }: { data: DeviceSummary | null }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>CID</th>
            <th>APN</th>
            <th>PDP type</th>
            <th>Status</th>
            <th>Assigned address</th>
          </tr>
        </thead>
        <tbody>
          {(data?.contexts ?? []).map((row) => (
            <tr key={row.cid}>
              <td>{row.cid}</td>
              <td className="mono">{row.apn || "—"}</td>
              <td>{row.pdp_type || "—"}</td>
              <td><BoolPill value={row.active} yes="Active" no="Inactive" /></td>
              <td className="mono">
                {row.addresses.length ? row.addresses.join(" · ") : row.pdp_address || "—"}
              </td>
            </tr>
          ))}
          {!data?.contexts?.length && (
            <tr><td colSpan={5} className="empty-row">No PDP contexts returned.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SimInfo({ data }: { data: DeviceSummary | null }) {
  return (
    <div className="page-grid two">
      <Panel title="SIM State" eyebrow="Subscriber" icon={<Database size={22} />}>
        <div className="detail-grid">
          <div><span>Status</span><strong>{fmt(data?.sim_status)}</strong></div>
          <div><span>CFUN</span><strong>{fmt(data?.cfun)}</strong></div>
          <div><span>Registered</span><BoolPill value={Boolean(data?.registered)} /></div>
          <div><span>Packet attached</span><BoolPill value={Boolean(data?.packet_attached)} /></div>
        </div>
      </Panel>

      <Panel title="Operator" eyebrow="Serving network" icon={<Antenna size={22} />}>
        <div className="detail-grid">
          <div><span>Name</span><strong>{fmt(data?.operator)}</strong></div>
          <div><span>RAT</span><strong>{fmt(data?.rat)}</strong></div>
          <div><span>PCUI</span><strong>{fmt(data?.port)}</strong></div>
          <div><span>Mode</span><strong>{fmt(data?.mode).toUpperCase()}</strong></div>
        </div>
      </Panel>

      <Panel title="Privacy" eyebrow="Repository policy" icon={<FileJson size={22} />} wide>
        <div className="notice-box">
          IMSI, ICCID, IMEI, serials and credentials are intentionally not displayed or committed by the project MVP.
          Raw capture files remain in the ignored <code>captures/</code> workspace.
        </div>
      </Panel>
    </div>
  );
}

function SignalMonitor({ data }: { data: DeviceSummary | null }) {
  const values = data?.hcsq?.raw_values ?? [];
  return (
    <div className="page-grid two">
      <Panel title="Primary Signal" eyebrow="Live radio" icon={<Signal size={22} />}>
        <div className="signal-big">
          <span>CSQ</span>
          <strong>{data?.csq ?? "—"}</strong>
          <small>/31</small>
        </div>
        <div className="signal-meter tall">
          <span style={{ width: `${data?.csq == null ? 0 : (data.csq / 31) * 100}%` }} />
        </div>
      </Panel>
      <Panel title="Vendor HCSQ" eyebrow="Balong raw data" icon={<Radio size={22} />}>
        <div className="chip-row">
          {values.length
            ? values.map((v, i) => <span className="metric-chip" key={i}>V{i + 1}: {v}</span>)
            : <span className="muted">No HCSQ values.</span>}
        </div>
        <pre className="code-block">{data?.hcsq?.raw || "—"}</pre>
      </Panel>
      <Panel title="SYSINFOEX" eyebrow="Modem state" icon={<Activity size={22} />} wide>
        <pre className="code-block">{data?.sysinfoex || "—"}</pre>
      </Panel>
    </div>
  );
}

function NetworkScan({
  mode,
}: {
  mode: Mode;
}) {
  const [results, setResults] = useState<NetworkResult[]>([]);
  const [note, setNote] = useState("Not scanned yet.");
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const payload = await api.scanNetworks(mode === "real");
      setResults(payload.results);
      setNote(payload.note);
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <Panel title="Available Networks" eyebrow="Manual scan" icon={<Antenna size={22} />}>
        <div className="toolbar-line">
          <button className="primary-button" onClick={run} disabled={busy}>
            <Play size={16} />
            {busy ? "Scanning…" : "Start Scan"}
          </button>
          <span className="hint inline">
            {mode === "real"
              ? "Real scan is manual because AT+COPS=? can take time and temporarily occupy the radio."
              : "Mock mode returns a deterministic lab dataset."}
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Operator</th><th>PLMN</th><th>RAT</th><th>Status</th></tr>
            </thead>
            <tbody>
              {results.map((row, i) => (
                <tr key={`${row.numeric}-${i}`}>
                  <td>{row.operator}</td>
                  <td className="mono">{row.numeric}</td>
                  <td>{row.rat}</td>
                  <td>{row.status}</td>
                </tr>
              ))}
              {!results.length && (
                <tr><td className="empty-row" colSpan={4}>No scan results.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="hint">{note}</p>
      </Panel>
    </div>
  );
}

function PdpPage({ data }: { data: DeviceSummary | null }) {
  return (
    <div className="page-grid">
      <Panel title="APN / PDP Contexts" eyebrow="Read-only" icon={<Network size={22} />}>
        <PdpTable data={data} />
      </Panel>
      <Panel title="Current Packet State" eyebrow="Summary" icon={<Globe2 size={22} />}>
        <div className="detail-grid four">
          <div><span>APN</span><strong>{fmt(data?.apn)}</strong></div>
          <div><span>IPv4</span><strong>{fmt(data?.ipv4)}</strong></div>
          <div><span>Attached</span><BoolPill value={Boolean(data?.packet_attached)} /></div>
          <div><span>PDP active</span><BoolPill value={Boolean(data?.pdp_active)} /></div>
        </div>
      </Panel>
    </div>
  );
}

function InternetTestPage() {
  const [result, setResult] = useState<InternetResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true);
    setErr("");
    try {
      setResult(await api.internetTest());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid">
      <Panel title="Internet Diagnostics" eyebrow="Host-side validation" icon={<Gauge size={22} />}>
        <button className="primary-button" onClick={run} disabled={busy}>
          <Play size={16} /> {busy ? "Testing…" : "Run Internet Test"}
        </button>
        {err && <div className="error-box">{err}</div>}
        <div className="result-cards">
          <div><span>DNS</span><strong>{result ? (result.dns_ok ? "PASS" : "FAIL") : "—"}</strong></div>
          <div><span>Ping</span><strong>{result?.ping_ms != null ? `${result.ping_ms} ms` : "—"}</strong></div>
          <div><span>Loss</span><strong>{result?.packet_loss_pct != null ? `${result.packet_loss_pct}%` : "—"}</strong></div>
          <div><span>Download</span><strong>{result?.download_mbps != null ? `${result.download_mbps} Mbps` : "—"}</strong></div>
          <div><span>Upload</span><strong>{result?.upload_mbps != null ? `${result.upload_mbps} Mbps` : "—"}</strong></div>
        </div>
        <p className="hint">{result?.note ?? "This currently validates the PC's route through DNS and ping. Throughput is reserved for a later dedicated test engine."}</p>
      </Panel>
    </div>
  );
}

function LoggerPage() {
  const [samples, setSamples] = useState<TelemetrySample[]>([]);
  const [busy, setBusy] = useState(false);

  async function reload() {
    const r = await api.telemetry(120);
    setSamples(r.samples);
  }

  async function capture() {
    setBusy(true);
    try {
      await api.captureTelemetry();
      await reload();
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    reload().catch(() => undefined);
  }, []);

  const recent = samples.slice(-30);
  const max = 31;

  return (
    <div className="page-grid">
      <Panel title="Cell / Signal Logger" eyebrow="Local development data" icon={<History size={22} />}>
        <div className="toolbar-line">
          <button className="primary-button" onClick={capture} disabled={busy}>
            <Save size={16} /> {busy ? "Capturing…" : "Capture Sample"}
          </button>
          <button className="secondary-button" onClick={() => reload()}>
            <RefreshCw size={16} /> Refresh
          </button>
          <span className="hint inline">{samples.length} samples loaded</span>
        </div>

        <div className="sparkline">
          {recent.map((s, i) => {
            const height = s.csq == null ? 3 : Math.max(3, (s.csq / max) * 100);
            return <span key={`${s.timestamp}-${i}`} style={{ height: `${height}%` }} title={`${s.timestamp}: CSQ ${s.csq ?? "—"}`} />;
          })}
          {!recent.length && <div className="empty-chart">No telemetry yet.</div>}
        </div>

        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>Operator</th><th>RAT</th><th>CSQ</th><th>Reg</th><th>PDP</th><th>APN</th></tr></thead>
            <tbody>
              {samples.slice().reverse().slice(0, 25).map((s) => (
                <tr key={s.timestamp}>
                  <td className="mono">{new Date(s.timestamp).toLocaleString()}</td>
                  <td>{s.operator}</td>
                  <td>{s.rat}</td>
                  <td>{s.csq ?? "—"}</td>
                  <td><BoolPill value={s.registered} /></td>
                  <td><BoolPill value={s.pdp_active} /></td>
                  <td className="mono">{s.apn ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function DiagnosticsPage({ data }: { data: DeviceSummary | null }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const rows = Object.entries(data?.raw ?? {});

  return (
    <div className="page-grid">
      <Panel title="Raw Modem Diagnostics" eyebrow="Query snapshot" icon={<FileJson size={22} />}>
        <div className="raw-list">
          {rows.map(([name, value]) => (
            <div className="raw-item" key={name}>
              <button onClick={() => setOpen((prev) => ({ ...prev, [name]: !prev[name] }))}>
                <span>{name}</span>
                <span>{open[name] ? "Hide" : "View"}</span>
              </button>
              {open[name] && <pre>{value}</pre>}
            </div>
          ))}
          {!rows.length && <div className="empty-row">No raw data.</div>}
        </div>
      </Panel>
    </div>
  );
}

function AtConsole() {
  const [commands, setCommands] = useState<Record<string, string>>({});
  const [key, setKey] = useState("");
  const [response, setResponse] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.atCommands().then((r) => {
      setCommands(r.commands);
      const first = Object.keys(r.commands)[0];
      if (first) setKey(first);
    }).catch(() => undefined);
  }, []);

  async function run() {
    if (!key) return;
    setBusy(true);
    try {
      const r = await api.queryAt(key);
      setResponse(`${r.command}\n\n${r.response}`);
    } catch (e) {
      setResponse(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-grid two">
      <Panel title="Safe AT Console" eyebrow="Whitelist only" icon={<TerminalSquare size={22} />}>
        <label className="field-label">Query command</label>
        <select value={key} onChange={(e) => setKey(e.target.value)}>
          {Object.entries(commands).map(([k, cmd]) => (
            <option value={k} key={k}>{k} — {cmd}</option>
          ))}
        </select>
        <button className="primary-button top-gap" onClick={run} disabled={busy || !key}>
          <Play size={16} /> {busy ? "Running…" : "Run Query"}
        </button>
        <p className="hint">
          Arbitrary AT input is intentionally unavailable in this stage. The backend rejects non-whitelisted commands.
        </p>
      </Panel>
      <Panel title="Response" eyebrow="Raw serial output" icon={<Radio size={22} />}>
        <pre className="terminal">{response || "Run a query to view the response."}</pre>
      </Panel>
    </div>
  );
}

function FirmwarePage() {
  const [status, setStatus] = useState<FirmwareStatus | null>(null);

  useEffect(() => {
    api.firmwareStatus().then(setStatus).catch(() => undefined);
  }, []);

  return (
    <div className="page-grid">
      <Panel title="Firmware Development Gates" eyebrow="Offline track" icon={<Download size={22} />}>
        <div className="firmware-banner">
          <strong>Flashing is {status?.flashing_enabled ? "ENABLED" : "DISABLED"}</strong>
          <span>{status?.current_track ?? "Loading…"}</span>
        </div>
        <div className="gate-list">
          {(status?.gates ?? []).map((g) => (
            <div className={`gate ${g.status}`} key={g.id}>
              <div className="gate-state">{g.status.toUpperCase()}</div>
              <div><strong>{g.title}</strong><p>{g.detail}</p></div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function SettingsPage({
  mode,
  onMode,
  port,
}: {
  mode: Mode;
  onMode: (mode: Mode) => void;
  port: string;
}) {
  return (
    <div className="page-grid two">
      <Panel title="Runtime Mode" eyebrow="Application" icon={<SettingsIcon size={22} />}>
        <div className="settings-row">
          <button className={mode === "mock" ? "choice active" : "choice"} onClick={() => onMode("mock")}>
            MOCK
          </button>
          <button className={mode === "real" ? "choice active" : "choice"} onClick={() => onMode("real")}>
            REAL
          </button>
        </div>
        <p className="hint">Real mode reads the physical modem. Mock mode is for UI development.</p>
      </Panel>

      <Panel title="Serial Interface" eyebrow="PCUI" icon={<Radio size={22} />}>
        <div className="detail-grid">
          <div><span>Detected port</span><strong>{port || "—"}</strong></div>
          <div><span>Baud</span><strong>115200</strong></div>
          <div><span>DTR</span><strong>ON</strong></div>
          <div><span>RTS</span><strong>OFF</strong></div>
        </div>
      </Panel>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [data, setData] = useState<DeviceSummary | null>(null);
  const [mode, setMode] = useState<Mode>("mock");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [updated, setUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.summary();
      setData(payload);
      setMode(payload.mode);
      setUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const changeMode = useCallback(async (next: Mode) => {
    setLoading(true);
    setError("");
    try {
      await api.setMode(next);
      setMode(next);
      window.setTimeout(() => refresh(), 150);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (mode !== "real") return;
    const timer = window.setInterval(refresh, 15000);
    return () => window.clearInterval(timer);
  }, [mode, refresh]);

  const navTitle = useMemo(
    () => NAV_ITEMS.find(([key]) => key === page)?.[1] ?? "Dashboard",
    [page],
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Radio size={22} /></div>
          <div>
            <div className="brand-title">T6R-A Network Lab</div>
            <div className="brand-subtitle">Research & Testing</div>
          </div>
        </div>

        <nav>
          {NAV_ITEMS.map(([key, label, Icon]) => (
            <button
              className={`nav-item ${page === key ? "active" : ""}`}
              key={key}
              onClick={() => setPage(key)}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="device-card">
          <div className="device-row"><Wifi size={18} /><strong>ZLT T6R-A</strong></div>
          <div className="connected-dot-row">
            <span className={`dot ${error ? "red" : ""}`} />
            {error ? "Backend error" : (data?.connected ? "Connected" : "Disconnected")}
          </div>
          <div className="small muted">{data?.port ?? "COM port unknown"} · {mode.toUpperCase()}</div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <div className="title-row">
              <h1>{navTitle}</h1>
              <span className={`mode-pill ${mode}`}>{mode.toUpperCase()}</span>
            </div>
            <p>
              Network Lab v0.4
              {updated ? ` · updated ${updated.toLocaleTimeString()}` : ""}
            </p>
          </div>

          <div className="header-actions">
            <div className="mode-switch">
              <button className={mode === "mock" ? "selected" : ""} onClick={() => changeMode("mock")} disabled={loading}>Mock</button>
              <button className={mode === "real" ? "selected" : ""} onClick={() => changeMode("real")} disabled={loading}>Real COM12</button>
            </div>
            <button className="refresh-button" onClick={refresh} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} />
              {loading ? "Reading…" : "Refresh"}
            </button>
          </div>
        </header>

        <SafetyStrip />

        {error && (
          <div className="error-banner">
            <WifiOff size={17} />
            <div><strong>Backend / modem read failed.</strong><div>{error}</div></div>
          </div>
        )}

        {page === "dashboard" && <Dashboard data={data} />}
        {page === "sim" && <SimInfo data={data} />}
        {page === "signal" && <SignalMonitor data={data} />}
        {page === "scan" && <NetworkScan mode={mode} />}
        {page === "pdp" && <PdpPage data={data} />}
        {page === "internet" && <InternetTestPage />}
        {page === "logger" && <LoggerPage />}
        {page === "diagnostics" && <DiagnosticsPage data={data} />}
        {page === "at" && <AtConsole />}
        {page === "firmware" && <FirmwarePage />}
        {page === "settings" && <SettingsPage mode={mode} onMode={changeMode} port={data?.port ?? ""} />}
      </main>
    </div>
  );
}
