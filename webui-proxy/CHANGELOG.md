# Changelog

## 0.1.14

- Add referer-based fallback proxy routes for absolute asset/API paths.

## 0.1.15

- Inject global url variable for UIs relying on it.

## 0.1.16

- Provide url constructor alias for legacy UI code.

## 0.1.17

- Sync restored targets back to Home Assistant options UI.

## 0.1.18

- Add url constructor shim for legacy frontends.

## 0.1.19

- Inject runtime URL rewrites for absolute paths and WebSocket.

## 0.1.20

- Fix nginx config parsing for injected runtime script.

## 0.1.21

- Rewrite unquoted URLs and webpack publicPath for chunks/assets.

## 0.1.22

- Rewrite DOM src/href assignments for scripts and links.

## 0.1.23

- Add fallback proxy routes for font assets.

## 0.1.24

- Add generic font extension fallback proxy.

## 0.1.13

- Rewrite unquoted /scripts and /glyphicons paths.

## 0.1.12

- Rewrite /scripts and glyphicon asset paths for Wirenboard UI.

## 0.1.11

- Rewrite webpack public path (o.p) to Ingress prefix.

## 0.1.10

- Hide frame-blocking headers for embedded UIs.
- Rewrite /rpc and /ws paths for SPA backends.

## 0.1.9

- Restore targets when only default placeholder is present.
- Rewrite absolute URLs with host to Ingress path.

## 0.1.8

- Restore targets from /share into options when empty.
- Inject base href to improve SPA rendering.

## 0.1.7

- Use ingress path in rewritten URLs, cookies, and redirects.
- Do not overwrite backup when targets are empty.

## 0.1.6

- Improve path rewriting for JS/CSS and single-quoted URLs.
- Add API path rewrites for absolute /api/ calls.

## 0.1.5

- Backup targets to /share/webui-proxy.json and restore if options are empty.

## 0.1.4

- Fix absolute paths behind Ingress (sub_filter + cookie path).
- Preserve target host with port in `Host` header.

## 0.1.3

- Auto-detect HTTPS for common ports (443/8443/8006).
- Improved label rendering consistency.

## 0.1.2

- Added support for custom device names.
- Targets can now be specified as objects with "name" and "url" fields.
- Backward compatible with simple string targets.

## 0.1.1

- Fixed proxy redirect for Ingress compatibility.
- Removed sub_filter approach for better compatibility.
- Updated repository URL.

## 0.1.0

- Initial release.
