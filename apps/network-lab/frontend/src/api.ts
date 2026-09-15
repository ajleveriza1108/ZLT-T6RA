import type {
  DeviceSummary,
  FirmwareStatus,
  Health,
  InternetResult,
  Mode,
  NetworkResult,
  RuntimeConfig,
  SerialPortInfo,
  TelemetrySample,
} from "./types";

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }

  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<Health> =>
    fetch("/api/health").then((res) =>
      parseResponse<Health>(res),
    ),

  summary: (): Promise<DeviceSummary> =>
    fetch("/api/device/summary").then((res) =>
      parseResponse<DeviceSummary>(res),
    ),

  getConfig: (): Promise<RuntimeConfig> =>
    fetch("/api/config").then((res) =>
      parseResponse<RuntimeConfig>(res),
    ),

  setSerialPort: (
    port: string | null,
  ): Promise<RuntimeConfig> =>
    fetch("/api/config/serial", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ port }),
    }).then((res) => parseResponse<RuntimeConfig>(res)),

  discoverDevices: (): Promise<{
    candidates: SerialPortInfo[];
    resolved_port: string | null;
  }> =>
    fetch("/api/device/discover", {
      method: "POST",
    }).then((res) =>
      parseResponse<{
        candidates: SerialPortInfo[];
        resolved_port: string | null;
      }>(res),
    ),

  setMode: (mode: Mode): Promise<{ mode: Mode }> =>
    fetch(`/api/mode?mode=${mode}`, {
      method: "POST",
    }).then((res) =>
      parseResponse<{ mode: Mode }>(res),
    ),

  scanNetworks: (
    confirm = false,
  ): Promise<{
    results: NetworkResult[];
    note: string;
  }> =>
    fetch(`/api/network/scan?confirm=${confirm}`, {
      method: "POST",
    }).then((res) =>
      parseResponse<{
        results: NetworkResult[];
        note: string;
      }>(res),
    ),

  internetTest: (): Promise<InternetResult> =>
    fetch("/api/internet/test", {
      method: "POST",
    }).then((res) =>
      parseResponse<InternetResult>(res),
    ),

  telemetry: (
    limit = 120,
  ): Promise<{ samples: TelemetrySample[] }> =>
    fetch(`/api/telemetry?limit=${limit}`).then((res) =>
      parseResponse<{ samples: TelemetrySample[] }>(res),
    ),

  captureTelemetry: (): Promise<TelemetrySample> =>
    fetch("/api/telemetry/capture", {
      method: "POST",
    }).then((res) =>
      parseResponse<TelemetrySample>(res),
    ),

  queryAt: (
    key: string,
  ): Promise<{
    command: string;
    response: string;
  }> =>
    fetch(`/api/at/query?key=${encodeURIComponent(key)}`, {
      method: "POST",
    }).then((res) =>
      parseResponse<{
        command: string;
        response: string;
      }>(res),
    ),

  atCommands: (): Promise<{
    commands: Record<string, string>;
  }> =>
    fetch("/api/at/commands").then((res) =>
      parseResponse<{
        commands: Record<string, string>;
      }>(res),
    ),

  firmwareStatus: (): Promise<FirmwareStatus> =>
    fetch("/api/firmware/status").then((res) =>
      parseResponse<FirmwareStatus>(res),
    ),
};
