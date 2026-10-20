# Local tool service

The Python service exposes ACE-Step, MiniMax Music 3, and YuE through one persistent job queue. Use the REST API, the browser at `/ui/`, or Streamable HTTP MCP at `/mcp`. Each tool accepts the existing [Markdown song format](song-generation-jobs.md) and produces a downloadable WAV.

## Install and start

Install the music tools/models using the existing commands, then:

```powershell
just install tool-service
Copy-Item config/tool-service.keys.example.yaml config/tool-service.keys.yaml
# Edit the new file: replace every example with your own keys.
just validate tool-service
just serve
```

Installation is safe to rerun, syncs the committed lockfile into `apps/tool-service/.venv`, and never creates, prints, or overwrites credentials. It does not launch the server or download music models. The optional `service` profile installs this component; `full` includes it. The default `music` profile remains unchanged. Provision the ignored keys file before unattended validation of `service` or `full`.

Open [Local tools](http://127.0.0.1:8000/ui/), enter a key, and connect. Choose a tool, load its example or write a job, then click **Download**. The page submits once, polls every two seconds, and downloads when the WAV is ready. Recent jobs retain download buttons. Closing the page does not stop accepted work; reconnect after refresh to retrieve results. Authentication stays in tab memory; it is not written to local/session storage. Markdown is never rendered as HTML.

The server runs in the foreground; Ctrl+C stops it and interrupts active generation. There is no Windows service installation, OAuth login, upload support, cancellation endpoint, or automatic deletion in v1.

## Configuration and credentials

`config/tool-service.yaml` declares the listener, advertised URL, host/origin allowlists, key-file location, queue limit, text limit, enabled adapters, and state subdirectory. Keys use a separate plain YAML list:

```yaml
- your-long-random-key
- "user:your-long-random-password"
```

Never commit the real file. `config/tool-service.keys.yaml` is ignored; if you choose another location, keep that file outside tracked source too. Restart after changing keys or configuration. Empty lists, duplicates, malformed YAML, and unchanged example keys prevent startup.

Every key is accepted as `Authorization: Bearer <key>`. A key containing a colon can also be sent as HTTP Basic credentials: the decoded `user:password` must match the entire key exactly. Both representations have the same job ownership. Different keys cannot list, inspect, or download each other's jobs. Changing/removing a key removes network access to its old jobs; their files remain available to the local operator. This is an access gate for trusted users, not an operating-system sandbox or a user-account system.

The default listener is `127.0.0.1:8000`. For LAN access, set `host` to `0.0.0.0` or a specific IPv4 address; set `public_url` to the address clients use, and add its hostname/IP to `allowed_hosts` and full origin to `allowed_origins`. Keep localhost entries for local diagnostics. The URL is used in REST/MCP results; incoming Host headers never determine result URLs. There are no credential-bearing URLs, cookies, or cross-origin API permissions. The allowlists reject unexpected Host and Origin headers, including on MCP.

Use a trusted network or an HTTPS reverse proxy when credentials leave localhost: Basic/Bearer headers are plaintext over HTTP. TLS termination is external to Python. Configure the externally advertised HTTPS origin explicitly and preserve an allowed Host header at the proxy. Proxy forwarding headers are not trusted. Clients must support sending an Authorization header; OAuth-only MCP clients cannot connect directly.

Workspace root and `bin`/`work` locations come from `config/workspace.yaml`, including `AI_WORKSPACE_ROOT`. Existing runner configs in the workspace's `bin` directory determine model paths, runtimes, and per-tool generation timeouts. The service uses the tracked runners with that fixed working directory; submitted Markdown cannot choose commands or deployment paths.

## REST API

All `/api/` endpoints require authentication, including health checks. The UI shell is public.

| Request | Result |
| --- | --- |
| `GET /api/tools` | Tool metadata, Markdown examples, readiness, and repair commands. |
| `POST /api/tools/{tool_name}` | JSON `{"text":"…"}`; `202` and a job object plus `Location` header. |
| `GET /api/jobs?limit=20&offset=0` | Own jobs, newest first; `jobs`, `total`, `limit`, `offset`. Limit is 1–100. |
| `GET /api/jobs/{id}` | State, timestamps, error, status URL, and download URL when complete. |
| `GET /api/jobs/{id}/download` | WAV attachment with byte-range support; `409` until successful, `410` if removed locally. |
| `GET /api/health` | Service identity and worker/database readiness. |

Example using a process-local environment variable containing an existing configured key:

```powershell
$headers = @{ Authorization = "Bearer $env:TOOL_SERVICE_KEY"; 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$text = Get-Content examples/song-jobs/ace-step-first-song.md -Raw
$job = Invoke-RestMethod http://127.0.0.1:8000/api/tools/ace-step -Method Post -Headers $headers -ContentType application/json -Body (@{ text = $text } | ConvertTo-Json)
do {
    Start-Sleep -Seconds 2
    $job = Invoke-RestMethod $job.status_url -Headers $headers
} while ($job.state -in @('queued', 'running'))
if ($job.state -eq 'succeeded') {
    Invoke-WebRequest $job.download_url -Headers $headers -OutFile "$($job.id).wav"
} else { $job.error }
```

Retain `Idempotency-Key` when retrying a submission after a lost response. It is scoped to your key: identical tool/text returns the original job, while different input returns `409`. The key is 1–200 printable ASCII characters without spaces. Omit it or use a new value to request another generation. Even failed/interrupted jobs remain associated with their original idempotency key.

States are `queued`, `running`, `succeeded`, `failed`, and `interrupted`. Errors use `code`, `message`, and optionally `job_id`; unknown jobs and jobs owned by another key both return `404`. Invalid input returns `422`, text over the configured UTF-8 limit (default 1 MiB) returns `413`, unavailable tools return `503`, and a full queue returns `429`. JSON transport permits escaping overhead but is also bounded. Only `text` is accepted in a submission; uploads and local reference-audio paths are unsupported by the current adapters.

## MCP

Configure a **Streamable HTTP** server at `http://127.0.0.1:8000/mcp`, with `Authorization: Bearer <your-key>` in its request headers. Basic is also supported. Configuration syntax depends on the client; store credentials in its local secret settings rather than this repository.

Each enabled runner is a tool named `ace-step`, `minimax-music3`, or `yue`, accepting `text` and optional `idempotency_key`. Discovery includes its Markdown example. Tools return the job immediately; `get_job(job_id)` polls state and `list_jobs(limit, offset)` lists your work. Results include authenticated HTTP download links, not audio embedded in the protocol. Download using the same key. A client without an authenticated HTTP downloader can still create/monitor jobs and retrieve results through the UI.

The official SDK handles protocol negotiation and messages. HTTP is stateless at the MCP transport layer; job durability and ownership live in the shared service. SDK v1 is deliberately bounded below v2 and locked for interface stability; see the [supported SDK v1 documentation](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x). No experimental MCP task extension is required.

## Persistence, failures, and diagnostics

The default state location is `<workspace>/work/tool-service/jobs/`:

- `jobs.sqlite3` and SQLite WAL files: durable job metadata; treat these as user work.
- `<job-id>/job.md`, validation/runner logs, and `output/`: input and preserved artifacts.
- `service.log`: rotating operator log, with three backups.
- `service.lock`: OS-locked single-instance file; its mere existence does not indicate a running service.

One worker runs GPU jobs serially, with up to 100 queued jobs by default. SQLite acceptance commits before the response. Validation runs the existing runner's `--validate` mode, never generation, and reports missing tools/models without installing them. Invalid submissions retain a local directory for operator investigation but are not accepted into the queue.

On shutdown or crash, Windows Job Objects terminate the runner and descendants. Children cannot begin tool code before assignment to the Job Object. A startup lock prevents another service using the same state directory from starting a second worker. Use one Uvicorn worker and the supplied launcher; multiple state directories targeting the same GPU are unsupported.

After restart, queued jobs resume. Previously running jobs become `interrupted` and are never automatically retried. Submit a new request/idempotency key to retry. Timeouts use the runner configuration; partial artifacts and logs survive. A zero exit code without a readable expected stereo WAV is a failure. WAV artifacts are restricted to each job directory, and metadata never returns local paths or raw runner logs.

`just status` summarizes configured service state. `just doctor` validates an installed service and each enabled runner, checks the existing database, and probes authenticated health without generating music. `just validate tool-service` runs those service checks directly. An unstarted listener is informational; a missing key file or invalid adapter is a failure with repair instructions. Validation never initializes the job database. Installation logs live in the workspace `logs/` directory.

Keep access keys separate from inference credentials such as `HF_TOKEN`. No logs intentionally include access keys. Protect the state directory and logs using normal Windows account permissions: local operators can inspect inputs and audio. No cleanup command is supplied; preserve generated work and back up its database and artifacts together while the server is stopped.

## Development and verification

```powershell
just test-service
# Optional: also exercise the real browser flow in installed Microsoft Edge.
$env:TOOL_SERVICE_BROWSER_TEST = '1'
just test-service
Remove-Item Env:TOOL_SERVICE_BROWSER_TEST
```

Tests use fake runners and temporary state. They cover REST/MCP ownership and interoperability, idempotency, validation, serial execution, queue limits, restart recovery, process-tree termination, WAV verification/range downloads, and browser refresh/download behavior. The browser test uses headless installed Edge without downloading a browser. Routine tests do not load models or call inference services.

For an explicit GPU smoke test, start the configured service, load a tool's supplied example in `/ui/`, click Download, and inspect/listen to the WAV. Repeat only for tools you intend to exercise; this consumes GPU time and retains the generated files.

New tools require a registered adapter in the service, metadata/example input, validation, fixed invocation, and result verification. Add its identifier to the allowed adapter catalog and YAML tool list. There is intentionally no endpoint or generic configuration mechanism for arbitrary shell commands.
