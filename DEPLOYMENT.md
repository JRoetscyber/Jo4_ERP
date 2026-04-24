# Deployment

This repository now includes a production Flask WSGI entrypoint, Gunicorn config, Docker image, and Docker Compose stack with an optional Cloudflare Tunnel sidecar.

## Included files

- `wsgi.py`: Gunicorn entrypoint.
- `gunicorn.conf.py`: worker and timeout settings.
- `Dockerfile`: production image for the Flask app.
- `docker-compose.yml`: app container plus `cloudflared`.
- `.env.example`: environment variables you need to set.
- `cloudflared/config.yml.example`: example for a locally-managed tunnel if you prefer config files over tunnel tokens.

## Recommended path

Cloudflare currently recommends remotely-managed tunnels for most deployments. In that model, the tunnel runs with a token and Cloudflare stores the tunnel configuration remotely.

Reference:
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/
- https://developers.cloudflare.com/tunnel/advanced/tunnel-tokens/

## Server steps

1. Copy the project to the Linux server.
2. Copy `.env.example` to `.env` and replace the placeholder values.
   On a 64-bit Raspberry Pi, set `CLOUDFLARED_IMAGE=cloudflare/cloudflared:latest-arm64`.
3. Make sure Docker and Docker Compose are installed.
4. Start the stack:

```bash
docker compose up -d --build
```

5. Check logs:

```bash
docker compose logs -f app
docker compose logs -f cloudflared
```

## Cloudflare Tunnel setup

### Option A: Remotely-managed tunnel

1. In Cloudflare, create a tunnel.
2. Copy the tunnel token and place it in `.env` as `CLOUDFLARED_TOKEN`.
   If the server is `linux/arm64` or `linux/arm/v8`, also set `CLOUDFLARED_IMAGE=cloudflare/cloudflared:latest-arm64`.
3. In the tunnel public hostname configuration, point your hostname to the local service.

Service value to use:

```text
http://app:8000
```

That service hostname is resolved by the `cloudflared` container over the Docker network.

### Option B: Locally-managed tunnel

If you want the tunnel config on the server instead of in Cloudflare:

1. Create the tunnel on the server with `cloudflared tunnel create <name>`.
2. Copy the generated credentials JSON to the server.
3. Start `cloudflared` with a config based on `cloudflared/config.yml.example`.

Reference:
- https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/
- https://developers.cloudflare.com/tunnel/routing/

## Notes

- The app stores SQLite under `./instance/erp.sqlite` by default.
- Do not expose port `8000` publicly when you are using Cloudflare Tunnel.
- Use a strong `SECRET_KEY`.
- If you move to PostgreSQL later, set `DATABASE_URL` accordingly and mount persistent storage for the database separately.
