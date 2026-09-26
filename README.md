# Ollama Console

A small web interface for an Ollama server running inside a Debian container. It uses only the Python standard library, so there are no frontend build tools or Python packages to install.

## Install

On the Debian container:

```sh
cd /home/ollama
git clone https://github.com/TheRebellious/ollama-webinterface.git
cd ollama-webinterface
cp config.example.json config.json
```

Edit `config.json` if needed:

```json
{
  "host": "0.0.0.0",
  "port": 8080,
  "ollama_url": "http://127.0.0.1:11434",
  "debug_shutdown": false,
  "upload_max_mb": 10,
  "log_file": "ollama-console.log"
}
```

By default the UI proxies Ollama at:

```text
http://127.0.0.1:11434
```

## Run Manually

From the repository directory:

```sh
python3 server.py
```

Open:

```text
http://SERVER_IP:8080
```

If you want to use a different config file:

```sh
python3 server.py --config /path/to/config.json
```

`config.json` is ignored by git for local deployment changes. CLI flags and legacy environment variables still work as overrides.

## Logging

The server writes request activity, errors, and uncaught handler exceptions to
`ollama-console.log` by default. The log is opened in append mode, so restarting
the server preserves previous entries. Set `log_file` in `config.json`, pass
`--log-file /path/to/server.log`, or set `OLLAMA_CONSOLE_LOG_FILE` to use another
location. Relative log paths are resolved beside the selected config file, so a
systemd service does not write logs to an unexpected working directory.

For local debugging, start it with an in-page exit button:

```sh
python3 server.py --debug-shutdown
```

This exposes `POST /api/shutdown` and shows an `Exit server` button in the sidebar. Do not enable this on a public server.

## Pull a model

If the UI says no models were found, pull one first:

```sh
ollama pull llama3.1
```

## Upload files

The UI can attach files to your next message. Text-like files are read in your browser and included as prompt context. Office Open XML files are sent to the Python server for text extraction, but they are not stored.

Supported base types include:

```text
.txt, .md, .csv, .json, .jsonl, .log, .xml, .yaml, .yml,
.toml, .ini, .conf, .cfg, source code files, shell scripts, SQL,
Dockerfile, .gitignore, .docx, .xlsx, and .pptx
```

The default file limit is 10 MB. You can change it with `upload_max_mb` in `config.json`. Large files can still exceed the selected model's context window after text extraction.

## Machine stats

The sidebar shows live machine stats from `/api/system`, including CPU, memory, disk usage, load average, uptime, and GPU usage. NVIDIA GPUs are detected with `nvidia-smi`; AMD GPUs are detected with `lspci`, Windows video-controller data, `amd-smi`, `rocm-smi`, or Linux sysfs when available. Windows RAM detection uses the native system API. The UI refreshes this every 5 seconds.

On Windows, the machine panel shows CPU load as a percentage. On Linux and other Unix-like systems, it shows load average for the last 1, 5, and 15 minutes.

## Model runtime

The model selector shows whether the currently selected Ollama model is active or idle by polling `/api/ps`.

## Context size

The context setting can run in automatic mode. The UI asks the server for a hardware-based recommendation using 95% of currently available GPU memory when a GPU is available, reserving the estimated model footprint. System RAM is used only when no GPU is detected or Ollama is running the model on the CPU. The recommendation is clamped to the model's maximum context length before being sent as `num_ctx`. Manual mode is still available when you want to choose a smaller value.

## Mobile layout

On narrow screens, the chat uses the full viewport and the settings/sidebar content moves into a slide-out panel. The app also includes a web app manifest and icon for mobile browser installation.

## Project structure

```text
server.py                  Small entrypoint
index.html                 Browser UI markup and module entry point
styles.css                 Browser UI styles
assets/js/app.js           Frontend startup and event binding
assets/js/api/             HTTP client boundary
assets/js/services/        Ollama, system, chat, and file workflows
assets/js/ui/              DOM rendering and control modules
assets/js/state.js         Shared client-side state and constants
assets/js/utils/           Formatting helpers
manifest.webmanifest       Mobile install metadata
icon.svg                   Mobile app icon
config.example.json        Example deploy config
ollama_console/config.py   CLI flags and defaults
ollama_console/handler.py  HTTP routes and UI serving
ollama_console/ollama.py   Ollama API proxying
ollama_console/server.py   Server startup
ollama_console/system_info.py Machine stats for the UI
```

## Run as a systemd service

