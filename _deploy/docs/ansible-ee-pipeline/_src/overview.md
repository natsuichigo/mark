# Overview
Build, test and promote Ansible Execution Environments for AAP, AWX and ansible-navigator, trimmed for my home lab.

An **Execution Environment (EE)** is the container image Ansible Automation
Platform runs every job inside: ansible-core, Python, collections and tools, all
pinned together. If that image changes underneath a production job, automation
breaks in ways that are hard to trace. This project treats EEs like any other
release artefact: built in CI, tested against real target systems, soaked in dev,
then promoted to prod **without being rebuilt**.

<div class="callout">
<p><strong>The core idea.</strong> Production runs exactly the image that was tested. Promotion copies the tested image by tag into the prod repository, behind an approval gate, instead of building it again.</p>
</div>

<div class="callout warn">
<p><strong>This is the home-lab edition.</strong> The pipeline was built for an estate that included AWS. The lab has no AWS (it costs money I'm not spending yet), so I switched the AWS content off and kept it as a reference: the <code>amazon.aws</code> and <code>community.aws</code> collections, the AWS CLI, the SSM plugin and the Amazon Linux 2023 test target are commented out with <code>#AWS#</code> markers rather than deleted. The fuller organization version is kept separately. Finished images are copied into the container registry inside my <a href="../platform-lab/index.html">Platform Lab</a> cluster, where AWX pulls them.</p>
</div>

## What It Builds

| EE | Runtime | Tested against |
|---|---|---|
| Base, latest | Fedora 42, Python 3.13, ansible-core 2.18 | AlmaLinux 9, Ubuntu 22.04 |
| Base, compat | Fedora 40, Python 3.12, ansible-core 2.16 | AlmaLinux 8 |
| Derived | Built on top of each base | Its own validation playbook |

The compat track exists because ansible-core 2.16 is the last series that can manage
**Python 3.6** hosts, which is RHEL 8's platform Python.

- **Base EEs** hold general-purpose collections from public Galaxy (posix, windows,
  VMware, Kubernetes, community.\*), plus Helm.
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
    <span class="badge badge-amber">GitHub-hosted runners</span>
</div>

## Repository

The code is at [natsuichigo/ansible-execution-image-pipeline](https://github.com/natsuichigo/ansible-execution-image-pipeline).
