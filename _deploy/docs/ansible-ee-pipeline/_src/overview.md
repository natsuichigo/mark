# Overview
Build, test and promote Ansible Execution Environments for AAP, AWX and ansible-navigator.

An **Execution Environment (EE)** is the container image Ansible Automation
Platform runs every job inside: ansible-core, Python, collections and tools, all
pinned together. If that image changes underneath a production job, automation
breaks in ways that are hard to trace. This project treats EEs like any other
release artefact: built in CI, tested against real target systems, soaked in dev,
then promoted to prod **without being rebuilt**.

<div class="callout">
<p><strong>The core idea.</strong> Production runs exactly the image that was tested. Promotion copies the tested image by tag into the prod repository, behind an approval gate, instead of building it again.</p>
</div>

## What It Builds

| EE | Runtime | Tested against |
|---|---|---|
| Base, latest | Fedora 42, Python 3.13, ansible-core 2.18 | AlmaLinux 9, Ubuntu 22.04 |
| Base, compat | Fedora 40, Python 3.12, ansible-core 2.16 | AlmaLinux 8, Amazon Linux 2023 |
| Derived | Built on top of each base | Its own validation playbook |

The compat track exists because ansible-core 2.16 is the last series that can manage
**Python 3.6** hosts, which is RHEL 8's platform Python.

- **Base EEs** hold general-purpose collections from public Galaxy (posix, windows,
  AWS, VMware, Kubernetes, community.\*), plus the AWS CLI, Helm and the SSM plugin.
- **The derived EE** adds the AAP collections (`ansible.platform`,
  `ansible.controller`, `ansible.eda`), `redhat.*` and the `infra.*`
  configuration-as-code collections, most of them certified content from
  Automation Hub.

## The Stack

<div class="badge-row">
    <span class="badge badge-blue">ansible-builder</span>
    <span class="badge badge-green">ansible-navigator</span>
    <span class="badge badge-amber">GitHub Actions</span>
    <span class="badge badge-blue">Container registry</span>
    <span class="badge badge-green">AAP / AWX</span>
</div>

## Repository

The code is at [natsuichigo/ansible-execution-image-pipeline](https://github.com/natsuichigo/ansible-execution-image-pipeline).
