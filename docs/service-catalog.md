# Service catalog

| Service | Profile | Purpose | State path |
| --- | --- | --- | --- |
| Caddy | core | one private HTTP entry point | none |
| Homarr | core | dashboard and bounded container controls | `data/homarr` |
| socket proxy | core | restricted Docker API boundary | none |
| Prometheus | observability | metrics and rule evaluation | `data/prometheus` |
| Grafana | observability | provisioned visualization | `data/grafana` |
| node exporter | observability | Linux host metrics | none |
| cAdvisor | observability | container metrics | none |
| blackbox exporter | observability | HTTP and DNS probes | none |
| Loki | observability-full | bounded log storage | `data/loki` |
| Alloy | observability-full | Docker log collection | none |
| Pi-hole | network-lab | isolated DNS filtering experiment | `data/pihole` |
| Open WebUI | ai | offline local-model UI and knowledge surface | `data/open-webui` |
| MLflow | ai | experiment and artifact tracking | `data/mlflow` |
| Syncthing | knowledge | approved-folder synchronization | `data/syncthing` |
| Paperless-ngx | knowledge | OCR document archive | `data/paperless` |

Image versions are pinned in Compose. Updates are reviewed changes; there is no
runtime auto-updater. `renovate.json` defines a review-oriented dependency
update policy, but no Renovate installation or schedule is assumed.
