import html
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

OPTIONS_PATH = "/data/options.json"
BACKUP_PATH = "/share/webui-proxy.json"
NGINX_CONF_PATH = "/etc/nginx/nginx.conf"
HTML_PATH = "/app/html/index.html"
HTTPS_PORTS = {443, 8443, 8006}
DEFAULT_TARGETS = [
    {"name": "Мое устройство", "url": "192.168.1.10"},
    "192.168.1.10",
]


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


def _is_default_targets(targets):
    if not targets:
        return False
    if len(targets) != 1:
        return False
    return targets[0] in DEFAULT_TARGETS


def _load_targets():
    data = _load_json(OPTIONS_PATH) or {}
    targets = data.get("targets", []) or []
    restored = False
    if _is_default_targets(targets):
        targets = []
    if not targets:
        backup = _load_json(BACKUP_PATH) or {}
        targets = backup.get("targets", []) or []
        if targets:
            _write_json(OPTIONS_PATH, {"targets": targets})
            restored = True
    parsed_targets = []
    for item in targets:
        parsed = _parse_target(item)
        if parsed:
            parsed_targets.append(parsed)

    return parsed_targets, restored


def _update_supervisor_options(targets):
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        return
    base_url = os.getenv("SUPERVISOR_URL", "http://supervisor")
    payload = {
        "options": {
            "targets": [
                {"name": target.get("name", ""), "url": target.get("raw", "")}
                for target in targets
            ]
        }
    }
    try:
        req = urllib.request.Request(
            f"{base_url}/addons/self/options",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return


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
    referer_map = [
        "    map $http_referer $proxy_target {",
        "        default \"\";",
    ]
    referer_host_map = [
        "    map $http_referer $proxy_host {",
        "        default \"\";",
    ]
    for idx, target in enumerate(targets, start=1):
        referer_map.append(
            f"        ~*/proxy/{idx}/ {target['scheme']}://{target['host']}:{target['port']};"
        )
        referer_host_map.append(
            f"        ~*/proxy/{idx}/ {target['host']}:{target['port']};"
        )
    referer_map.append("    }")
    referer_host_map.append("    }")
    referer_map_block = "\n".join(referer_map + [""] + referer_host_map)
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
            proxy_hide_header X-Frame-Options;
            proxy_hide_header Content-Security-Policy;
            proxy_hide_header X-Content-Security-Policy;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_redirect ~^(https?://[^/]+)?(/.*)$ $http_x_ingress_path{prefix}$2;
            proxy_cookie_path / $http_x_ingress_path{prefix}/;
            sub_filter_once off;
            sub_filter_types text/html text/css application/javascript text/javascript application/x-javascript;
            sub_filter 'href="/' 'href="$http_x_ingress_path{prefix}/';
            sub_filter 'src="/' 'src="$http_x_ingress_path{prefix}/';
            sub_filter 'action="/' 'action="$http_x_ingress_path{prefix}/';
            sub_filter 'href=/' 'href=$http_x_ingress_path{prefix}/';
            sub_filter 'src=/' 'src=$http_x_ingress_path{prefix}/';
            sub_filter 'action=/' 'action=$http_x_ingress_path{prefix}/';
            sub_filter "href='/" "href='$http_x_ingress_path{prefix}/";
            sub_filter "src='/" "src='$http_x_ingress_path{prefix}/";
            sub_filter "action='/" "action='$http_x_ingress_path{prefix}/";
            sub_filter 'url("/' 'url("$http_x_ingress_path{prefix}/';
            sub_filter "url('/" "url('$http_x_ingress_path{prefix}/";
            sub_filter 'url(/' 'url($http_x_ingress_path{prefix}/';
            sub_filter '"/api/' '"$http_x_ingress_path{prefix}/api/';
            sub_filter "'/api/" "'$http_x_ingress_path{prefix}/api/";
            sub_filter '"/rpc/' '"$http_x_ingress_path{prefix}/rpc/';
            sub_filter "'/rpc/" "'$http_x_ingress_path{prefix}/rpc/";
            sub_filter '"/ws/' '"$http_x_ingress_path{prefix}/ws/';
            sub_filter "'/ws/" "'$http_x_ingress_path{prefix}/ws/";
            sub_filter '"/scripts/' '"$http_x_ingress_path{prefix}/scripts/';
            sub_filter "'/scripts/" "'$http_x_ingress_path{prefix}/scripts/";
            sub_filter '"/glyphicons-' '"$http_x_ingress_path{prefix}/glyphicons-';
            sub_filter "'/glyphicons-" "'$http_x_ingress_path{prefix}/glyphicons-";
            sub_filter 'http://{target['host']}:{target['port']}/' '$http_x_ingress_path{prefix}/';
            sub_filter 'https://{target['host']}:{target['port']}/' '$http_x_ingress_path{prefix}/';
            sub_filter '//{target['host']}:{target['port']}/' '$http_x_ingress_path{prefix}/';
            sub_filter 'http://{target['host']}/' '$http_x_ingress_path{prefix}/';
            sub_filter 'https://{target['host']}/' '$http_x_ingress_path{prefix}/';
            sub_filter '//{target['host']}/' '$http_x_ingress_path{prefix}/';
            sub_filter 'o.p="/' 'o.p="$http_x_ingress_path{prefix}/';
            sub_filter "o.p='/" "o.p='$http_x_ingress_path{prefix}/";
            sub_filter '__webpack_require__.p="/' '__webpack_require__.p="$http_x_ingress_path{prefix}/';
            sub_filter "__webpack_require__.p='/" "__webpack_require__.p='$http_x_ingress_path{prefix}/";
            sub_filter 'publicPath:"/' 'publicPath:"$http_x_ingress_path{prefix}/';
            sub_filter "publicPath:'/" "publicPath:'$http_x_ingress_path{prefix}/";
            sub_filter '<head>' '<head><base href="$http_x_ingress_path{prefix}/"><script>(function(){{var base="$http_x_ingress_path{prefix}/";window.__ingress_base=base;try{{if(!window.url){{window.url=function(){{return new URL(...arguments);}};}}if(window.URL){{window.url.prototype=window.URL.prototype;window.url.URL=window.URL;}}}}catch(e){{}}function fix(u){{try{{if(!u)return u;if(typeof u==="string"){{if(u.indexOf(base)===0)return u;if(u[0]==="/")return base+u.slice(1);var m=u.match(/^(https?:\/\/|wss?:\/\/)([^/]+)\/(.*)/);if(m&&m[2]===location.host){{return m[1]+m[2]+base+m[3];}}}}return u;}}catch(e){{return u;}}}}var _f=window.fetch;if(_f){{window.fetch=function(input,init){{return _f.call(this,fix(input),init);}};}}var _o=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,url){{return _o.apply(this,[method,fix(url)].concat([].slice.call(arguments,2)));}};var _ws=window.WebSocket;if(_ws){{window.WebSocket=function(url,protocols){{return protocols!==undefined?new _ws(fix(url),protocols):new _ws(fix(url));}};window.WebSocket.prototype=_ws.prototype;}}try{{var _set=Element.prototype.setAttribute;Element.prototype.setAttribute=function(name,value){{if(name==="src"||name==="href"){{return _set.call(this,name,fix(value));}}return _set.call(this,name,value);}};var sd=Object.getOwnPropertyDescriptor(HTMLScriptElement.prototype,"src");if(sd&&sd.set){{Object.defineProperty(HTMLScriptElement.prototype,"src",{{set:function(v){{return sd.set.call(this,fix(v));}},get:sd.get}});}}var ld=Object.getOwnPropertyDescriptor(HTMLLinkElement.prototype,"href");if(ld&&ld.set){{Object.defineProperty(HTMLLinkElement.prototype,"href",{{set:function(v){{return ld.set.call(this,fix(v));}},get:ld.get}});}}}}catch(e){{}}}})();</script>';
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

{referer_map_block}

    server {{
        listen 8080;
        server_name _;

        root /app/html;
        index index.html;

        location = / {{
            try_files /index.html =404;
        }}

        location /scripts/ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /glyphicons- {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /fontawesome- {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /fonts/ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location ~* \.(woff2?|ttf|eot|otf)$ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /rpc/ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /api/ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        location /ws/ {{
            if ($proxy_target = "") {{ return 404; }}
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_set_header Host $proxy_host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
            proxy_ssl_server_name on;
            proxy_ssl_verify off;
            proxy_pass $proxy_target;
        }}

        {''.join(locations)}
    }}
}}
"""


def main():
    targets, restored = _load_targets()
    _write_backup(targets)
    if restored:
        _update_supervisor_options(targets)

    os.makedirs(os.path.dirname(HTML_PATH), exist_ok=True)
    with open(HTML_PATH, "w", encoding="utf-8") as file:
        file.write(_render_index(targets))

    os.makedirs(os.path.dirname(NGINX_CONF_PATH), exist_ok=True)
    with open(NGINX_CONF_PATH, "w", encoding="utf-8") as file:
        file.write(_render_nginx_conf(targets))


if __name__ == "__main__":
    main()
