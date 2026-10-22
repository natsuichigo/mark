# Overview
Hardened golden images for AWS and vSphere, built by Packer and Ansible and validated inside the build.

Every server should start from a known, hardened, tested image rather than being
configured by hand after it boots. This project builds those **golden images**
with HashiCorp Packer, configures and hardens them with Ansible, and runs the whole
thing from GitHub Actions, for two platforms: **AWS** (AMIs) and **VMware vSphere**
(content-library templates).

<div class="callout">
<p><strong>The rule the whole pipeline is built around.</strong> Validation runs <em>inside</em> the build, as the last provisioner before clean-up. A failed check fails the build, so no AMI or template is ever published from a bad run.</p>
</div>

## What It Builds

| OS | AWS | vSphere | Hardening |
|---|---|---|---|
| RHEL 8.10 | Two-stage (`amazon-ebssurrogate` → `amazon-ebs`) | Kickstart ISO build | CIS (`rhel_cis` role) |
| Amazon Linux 2023 (x86_64 + arm64) | Two-stage | — | CIS (`aml23_cis` role) |
| Windows Server 2022 | Single stage | Autounattend ISO build | Baseline; CIS arrives by GPO after domain join |

## The Stack

<div class="badge-row">
    <span class="badge badge-blue">Packer</span>
    <span class="badge badge-green">Ansible</span>
    <span class="badge badge-amber">GitHub Actions</span>
    <span class="badge badge-blue">AWS</span>
    <span class="badge badge-green">VMware vSphere</span>
</div>

| Area | Tools |
|---|---|
| Image builds | Packer: `amazon-ebssurrogate`, `amazon-ebs`, `vsphere-iso` |
| Configuration and hardening | Ansible roles: `base`, `configure`, `clean`, `rhel_cis`, `aml23_cis`, `software_collections` |
| Validation | Bash validators for Linux, PowerShell for Windows, under `tests/` |
| CI/CD | GitHub Actions workflows plus composite actions, on self-hosted runners |
| Cloud access | GitHub OIDC to an AWS IAM role: no long-lived AWS keys |

## Repository

The code is at [natsuichigo/packer-image-pipeline](https://github.com/natsuichigo/packer-image-pipeline).
The build standards in `docs/standards/` define the conventions every build follows:
block order, naming, credentials, tags, pipeline shape and validation.
