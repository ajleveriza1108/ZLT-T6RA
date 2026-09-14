import type { ReactNode } from "react";
import {
  Activity,
  Antenna,
  Database,
  FileCode2,
  Gauge,
  Globe2,
  History,
  Network,
  Radio,
  Router,
  Settings,
  ShieldCheck,
  Signal,
  TerminalSquare,
} from "lucide-react";

export const NAV_ITEMS = [
  ["dashboard", "Dashboard", Activity],
  ["sim", "SIM Info", Database],
  ["signal", "Signal Monitor", Signal],
  ["scan", "Network Scan", Antenna],
  ["pdp", "APN / PDP", Network],
  ["internet", "Internet Test", Gauge],
  ["logger", "Cell Logger", History],
  ["diagnostics", "Diagnostics", Router],
  ["at", "AT Console", TerminalSquare],
  ["firmware", "Firmware", FileCode2],
  ["settings", "Settings", Settings],
] as const;

export function Panel({
  title,
  eyebrow,
  icon,
  children,
  wide = false,
}: {
  title: string;
  eyebrow?: string;
  icon?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <section className={`panel ${wide ? "wide" : ""}`}>
      <div className="panel-heading">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {icon}
      </div>
      {children}
    </section>
  );
}

export function BoolPill({
  value,
  yes = "Yes",
  no = "No",
}: {
  value: boolean;
  yes?: string;
  no?: string;
}) {
  return (
    <span className={`bool-pill ${value ? "good" : "bad"}`}>
      <span className="tiny-dot" />
      {value ? yes : no}
    </span>
  );
}

export function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: ReactNode;
}) {
  return (
    <div className="value-card">
      <div className="value-icon">{icon}</div>
      <div className="value-copy">
        <div className="muted">{label}</div>
        <strong title={value}>{value}</strong>
      </div>
    </div>
  );
}

export function SafetyStrip() {
  return (
    <div className="safety-strip">
      <ShieldCheck size={17} />
      <strong>Safe development mode:</strong>
      no firmware writes · real AT console is query-only · no NVRAM / IMEI changes
    </div>
  );
}

export const statIcons = {
  operator: <Antenna size={18} />,
  rat: <Signal size={18} />,
  cfun: <Activity size={18} />,
  sim: <Database size={18} />,
  apn: <Network size={18} />,
  ipv4: <Globe2 size={18} />,
  radio: <Radio size={18} />,
};
