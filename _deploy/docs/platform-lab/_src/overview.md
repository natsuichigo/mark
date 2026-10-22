# Overview
A home platform built sprint by sprint and run like production. Work in progress.

Platform Lab is one repository for building a reusable home platform: a local
Kubernetes platform, the automation around it, and eventually Terraform-managed
infrastructure and an image factory. It is also how I practise for the
Kubernetes certifications, so each sprint ends with something running that I can
work against.

<div class="callout">
<p><strong>Status: in progress.</strong> Sprint 0 (workstation and repository) is done. Sprint 1, the first Kubernetes platform, is underway. Later sprints are on the <a href="./lessons.html">roadmap</a>.</p>
</div>

## Principles

- **One product.** Everything belongs in the `platform-lab` repository, so the work
  doesn't fragment across many small repos.
- **Every commit contributes to the platform.** No throwaway tutorials.
- **Capacity first.** Heavy services wait until the lab has the resources to run
  them properly.

## The Stack

<div class="badge-row">
    <span class="badge badge-blue">Kubernetes (kind)</span>
    <span class="badge badge-green">Helm</span>
    <span class="badge badge-amber">Traefik</span>
    <span class="badge badge-blue">Podman</span>
    <span class="badge badge-green">Fedora 44 / WSL 2</span>
</div>

| Area | Today | Planned |
|---|---|---|
| Workstation | Fedora 44 on WSL 2 or native, VS Code, Podman | — |
| Kubernetes | kind (single node), kubectl, Helm, k9s | Argo CD for GitOps |
| Ingress | Traefik | Gateway API, evaluated later |
| Metrics | Metrics Server | A lightweight observability stack |
| Automation | Ansible, GitHub Actions | AWX, Jenkins, n8n |
| Infrastructure | — | Terraform, a Packer image factory |

## Repository

The code is at [natsuichigo/platform-lab](https://github.com/natsuichigo/platform-lab).
