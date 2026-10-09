# Pool & Spa family app

A deliberately small Home Assistant OS app. Family UI exposes only pool and spa ON/OFF/setpoints, jets, spillway and slide. All commands use Home Assistant service calls; no direct Pentair connection or automation authority.

The app uses Supervisor's server-side API token via homeassistant_api and a household PIN stored in app options. Configure a nonempty PIN before use. Port 8101 is LAN-only; never forward it to the internet. The PIN protects application commands but is not a replacement for HTTPS or network isolation.

## Installation

Add this repository to Home Assistant App store, install Pool & Spa Family, set a PIN in app configuration, and start. Open http://<HA-host>:8101 in Safari. Current first slice has a manifest but no install icon or service worker; PWA packaging and security hardening must be completed before production commissioning.

## Safety

Grid outage protection, physical interlocks, and automation ownership remain in Home Assistant and the native IntelliCenter bridge. The backend only allows five predefined controls and bounded climate setpoints. Read-only polling reconciles externally initiated changes. No command on load/reconnect.
