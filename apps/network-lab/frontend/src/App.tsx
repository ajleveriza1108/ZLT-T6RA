import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Antenna,
  Database,
  Gauge,
  Globe2,
  Network,
  Radio,
  RefreshCw,
  Router,
  Settings,
  Signal,
  TerminalSquare,
  Wifi,
} from "lucide-react";

type Summary = {
  device: string;
  connected: boolean;
  operator: string;
  rat: string;
  band: string | null;
  pci: number | null;
  cfun: number | null;
  sim_status: string;
  registered: boolean;
  packet_attached: boolean;
  apn: string | null;
  wan: string | null;
  ipv4: string | null;
  signal: {
    rsrp: number | null;
    rsrq: number | null;
    sinr: number | null;
    rssi: number | null;
    csq: number | null;
  };
  internet: null | {
    ping_ms: number;
    packet_loss_pct: number;
    download_mbps: number;
    upload_mbps: number;
    dns: string;
  };
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
  ["Firmware", RefreshCw],
  ["Settings", Settings],
] as const;

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
      <div>
        <div className="muted">{label}</div>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setError(null);
      const res = await fetch(`${apiBase}/api/device/summary`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const status = useMemo(
    () => (data?.connected ? "Connected" : "Disconnected"),
    [data],
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
            <span className="dot" />
            {status}
          </div>
          <div className="small muted">Open. Test. Learn.</div>
        </div>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <div className="title-row">
              <h1>ZLT T6R-A</h1>
              <span className="status-pill">{status}</span>
            </div>
            <p>Network Lab · Safe query-only MVP</p>
          </div>
          <button className="refresh-button" onClick={refresh}>
            <RefreshCw size={16} />
            Refresh
          </button>
        </header>

        {error && (
          <div className="error-banner">
            Backend unavailable: {error}. Start the FastAPI service on port 8765.
          </div>
        )}

        <section className="summary-grid">
          <ValueCard label="Operator" value={data?.operator ?? "—"} icon={Antenna} />
          <ValueCard label="RAT" value={data?.rat ?? "—"} icon={Signal} />
          <ValueCard label="Band" value={data?.band ?? "—"} icon={Radio} />
          <ValueCard label="CFUN" value={data?.cfun?.toString() ?? "—"} icon={Activity} />
          <ValueCard label="APN" value={data?.apn ?? "—"} icon={Network} />
          <ValueCard label="WAN" value={data?.wan ?? "—"} icon={Globe2} />
        </section>

        <section className="dashboard-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Radio</span>
                <h2>Signal Quality</h2>
              </div>
              <Signal size={22} />
            </div>
            <div className="metric-list">
              {[
                ["RSRP", data?.signal.rsrp, "dBm"],
                ["RSRQ", data?.signal.rsrq, "dB"],
                ["SINR", data?.signal.sinr, "dB"],
                ["RSSI", data?.signal.rssi, "dBm"],
                ["CSQ", data?.signal.csq, "/ 31"],
              ].map(([label, value, suffix]) => (
                <div className="metric-row" key={label as string}>
                  <span>{label}</span>
                  <div className="metric-bar"><span /></div>
                  <strong>{value ?? "—"} {value == null ? "" : suffix}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Subscriber</span>
                <h2>SIM / Network</h2>
              </div>
              <Database size={22} />
            </div>
            <div className="status-list">
              <div><span>SIM</span><strong>{data?.sim_status ?? "—"}</strong></div>
              <div><span>Registered</span><strong>{data?.registered ? "Yes" : "No"}</strong></div>
              <div><span>Packet attached</span><strong>{data?.packet_attached ? "Yes" : "No"}</strong></div>
              <div><span>PCI</span><strong>{data?.pci ?? "—"}</strong></div>
              <div><span>IPv4</span><strong>{data?.ipv4 ?? "—"}</strong></div>
            </div>
          </article>

          <article className="panel wide">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">Diagnostics</span>
                <h2>Internet Test</h2>
              </div>
              <Gauge size={22} />
            </div>
            <div className="diagnostic-grid">
              <div><span>Ping</span><strong>{data?.internet ? `${data.internet.ping_ms} ms` : "—"}</strong></div>
              <div><span>Packet loss</span><strong>{data?.internet ? `${data.internet.packet_loss_pct}%` : "—"}</strong></div>
              <div><span>Download</span><strong>{data?.internet ? `${data.internet.download_mbps} Mbps` : "—"}</strong></div>
              <div><span>Upload</span><strong>{data?.internet ? `${data.internet.upload_mbps} Mbps` : "—"}</strong></div>
              <div><span>DNS</span><strong>{data?.internet?.dns ?? "—"}</strong></div>
            </div>
          </article>
        </section>

        <section className="panel notice-panel">
          <div>
            <span className="eyebrow">Development status</span>
            <h2>Mock-first, production-safe</h2>
            <p>
              The initial UI runs against a simulated modem. Real mode uses an approved
              query-only AT command set. Firmware flashing is outside the application MVP
              and remains blocked until recovery and image-verification gates pass.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
