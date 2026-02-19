# Deployment Guide for eidosSpeech v2 (Docker)

This guide explains how to deploy the application in production using Docker and Docker Compose.

## 1. Prerequisites

Ensure you have Docker and Docker Compose installed on your server (VPS):
```bash
# Ubuntu
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```
*(You may need to logout and login again for group changes to take effect)*

## 2. Configuration

1. Clone or upload your project to the server.
2. Create your production environment file:
   ```bash
   cp .env.production.example .env
   ```
3. **IMPORTANT**: Edit `.env` and set secure values for:
   - `SECRET_KEY` (use `openssl rand -hex 32` to generate one)
   - `ADMIN_KEY`
   - `SMTP_...` (Email settings for user registration)

## 3. Deployment

1. Build and start the container:
   ```bash
   docker-compose up -d --build
   ```
2. Checks logs to ensure everything is running:
   ```bash
   docker-compose logs -f
   ```

## 4. Host Nginx Configuration

Since you are using Nginx on the host, create a new site configuration:

```nginx
server {
    listen 80;
    server_name eidosspeech.xyz;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Timeouts for longer TTS processing
    proxy_read_timeout 120s;
    proxy_connect_timeout 120s;
}
```

Then enable and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/eidosspeech /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Maintenance

- **Update Code**: `git pull` then `docker-compose up -d --build api`
- **View Logs**: `docker-compose logs -f --tail=100`
- **Backup DB**: The database is in `./data/db/eidosspeech.db`. Just copy this file.

## 6. Troubleshooting

- **502 Bad Gateway**: The API container is not running or crashing. Check `docker-compose logs api`.
- **Permission Denied (Data)**: Issues with `/app/data`. Run `docker-compose down` and verify directory permissions on host, or `chown` them.
