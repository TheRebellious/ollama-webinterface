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
  "upload_max_mb": 10
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

The sidebar shows live machine stats from `/api/system`, including CPU, memory, disk usage, load average, uptime, and NVIDIA GPU usage when `nvidia-smi` is available. The UI refreshes this every 5 seconds.

## Model runtime

The model selector shows whether the currently selected Ollama model is active or idle by polling `/api/ps`.

## Mobile layout

On narrow screens, the chat uses the full viewport and the settings/sidebar content moves into a slide-out panel. The app also includes a web app manifest and icon for mobile browser installation.

## Project structure

```text
server.py                  Small entrypoint
index.html                 Browser UI
styles.css                 Browser UI styles
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

## Firewall

Allow TCP port `8080` from your trusted network only. If the server is public, put this behind a reverse proxy with authentication and HTTPS.
