# Overview
A full platform stack on an 8 GB laptop, deployed from Git by Argo CD. Work in progress.

Platform Lab is one repository for a real home platform: a Kubernetes cluster that
**Argo CD deploys entirely from Git**, with GitHub Actions runners inside the cluster.
The challenge is to run the tools a platform team actually uses (GitOps, ingress,
CI runners, a container registry, Prometheus and Grafana, AWX, Backstage, and a KVM
hypervisor for VM images) on one 8 GB laptop, with no cloud bill. It is also how I practise for the Kubernetes certifications: the cluster I
study on is the platform itself.

<div class="callout">
<p><strong>Status: in progress.</strong> The kind cluster and Argo CD are running and syncing from GitHub through a GitHub App, after a DNS search-domain clash that broke TLS to GitHub was found and fixed. The core platform (Traefik, Metrics Server, RBAC and the Headlamp cluster UI) deploys from Git, and every UI opens with no port-forward. In-cluster runners for this repo and the Packer pipeline are next, then hardening. See the <a href="./lessons.html">roadmap and problems log</a>.</p>
</div>

## Principles

- **Git is the source of truth.** After a one-script bootstrap, nothing is installed
  by hand. Changing the platform means opening a commit, and rolling back means
  `git revert`.
- **No throwaway tutorials.** No sample apps in sprint namespaces: every component
  is a real part of the platform.
- **Capacity first.** An always-on core plus one heavy profile at a time, each with
  explicit requests and limits.
- **Secrets never go in Git.**
- **Built by hand first.** Every step is in a written guide with no scripts: what
  to do, why, and how to check it worked. The bootstrap scripts exist, but only as a
  shortcut once the manual path is understood.
- **Every security control is tested.** A control without a test that proves it
  blocks something doesn't count.

## The Stack

<div class="badge-row">
    <span class="badge badge-blue">Kubernetes (kind)</span>
    <span class="badge badge-green">Argo CD</span>
    <span class="badge badge-amber">Traefik</span>
    <span class="badge badge-blue">Actions Runner Controller</span>
    <span class="badge badge-green">Headlamp</span>
    <span class="badge badge-amber">zot</span>
    <span class="badge badge-blue">KVM / libvirt</span>
    <span class="badge badge-green">Vagrant</span>
    <span class="badge badge-green">Helm</span>
    <span class="badge badge-amber">Podman</span>
    <span class="badge badge-blue">Fedora 44 / WSL 2</span>
</div>

| Area | Today | Next |
|---|---|---|
| Workstation | Fedora 44 on WSL 2, VS Code, Podman | — |
| Cluster | kind (single node), kubectl, Helm, k9s | — |
| Delivery | Argo CD app-of-apps from Git | Sealed Secrets |
| Ingress | Traefik on `*.platform-lab.localhost:8080`, published by kind on loopback | cert-manager, Gateway API |
| Cluster UI | Headlamp, token sign-in | — |
| Registry | zot in the cluster, one image name from WSL and from pods | Authentication |
| VM images | Packer `qemu` on KVM inside WSL, Vagrant + libvirt | The Packer pipeline's RHEL and Windows builds on `qemu` |
| CI | GitHub Actions runners in the cluster (ARC), one scale set per repo | More repos, more in-cluster jobs |
| Observability | Metrics Server | Prometheus + Grafana, then Loki |
| Automation | Ansible, GitHub Actions | AWX, Jenkins, n8n |
| Security | RBAC, local-only access, secrets kept out of Git | Pod Security `restricted`, NetworkPolicy, SHA-pinned actions, Sealed Secrets |
| Developer portal | — | Backstage, built from my own app |
| Infrastructure | Packer builds for vSphere run on the lab's runners | Terraform; AWS once it's worth the cost |

## Repository

The code is at [natsuichigo/platform-lab](https://github.com/natsuichigo/platform-lab).
