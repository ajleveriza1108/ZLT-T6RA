export type Mode = "mock" | "real";

export type PdpContext = {
  cid: number;
  pdp_type: string;
  apn: string;
  pdp_address: string;
  active: boolean;
  addresses: string[];
};

export type DeviceSummary = {
  device: string;
  connected: boolean;
  mode: Mode;
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
  contexts: PdpContext[];
  apn: string | null;
  ipv4: string | null;
  pdp_active: boolean;
  raw: Record<string, string>;
};

export type NetworkResult = {
  operator: string;
  numeric: string;
  rat: string;
  status: string;
};

export type InternetResult = {
  dns_ok: boolean;
  dns_answer: string | null;
  ping_target: string;
  ping_ok: boolean;
  ping_ms: number | null;
  packet_loss_pct: number | null;
  download_mbps: number | null;
  upload_mbps: number | null;
  note: string;
};

export type TelemetrySample = {
  timestamp: string;
  operator: string;
  rat: string;
  csq: number | null;
  registered: boolean;
  packet_attached: boolean;
  pdp_active: boolean;
  apn: string | null;
};

export type FirmwareStatus = {
  flashing_enabled: boolean;
  current_track: string;
  gates: Array<{
    id: string;
    title: string;
    status: "pending" | "pass" | "blocked";
    detail: string;
  }>;
};

export type SerialPortInfo = {
  device: string;
  description: string | null;
  manufacturer: string | null;
  product: string | null;
  interface: string | null;
  hwid: string | null;
  score: number;
  responsive?: boolean;
  identity?: string | null;
  model?: string | null;
  error?: string | null;
};

export type RuntimeConfig = {
  settings: {
    runtime: {
      mode: Mode;
    };
    serial: {
      port: string | null;
      baudrate: number;
      read_timeout_seconds: number;
      write_timeout_seconds: number;
      query_timeout_seconds: number;
      open_retries: number;
      scan_timeout_seconds: number;
    };
    network: {
      dns_test_host: string;
      ping_target: string;
      ping_count: number;
      ping_timeout_ms: number;
    };
  };
  resolved_port: string | null;
  ports: SerialPortInfo[];
};

export type Health = {
  ok: boolean;
  name: string;
  version: string;
  mode: Mode;
  detected_port: string | null;
  write_commands_enabled: boolean;
  firmware_writes_enabled: boolean;
};