Create `/etc/systemd/system/ollama-console.service`:

```ini
[Unit]
Description=Ollama Console
After=network.target ollama.service

[Service]
WorkingDirectory=/home/ollama/ollama-webinterface
ExecStart=/usr/bin/python3 /home/ollama/ollama-webinterface/server.py --config /home/ollama/ollama-webinterface/config.json
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then enable it:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now ollama-console
```

Check logs/status:

```sh
sudo systemctl status ollama-console --no-pager -l
sudo journalctl -u ollama-console -n 80 --no-pager
```

After pulling updates:

```sh
cd /home/ollama/ollama-webinterface
git pull
sudo systemctl restart ollama-console
```

## Security and TLS Best Practices

### HTTPS/TLS Configuration (Required for Production)

**Never deploy without HTTPS in production.** For any server exposed to external networks:

1. **Obtain an SSL/TLS certificate**:
   - Use [Let's Encrypt](https://letsencrypt.org/) for free certificates, or purchase from a trusted CA
   - Or use DNS-based certificates (ACME/DNS01) if your DNS provider supports it
   - For internal networks, consider an internal PKI with valid CRL/OCSP

2. **Configure reverse proxy for TLS termination** (recommended):
   ```bash
   # Nginx example
   nginx -c 'http {
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;
       server {
           listen 443 ssl http2;
           server_name your.domain.com;
           
           ssl_certificate     /path/to/fullchain.pem;
           ssl_certificate_key /path/to/privkey.pem;
           
           location / {
               proxy_pass http://127.0.0.1:8080;
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto $scheme;
           }
       }
   }'
   ```

3. **Hardening the Bearer token** (if HTTP required):
   - Set a strong random secret (min 32 characters, mix of letters/numbers/symbols)
   - Rotate tokens periodically (recommended every 90 days or on admin action)
   - Log all failed auth attempts and alert on anomalies
   - Use token expiration via custom header logic if supported

4. **Network isolation**:
   - Bind to internal interfaces only when appropriate (`host = "127.0.0.1"`)
   - Use firewall rules: `ufw allow 8080 from <trusted-network>`
   - Consider Docker/container network segregation
   - Deploy in a DMZ with strict egress rules

5. **Headers already implemented**:
   - The server includes `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and CORS headers
   - Content Security Policy can be added via reverse proxy if needed

### Authenticated Proxy Deployment

When placing behind a reverse proxy (Nginx, Apache, HAProxy):

```nginx
# Nginx example with authentication
server {
    listen 80;
    server_name your.domain.com;
    
    location / {
        # Reverse proxy auth (mod_auth_request module)
        auth_request /auth;
        
        # JWT/OAuth bearer verification via Lua or headers
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Authorization $http_authorization;
        
        # Rate limiting to prevent abuse
        limit_req zone=one burst=5 nodelay;
    }
}
```

### Security Audit Checklist

Before deploying to production:

- [ ] HTTPS enabled with valid certificate (TLSv1.2+, strong ciphers)
- [ ] Firewall configured to restrict access to trusted networks only
- [ ] Bearer token secret changed from default and stored securely
- [ ] Rate limiting active (`/api/*` routes protected)
- [ ] Log file location is not publicly writable
- [ ] Reverse proxy rate limits for upstream API (prevent denial of service)
- [ ] Sensitive fields redacted in logs (`password`, `auth_token`, etc.)
- [ ] CORS configured with strict origins only if public-facing

### Logging and Monitoring

Enable external log aggregation:

```ini
# Systemd example with journald forwarding
[Service]
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ollama-console

# Or to specific file in centralized location
Environment="OLLAMA_CONSOLE_LOG_FILE=/var/log/ollama-console.log"
```

Set up alerts for:
- Failed authentication attempts (`/api/*` 401 responses)
- Rate limit triggers (`X-RateLimit-Over` headers)
- Unusual traffic patterns or high connection counts
- Model API errors that might indicate upstream issues

### Additional Recommendations

- **Regular updates**: Pull changes with `git pull` and restart after testing in staging
- **Backup configuration**: Version control your `config.json` (do not commit secrets)
- **Health checks**: Monitor `/api/ps` for model availability, `/api/system` for hardware health
- **Resource monitoring**: Watch for Ollama resource exhaustion via system metrics

## Firewall

Allow TCP port `8080` from your trusted network only. If the server is public, use HTTPS with a reverse proxy and apply the security guidelines above.
