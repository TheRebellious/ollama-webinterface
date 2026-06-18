# Ollama Console

A small web interface for an Ollama server running inside a Debian container. It uses only the Python standard library, so there are no frontend build tools or Python packages to install.

## Run

On the Debian container:

```sh
python3 server.py
```

Open:

```text
http://SERVER_IP:8080
```

By default the UI proxies Ollama at:

```text
http://127.0.0.1:11434
```

If Ollama is somewhere else:

```sh
OLLAMA_URL=http://127.0.0.1:11434 python3 server.py --host 0.0.0.0 --port 8080
```

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

The UI can attach text-based files to your next message. Files are read in your browser and included as prompt context; they are not uploaded to storage on the Python server.

Supported base types include:

```text
.txt, .md, .csv, .json, .jsonl, .log, .xml, .yaml, .yml,
.toml, .ini, .conf, .cfg, source code files, shell scripts, SQL,
Dockerfile, and .gitignore
```

Each file is limited to 1 MB so prompts do not accidentally exceed the model context window.

## Machine stats

The sidebar shows live machine stats from `/api/system`, including CPU, memory, disk usage, load average, uptime, and NVIDIA GPU usage when `nvidia-smi` is available. The UI refreshes this every 5 seconds.

## Project structure

```text
server.py                  Small entrypoint
index.html                 Browser UI
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
WorkingDirectory=/opt/ollama-console
Environment=OLLAMA_URL=http://127.0.0.1:11434
ExecStart=/usr/bin/python3 /opt/ollama-console/server.py --host 0.0.0.0 --port 8080
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

## Firewall

Allow TCP port `8080` from your trusted network only. If the server is public, put this behind a reverse proxy with authentication and HTTPS.
