# Roadmap

## Hardware gate

After a dedicated server is physically present: record real inventory, select
storage from actual devices, install Proxmox, create a Debian service VM, apply
the existing Ansible roles, migrate Compose state, and prove each service. Only
then does the README tagline change from “building” to “got.”

## Candidates that require real need

- independent secondary DNS before router-wide filtering;
- HAOS VM and actual sensors using MQTT;
- VLANs based on a known router/firewall;
- UPS, power, temperature, humidity, and air-quality telemetry;
- GPU-specific inference serving and measured model selection;
- isolated security VMs and controlled network capture;
- local camera inference only after camera hardware and retention policy exist;
- household inventory, media, photo, or recipe tools only if they solve a real use.

## Kubernetes gate

Reconsider k3s when multiple always-on nodes, scheduling, rolling replacement,
Kubernetes APIs, or an intentional accepted learning target makes the cost
worthwhile. Preserve a small Compose emergency bundle even then.
