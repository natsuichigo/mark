# Lessons & Next Steps
Decisions made so far, and the roadmap.

## Decisions So Far

- **Traefik instead of ingress-nginx.** The architecture first named ingress-nginx,
  but that project was retired in March 2026 and no longer receives security fixes.
  Sprint 1 uses Traefik instead, with the Ingress API for now; Gateway API is the
  recommended direction for new designs and will be evaluated in a later sprint.
- **Podman as the kind provider.** It keeps the lab free of a Windows-side container
  runtime. The trade-off is rootless networking, which can need extra host
  capabilities when the cluster or ingress misbehaves.
- **Local-only by default.** `.localhost` names and a loopback-bound port-forward keep
  everything on the machine. Nothing is exposed until there is a reason to.
- **Capacity before features.** Backstage, AWX, Jenkins, n8n and the full
  Prometheus/Grafana/Loki stack wait until the lab has the resources. A single node
  that runs well beats a crowded one that doesn't.

## Roadmap

| Sprint | Goal | Status |
|---|---|---|
| Sprint 0 | Workstation tooling, repository structure, GitHub metadata | Done |
| Sprint 1 | kind cluster, Helm, ingress, Metrics Server, a sample app, CKAD labs | In progress |
| Sprint 2 | Argo CD with its UI on a local Traefik route; manage an app from Git | Next |
| Later | cert-manager, lightweight observability, Headlamp; then Backstage, AWX, Jenkins, n8n as capacity allows; Terraform and a Packer image factory | Planned |

## Goals Behind It

The lab supports working towards the **CKAD**, **CKA** and an **AWS Associate**
certification, and it gives the other projects on this site a place to run: the
[Packer pipeline](../packer-image-pipeline/index.html) and the
[Ansible EE pipeline](../ansible-ee-pipeline/index.html) both have homes in its
`images/` folder.
