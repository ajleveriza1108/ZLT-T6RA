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

type LocalRuntime = {
  apiBase: string;
};

let runtimePromise: Promise<LocalRuntime> | null = null;

async function runtime(): Promise<LocalRuntime> {
  if (!runtimePromise) {
    runtimePromise = fetch("/runtime.json", {
      cache: "no-store",
    }).then(async (response) => {
      if (!response.ok) {
        throw new Error(
          `Runtime configuration unavailable: HTTP ${response.status}`,
        );
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.includes("application/json")) {
        throw new Error(
          "Runtime configuration did not return JSON.",
        );
      }

      const value = (await response.json()) as Partial<LocalRuntime>;

      if (!value.apiBase || typeof value.apiBase !== "string") {
        throw new Error("runtime.json does not contain apiBase.");
      }

      return {
        apiBase: value.apiBase.replace(/\/+$/, ""),
      };
    });
  }

  return runtimePromise;
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const cfg = await runtime();
  const response = await fetch(`${cfg.apiBase}${path}`, init);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (!contentType.includes("application/json")) {
    const preview = (await response.text()).slice(0, 120);
    throw new Error(
      `API expected JSON but received ${contentType || "unknown content type"}: ${preview}`,
    );
  }

  return (await response.json()) as T;
}

export const api = {
  health: (): Promise<Health> =>
    request<Health>("/api/health"),

  summary: (): Promise<DeviceSummary> =>
    request<DeviceSummary>("/api/device/summary"),

  getConfig: (): Promise<RuntimeConfig> =>
    request<RuntimeConfig>("/api/config"),

  setSerialPort: (
    port: string | null,
  ): Promise<RuntimeConfig> =>
    request<RuntimeConfig>("/api/config/serial", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ port }),
    }),

  discoverDevices: (): Promise<{
    candidates: SerialPortInfo[];
    resolved_port: string | null;
  }> =>
    request<{
      candidates: SerialPortInfo[];
      resolved_port: string | null;
    }>("/api/device/discover", {
      method: "POST",
    }),

  setMode: (mode: Mode): Promise<{ mode: Mode }> =>
    request<{ mode: Mode }>(
      `/api/mode?mode=${encodeURIComponent(mode)}`,
      {
        method: "POST",
      },
    ),

  scanNetworks: (
    confirm = false,
  ): Promise<{
    results: NetworkResult[];
    note: string;
  }> =>
    request<{
      results: NetworkResult[];
      note: string;
    }>(
      `/api/network/scan?confirm=${confirm ? "true" : "false"}`,
      {
        method: "POST",
      },
    ),

  internetTest: (): Promise<InternetResult> =>
    request<InternetResult>("/api/internet/test", {
      method: "POST",
    }),

  telemetry: (
    limit = 120,
  ): Promise<{ samples: TelemetrySample[] }> =>
    request<{ samples: TelemetrySample[] }>(
      `/api/telemetry?limit=${encodeURIComponent(String(limit))}`,
    ),

  captureTelemetry: (): Promise<TelemetrySample> =>
    request<TelemetrySample>("/api/telemetry/capture", {
      method: "POST",
    }),

  queryAt: (
    key: string,
  ): Promise<{
    command: string;
    response: string;
  }> =>
    request<{
      command: string;
      response: string;
    }>(
      `/api/at/query?key=${encodeURIComponent(key)}`,
      {
        method: "POST",
      },
    ),

  atCommands: (): Promise<{
    commands: Record<string, string>;
  }> =>
    request<{
      commands: Record<string, string>;
    }>("/api/at/commands"),

  firmwareStatus: (): Promise<FirmwareStatus> =>
    request<FirmwareStatus>("/api/firmware/status"),
};
