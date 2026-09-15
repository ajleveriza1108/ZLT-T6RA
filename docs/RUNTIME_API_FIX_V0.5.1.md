# Runtime API Fix v0.5.1

The frontend no longer depends on a Vite proxy or a fixed API URL.

At development launch:

1. the launcher allocates free loopback ports;
2. it writes `frontend/public/runtime.json` locally with the actual backend URL;
3. the frontend reads that runtime file before every first API use;
4. the backend receives the actual frontend origin through `T6RA_ALLOWED_ORIGIN`;
5. CORS is therefore restricted to the dynamically launched frontend;
6. the runtime file is gitignored and is never committed.

The launcher also stores only the development-server process IDs in the user's local application-data directory so the next run can stop its own previous runtime safely.

No modem configuration, NVRAM, firmware, or IMEI writes are performed.
