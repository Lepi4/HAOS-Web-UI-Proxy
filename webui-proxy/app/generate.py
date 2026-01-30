import html
import json
import os
from urllib.parse import urlparse

OPTIONS_PATH = "/data/options.json"
BACKUP_PATH = "/share/webui-proxy.json"
NGINX_CONF_PATH = "/etc/nginx/nginx.conf"
HTML_PATH = "/app/html/index.html"
HTTPS_PORTS = {443, 8443, 8006}


def _load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _parse_target(raw):
    if isinstance(raw, dict):
        name = raw.get("name", "").strip()
        url = raw.get("url", "").strip()
    else:
        name = ""
        url = (raw or "").strip()

    if not url:
        return None

    scheme = "http"
    host = ""
    port = 80

    if "://" in url:
        parsed = urlparse(url)
        scheme = parsed.scheme or "http"
        host = parsed.hostname or ""
        port = parsed.port or (443 if scheme == "https" else 80)
    else:
        host_port = url.split("/", 1)[0]
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                return None
        else:
            host = host_port
        if port in HTTPS_PORTS:
            scheme = "https"

    host = host.strip()
    if not host:
        return None

    if not name:
        name = f"{host}:{port}"

    return {
        "name": name,
        "raw": url,
        "scheme": scheme,
        "host": host,
        "port": port,
    }


def _load_targets():
    data = _load_json(OPTIONS_PATH) or {}
    targets = data.get("targets", []) or []
    if not targets:
        backup = _load_json(BACKUP_PATH) or {}
        targets = backup.get("targets", []) or []
        if targets:
            _write_json(OPTIONS_PATH, {"targets": targets})
    parsed_targets = []
    for item in targets:
        parsed = _parse_target(item)
        if parsed:
            parsed_targets.append(parsed)

    return parsed_targets


def _write_backup(targets):
    if not targets:
        return
    payload = {
        "targets": [
            {
                "name": target.get("name", ""),
                "url": target.get("raw", ""),
            }
            for target in targets
        ]
    }
    _write_json(BACKUP_PATH, payload)


def _render_index(targets):
    if not targets:
        body = "<p>Добавьте устройства в настройках аддона.</p>"
    else:
        items = []
        for idx, target in enumerate(targets, start=1):
            label = target.get("name", f"{target['host']}:{target['port']}")
            items.append(
                f"<li><a href=\"proxy/{idx}/\">{html.escape(label)}</a></li>"
            )
        body = "<ul>" + "\n".join(items) + "</ul>"

    return f"""<!doctype html>
<html lang=\"ru\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Web UI Proxy</title>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 20px; }}
      ul {{ padding-left: 20px; }}
      a {{ text-decoration: none; }}
    </style>
  </head>
  <body>
    <h1>Web UI Proxy</h1>
    {body}
  </body>
</html>"""


def _render_nginx_conf(targets):
    locations = []
    for idx, target in enumerate(targets, start=1):
        proxy_pass = f"{target['scheme']}://{target['host']}:{target['port']}/"
        prefix = f"/proxy/{idx}"
        ssl_block = ""
        if target["scheme"] == "https":
            ssl_block = "\n            proxy_ssl_server_name on;\n            proxy_ssl_verify off;"
        locations.append(
            f"""
        location {prefix}/ {{
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host {target['host']}:{target['port']};
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-Prefix $http_x_ingress_path{prefix};
            proxy_set_header Accept-Encoding "";
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_redirect ~^(https?://[^/]+)?(/.*)$ $http_x_ingress_path{prefix}$2;
            proxy_cookie_path / $http_x_ingress_path{prefix}/;
            sub_filter_once off;
            sub_filter_types text/html text/css application/javascript application/json;
            sub_filter 'href="/' 'href="$http_x_ingress_path{prefix}/';
            sub_filter 'src="/' 'src="$http_x_ingress_path{prefix}/';
            sub_filter 'action="/' 'action="$http_x_ingress_path{prefix}/';
            sub_filter "href='/" "href='$http_x_ingress_path{prefix}/";
            sub_filter "src='/" "src='$http_x_ingress_path{prefix}/";
            sub_filter "action='/" "action='$http_x_ingress_path{prefix}/";
            sub_filter 'url("/' 'url("$http_x_ingress_path{prefix}/';
            sub_filter "url('/" "url('$http_x_ingress_path{prefix}/";
            sub_filter '"/api/' '"$http_x_ingress_path{prefix}/api/';
            sub_filter "'/api/" "'$http_x_ingress_path{prefix}/api/";
            sub_filter '<head>' '<head><base href="$http_x_ingress_path{prefix}/">';
            {ssl_block}
            rewrite ^{prefix}/(.*)$ /$1 break;
            proxy_pass {proxy_pass};
        }}
            """
        )

    return f"""worker_processes 1;

pid /run/nginx/nginx.pid;

error_log /var/log/nginx/error.log warn;

events {{
    worker_connections 1024;
}}

http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    sendfile on;
    keepalive_timeout 65;

    map $http_upgrade $connection_upgrade {{
        default upgrade;
        '' close;
    }}

    server {{
        listen 8080;
        server_name _;

        root /app/html;
        index index.html;

        location = / {{
            try_files /index.html =404;
        }}

        {''.join(locations)}
    }}
}}
"""


def main():
    targets = _load_targets()
    _write_backup(targets)

    os.makedirs(os.path.dirname(HTML_PATH), exist_ok=True)
    with open(HTML_PATH, "w", encoding="utf-8") as file:
        file.write(_render_index(targets))

    os.makedirs(os.path.dirname(NGINX_CONF_PATH), exist_ok=True)
    with open(NGINX_CONF_PATH, "w", encoding="utf-8") as file:
        file.write(_render_nginx_conf(targets))


if __name__ == "__main__":
    main()
