# Native OpenClaw Control UI

The persistent Gateway serves OpenClaw's native browser Control UI on the same
port as its WebSocket API. Compose publishes that port on VPS loopback only:

```text
127.0.0.1:18789 -> gateway:18789
```

It is deliberately not exposed on the VPS public interface.

## Deploy

From the production checkout:

```bash
git pull
docker compose up -d --build gateway worker
docker compose ps
```

Confirm that Docker published only the loopback address:

```bash
docker compose port gateway 18789
```

Expected:

```text
127.0.0.1:18789
```

## Connect

Create tunnels for both interfaces:

```bash
ssh \
  -L 18090:127.0.0.1:18090 \
  -L 18789:127.0.0.1:18789 \
  root@138.199.219.143
```

Then open:

- Agent Workbench: <http://127.0.0.1:18090/>
- Native OpenClaw: <http://127.0.0.1:18789/>

Authenticate the Control UI with the existing `OPENCLAW_GATEWAY_TOKEN` from
the VPS `.env`. Treat that token as a password and do not paste it into logs,
issues or chat.

The native UI talks directly to the persistent Gateway. It exposes OpenClaw's
own chat sessions and operational controls. The Agent Workbench remains the
product-facing interface for uploads, queued analysis and repeatable workflows.

## Verify

On the VPS:

```bash
docker compose ps
docker compose logs --tail=100 gateway
curl --fail --silent --show-error \
  --output /dev/null \
  http://127.0.0.1:18789/
```

A successful `curl` confirms that the Control UI assets are being served. A
browser connection additionally verifies Gateway authentication and WebSocket
access.

## Security

- Keep the host binding exactly `127.0.0.1:18789:18789`.
- Do not add a public firewall rule or public Nginx route for this port.
- Keep Gateway token authentication enabled.
- Use the SSH tunnel for remote access.
- Rotate `OPENCLAW_GATEWAY_TOKEN` if it is exposed.
