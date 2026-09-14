import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Antenna,
  CircleDot,
  Cpu,
  Database,
  FileJson,
  Gauge,
  Globe2,
  Network,
  Radio,
  RefreshCw,
  Router,
  Settings,
  ShieldCheck,
  Signal,
  TerminalSquare,
  Wifi,
  WifiOff,
} from "lucide-react";

type ContextRow = {
  cid: number;
  pdp_type: string;
  apn: string;
  pdp_address: string;
  active: boolean;
  addresses: string[];
};

type Summary = {
  device: string;
  connected: boolean;
  mode: "mock" | "real";
  port: string;
  operator: string;
  rat: string;
  cfun: number | null;
  sim_status: string;
  registered: boolean;
  packet_attached: boolean;
  csq: number | null;
  hcsq: {
    rat: string | null;
    raw_values: Array<number | string>;
    raw: string;
  };
  sysinfoex: string;
  contexts: ContextRow[];
  apn: string | null;
  ipv4: string | null;
  pdp_active: boolean;
  raw: Record<string, string>;
};

const apiBase = "http://127.0.0.1:8765";

const nav = [
  ["Dashboard", Activity],
  ["SIM Info", Database],
  ["Signal Monitor", Signal],
  ["Network Scan", Antenna],
  ["APN / PDP", Network],
  ["Internet Test", Gauge],
  ["Diagnostics", Router],
  ["AT Console", TerminalSquare],
  ["Firmware", Cpu],
  ["Settings", Settings],
] as const;

function BoolPill({ value, yes = "Yes", no = "No" }: { value: boolean; yes?: string; no?: string }) {
  return (
    <span className={`bool-pill ${value ? "good" : "bad"}`}>
      <CircleDot size={12} />
      {value ? yes : no}
    </span>
  );
}

function ValueCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Activity;
}) {
  return (
    <div className="value-card">
      <div className="value-icon"><Icon size={18} /></div>
      <div className="value-copy">
        <div className="muted">{label}</div>
        <strong title={value}>{value}</strong>
      </div>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<Summary | null>(null);
  const [mode, setModeState] = useState<"mock" | "real">("mock");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    if (loading) return;

    setLoading(true);
    try {
      setError(null);
      const res = await fetch(`${apiBase}/api/device/summary`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }

      const payload = (await res.json()) as Summary;
      setData(payload);
      setModeState(payload.mode);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const changeMode = useCallback(async (next: "mock" | "real") => {
    setLoading(true);
    try {
      setError(null);
      const res = await fetch(`${apiBase}/api/mode?mode=${next}`, {
        method: "POST",
      });

      if (!res.ok) throw new Error(await res.text());

      setModeState(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }

    window.setTimeout(() => refresh(), 150);
  }, [refresh]);

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (mode === "real") refresh();
    }, 15000);

    return () => window.clearInterval(timer);
  }, [mode, refresh]);

  const status = useMemo(
    () => (data?.connected ? "Connected" : "Disconnected"),
    [data],
  );

  const csqPercent = data?.csq == null
    ? 0
    : Math.max(0, Math.min(100, (data.csq / 31) * 100));

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
          {nav.map(([label, Icon], index) => (
            <button className={`nav-item ${index === 0 ? "active" : ""}`} key={label}>
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="device-card">
          <div className="device-row">
            <Wifi size={18} />
            <strong>ZLT T6R-A</strong>
          </div>
          <div className="connected-dot-row">
            <span className={`dot ${error ? "red" : ""}`} />
            {error ? "Backend error" : status}
          </div>
          <div className="small muted">
            {data?.port ?? "COM port unknown"} · {mode.toUpperCase()}
          </div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <div className="title-row">
              <h1>ZLT T6R-A</h1>
              <span className="status-pill">{status}</span>
              <span className={`mode-pill ${mode}`}>{mode.toUpperCase()}</span>
            </div>
            <p>
              Network Lab v0.2 · query-only modem research interface
              {lastUpdated ? ` · updated ${lastUpdated.toLocaleTimeString()}` : ""}
            </p>
          </div>

          <div className="header-actions">
            <div className="mode-switch">
              <button
                className={mode === "mock" ? "selected" : ""}
                onClick={() => changeMode("mock")}
                disabled={loading}
              >
                Mock
              </button>
              <button
                className={mode === "real" ? "selected" : ""}
                onClick={() => changeMode("real")}
                disabled={loading}
              >
                Real COM12
              </button>
            </div>

            <button className="refresh-button" onClick={refresh} disabled={loading}>
              <RefreshCw size={16} className={loading ? "spin" : ""} />
              {loading ? "Reading…" : "Refresh"}
            </button>
          </div>
        </header>

        <section className="safety-strip">
          <ShieldCheck size={17} />
          <strong>Safe mode:</strong>
          query-only AT commands · no firmware writes · no NVRAM/IMEI changes
        </section>

        {error && (
          <div className="error-banner">
            <WifiOff size={17} />
            <div>
              <strong>Real modem read failed.</strong>
              <div>{error}</div>
              <small>
                v50 may briefly hold COM12. Wait a few seconds and press Refresh.
              </small>
            </div>
          </div>
        )}

        <section className="summary-grid">
          <ValueCard label="Operator" value={data?.operator ?? "—"} icon={Antenna} />
          <ValueCard label="RAT" value={data?.rat ?? "—"} icon={Signal} />
          <ValueCard label="CFUN" value={data?.cfun?.toString() ?? "—"} icon={Activity} />
          <ValueCard label="SIM" value={data?.sim_status ?? "—"} icon={Database} />
          <ValueCard label="APN" value={data?.apn ?? "—"} icon={Network} />
          <ValueCard label="IPv4 / PDP" value={data?.ipv4 ?? "—"} icon={Globe2} />
        </section>

        <section className="dashboard-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Cellular state</span>
                <h2>Registration</h2>
              </div>
              <Antenna size={22} />
            </div>

            <div className="status-list">
              <div><span>SIM ready</span><BoolPill value={data?.sim_status === "READY"} /></div>
              <div><span>Network registered</span><BoolPill value={Boolean(data?.registered)} /></div>
              <div><span>Packet attached</span><BoolPill value={Boolean(data?.packet_attached)} /></div>
              <div><span>Any PDP active</span><BoolPill value={Boolean(data?.pdp_active)} /></div>
              <div><span>PCUI port</span><strong>{data?.port ?? "—"}</strong></div>
            </div>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Radio</span>
                <h2>Signal</h2>
              </div>
              <Signal size={22} />
            </div>

            <div className="signal-hero">
              <div>
                <span>CSQ</span>
                <strong>{data?.csq ?? "—"}{data?.csq == null ? "" : " / 31"}</strong>
              </div>
              <div className="signal-meter">
                <span style={{ width: `${csqPercent}%` }} />
              </div>
            </div>

            <div className="raw-small">
              <strong>HCSQ RAT:</strong> {data?.hcsq?.rat ?? "—"}
            </div>
            <div className="raw-small">
              <strong>Vendor values:</strong>{" "}
              {data?.hcsq?.raw_values?.length
                ? data.hcsq.raw_values.join(", ")
                : "—"}
            </div>
            <p className="hint">
              Raw Balong HCSQ values are displayed without unverified conversion formulas.
            </p>
          </article>

          <article className="panel wide">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Packet data</span>
                <h2>APN / PDP Contexts</h2>
              </div>
              <Network size={22} />
            </div>

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
                      <td>
                        <BoolPill value={row.active} yes="Active" no="Inactive" />
                      </td>
                      <td className="mono">
                        {row.addresses.length
                          ? row.addresses.join(" · ")
                          : row.pdp_address || "—"}
                      </td>
                    </tr>
                  ))}
                  {!data?.contexts?.length && (
                    <tr>
                      <td colSpan={5} className="empty-row">No PDP contexts returned.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </article>

          <article className="panel wide">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Vendor diagnostics</span>
                <h2>Balong State</h2>
              </div>
              <FileJson size={22} />
            </div>

            <div className="diagnostic-cards">
              <div>
                <span>SYSINFOEX</span>
                <code>{data?.sysinfoex || "—"}</code>
              </div>
              <div>
                <span>HCSQ</span>
                <code>{data?.hcsq?.raw || "—"}</code>
              </div>
            </div>

            <button className="secondary-button" onClick={() => setShowRaw((v) => !v)}>
              <TerminalSquare size={16} />
              {showRaw ? "Hide raw AT responses" : "Show raw AT responses"}
            </button>

            {showRaw && (
              <div className="raw-grid">
                {Object.entries(data?.raw ?? {}).map(([name, value]) => (
                  <div className="raw-card" key={name}>
                    <strong>{name}</strong>
                    <pre>{value}</pre>
                  </div>
                ))}
              </div>
            )}
          </article>
        </section>

        <section className="panel notice-panel">
          <div>
            <span className="eyebrow">Next milestone</span>
            <h2>Real telemetry first; firmware stays offline</h2>
            <p>
              Once Real COM12 mode displays the same Globe/baseband facts we have already
              established manually, the next code milestone is logging + cell/signal history.
              Firmware acquisition and patching remain a separate offline track until the
              recovery gates are complete.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
