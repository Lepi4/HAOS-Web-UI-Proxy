# Changelog

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
