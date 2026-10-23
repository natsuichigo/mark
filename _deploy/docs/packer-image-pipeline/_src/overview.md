# Overview
Hardened vSphere golden images, built by Packer and Ansible, validated inside the build, and run from my home lab.

Every server should start from a known, hardened, tested image rather than being
configured by hand after it boots. This project builds those **golden images**
with HashiCorp Packer, configures and hardens them with Ansible, and runs the whole
thing from GitHub Actions. The result is a **VMware vSphere** content-library template.

<div class="callout">
<p><strong>The rule the whole pipeline is built around.</strong> Validation runs <em>inside</em> the build, as the last provisioner before clean-up. A failed check fails the build, so no template is ever published from a bad run.</p>
</div>

<div class="callout warn">
<p><strong>This is the home-lab edition.</strong> The pipeline started life building for AWS and vSphere. For the lab I switched the AWS side off, because running AWS builds costs money I'm not spending yet. The AWS code stays in the repo as a reference: its jobs and steps are commented out with <code>#AWS#</code> markers rather than deleted, and the Amazon Linux 2023 workflow is disabled. The fuller organization version is kept separately. Here, the builds run on runners inside my <a href="../platform-lab/index.html">Platform Lab</a> cluster.</p>
</div>

## What It Builds

| OS | vSphere build | Hardening |
|---|---|---|
| RHEL 8.10 | `vsphere-iso` from the install ISO, kickstart delivered on a CD | CIS (`rhel_cis` role) |
| Windows Server 2022 | `vsphere-iso` from the install ISO, autounattend delivered on a CD | Baseline; CIS arrives by GPO after domain join |

The AWS builds (RHEL and Amazon Linux 2023 AMIs, Windows Server 2022) are still in
`builds/aws/` as a reference, switched off until building on AWS is worth the cost.

## The Stack

<div class="badge-row">
    <span class="badge badge-blue">Packer</span>
    <span class="badge badge-green">Ansible</span>
    <span class="badge badge-amber">GitHub Actions</span>
    <span class="badge badge-green">VMware vSphere</span>
    <span class="badge badge-blue">Actions Runner Controller</span>
</div>

| Area | Tools |
|---|---|
| Image builds | Packer `vsphere-iso`, publishing to a vSphere content library |
| Configuration and hardening | Ansible roles: `base`, `configure`, `clean`, `rhel_cis`, `software_collections` |
| Validation | A Bash validator for Linux, PowerShell for Windows, under `tests/` |
| CI/CD | GitHub Actions workflows plus composite actions |
| Runners | Ephemeral pods in the Platform Lab cluster (scale set `platform-lab-packer`), started only while a job runs |
| Retention | `govc` removes templates beyond the retention count |

## Repository

The code is at [natsuichigo/packer-image-pipeline](https://github.com/natsuichigo/packer-image-pipeline).
The build standards in `docs/standards/` define the conventions every build follows:
block order, naming, credentials, tags, pipeline shape and validation.
