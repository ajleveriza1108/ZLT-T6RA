import type {
  DeviceSummary,
  FirmwareStatus,
  InternetResult,
  Mode,
  NetworkResult,
  TelemetrySample,
} from "./types";

const base = "http://127.0.0.1:8765";

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }

  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<{
    ok: boolean;
    version: string;
    mode: Mode;
    detected_port: string | null;
    write_commands_enabled: boolean;
    firmware_writes_enabled: boolean;
  }> =>
    fetch(`${base}/api/health`).then((res) =>
      parseResponse<{
        ok: boolean;
        version: string;
        mode: Mode;
        detected_port: string | null;
        write_commands_enabled: boolean;
        firmware_writes_enabled: boolean;
      }>(res),
    ),

  summary: (): Promise<DeviceSummary> =>
    fetch(`${base}/api/device/summary`).then((res) =>
      parseResponse<DeviceSummary>(res),
    ),

  setMode: (mode: Mode): Promise<{ mode: Mode }> =>
    fetch(`${base}/api/mode?mode=${mode}`, {
      method: "POST",
    }).then((res) => parseResponse<{ mode: Mode }>(res)),

  scanNetworks: (
    confirm = false,
  ): Promise<{ results: NetworkResult[]; note: string }> =>
    fetch(`${base}/api/network/scan?confirm=${confirm}`, {
      method: "POST",
    }).then((res) =>
      parseResponse<{ results: NetworkResult[]; note: string }>(res),
    ),

  internetTest: (): Promise<InternetResult> =>
    fetch(`${base}/api/internet/test`, {
      method: "POST",
    }).then((res) => parseResponse<InternetResult>(res)),

  telemetry: (
    limit = 120,
  ): Promise<{ samples: TelemetrySample[] }> =>
    fetch(`${base}/api/telemetry?limit=${limit}`).then((res) =>
      parseResponse<{ samples: TelemetrySample[] }>(res),
    ),

  captureTelemetry: (): Promise<TelemetrySample> =>
    fetch(`${base}/api/telemetry/capture`, {
      method: "POST",
    }).then((res) => parseResponse<TelemetrySample>(res)),

  queryAt: (
    key: string,
  ): Promise<{ command: string; response: string }> =>
    fetch(`${base}/api/at/query?key=${encodeURIComponent(key)}`, {
      method: "POST",
    }).then((res) =>
      parseResponse<{ command: string; response: string }>(res),
    ),

  atCommands: (): Promise<{
    commands: Record<string, string>;
  }> =>
    fetch(`${base}/api/at/commands`).then((res) =>
      parseResponse<{ commands: Record<string, string> }>(res),
    ),

  firmwareStatus: (): Promise<FirmwareStatus> =>
    fetch(`${base}/api/firmware/status`).then((res) =>
      parseResponse<FirmwareStatus>(res),
    ),
};
