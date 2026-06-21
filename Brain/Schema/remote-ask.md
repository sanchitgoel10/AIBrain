# Remote Ask

Remote Ask keeps the Brain vault, retrieval index, and API key on this Mac. A
separate read-only server exposes only the Ask interface on
`http://127.0.0.1:8766`. It does not expose capture, file-opening, or source
management endpoints.

## Local Test

```bash
scripts/run_remote_ask.sh
```

Open `http://127.0.0.1:8766`.

## Keep It Running

```bash
scripts/install_remote_ask_service.sh
```

The LaunchAgent restarts the server after login and writes logs under
`.aibrain/logs/`.

## Private Phone Access

1. Install Tailscale on the Mac and phone.
2. Sign into the same tailnet on both devices.
3. Run:

```bash
scripts/setup_remote_ask_tailscale.sh
```

The command prints the private HTTPS URL. Open that URL on the phone. Tailscale
Serve is private to authenticated devices in the tailnet; do not replace it
with Tailscale Funnel, which publishes the service to the internet.

The Mac must be awake, connected to the internet, and running the Remote Ask
service for answers to work.
