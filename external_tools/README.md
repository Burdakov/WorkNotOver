# External Open Source Tools

This directory is reserved for optional open source tools used by the `waterflood_proxy_hm` architecture.

The native WorkNotOver forecast path must not require these tools. They are optional validation/adaptation backends:

- `opm-common`: OPM/Eclipse deck conventions and property parsing reference.
- `mrst`: MRST Flow Diagnostics source for allocation factors, time-of-flight, swept/drainage volumes.
- `pywaterflood`: optional CRM and Buckley-Leverett helper.
- `res2df`: optional OPM/Eclipse result import helpers.

Downloaded sources are intentionally kept outside `backend/app` so the application can run without vendored simulators.

Current local state:

- `opm-common`, `pywaterflood` and `res2df` were downloaded as shallow clones.
- `mrst` is listed as optional in `manifest.json`; the local clone can be retried separately because the repository checkout exceeded the interactive timeout.
