# Deployment (VPS + Docker Compose)

This is the easiest production setup for NOVA.

## 1. Server prerequisites

- Ubuntu 22.04 or 24.04 VPS
- Domain name pointed to server IP
- Ports 80 and 443 open in firewall/security group

Install Docker + Compose plugin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 2. Clone and configure

```bash
git clone <your-repo-url> nova
cd nova
cp .env.production.example .env.production
```

Edit .env.production and set at least:

- OPERATIONAL_API_KEY
- FRONTEND_URL
- VITE_API_KEY (usually same as OPERATIONAL_API_KEY)
- GROQ_API_KEY and/or ANTHROPIC_API_KEY
- APIFY_API_TOKEN and Reddit creds if scraper is used

## 3. Start services

```bash
sudo docker compose --env-file .env.production up -d --build
sudo docker compose ps
```

Frontend will be available on port 80.

## 4. Verify

```bash
curl http://127.0.0.1/api/health
```

If API auth is enabled, include header:

```bash
curl -H "X-API-Key: <OPERATIONAL_API_KEY>" http://127.0.0.1/api/scraped-posts
```

## 5. Logs

```bash
sudo docker compose logs -f frontend
sudo docker compose logs -f backend
```

## 6. TLS (HTTPS)

Recommended: put Caddy or Nginx Proxy Manager in front for automatic Let's Encrypt.

Simple Caddy option (outside this compose): reverse proxy your domain to `localhost:80`.

## 7. Updates

```bash
git pull
sudo docker compose --env-file .env.production up -d --build
```

## Notes

- SQLite is persisted in Docker volume `nova_data`.
- Backend logs are persisted in Docker volume `nova_logs`.
- For larger scale or multiple backend replicas, migrate from SQLite to Postgres.
