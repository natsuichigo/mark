# How It Works
One build, from a workflow run to a published, validated vSphere template.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Trigger</strong><span>A push to <code>dev</code> touching that OS's build files, or a manual run choosing the environment (<code>dev</code> / <code>prd</code>) and how many templates to keep</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Resolve</strong><span>A small job works out the image version and run parameters, and rejects bad values before Packer starts</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Build</strong><span>A runner pod in the Platform Lab cluster runs Packer against vCenter; Ansible configures and hardens the VM</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Validate inline</strong><span>The OS's validator runs as the last provisioner before clean-up. Any failure aborts the build</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Publish and tidy</strong><span>The template goes to the content library; <code>govc</code> removes versions beyond the retention count</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">6</div><div class="flow-text"><strong>Summarise</strong><span>A separate job publishes the run summary, even on failure</span></div></div>
</div>

Runs of one workflow on one branch never overlap: `concurrency` queues them, with
`cancel-in-progress: false`, because cancelling mid-build would leave an orphaned VM
behind in vSphere.

## Validation Inside the Build

Each OS has a validator in `tests/`: `validate-rhel-image.sh` and
`validate-windows-image.ps1`. They print records in a shared vocabulary that the
summary action understands:

| Record | Example |
|---|---|
| Section header | `━━━ Operating System ━━━` or `--- Operating System ---` |
| Check | `PASS : Password max days <= 365`, with `FAIL`, `WARN`, `SKIP` or `INFO` |
| Benchmark | `🔧 Disk write speed: …` |
| Summary | A closing block with `Passed:`, `Failed:` and `Warnings:` counts |

One summary parser handles every OS family, so adding an OS means emitting the same
records, not writing a new parser.

## Running on the Lab's Runners

The repo's runner labels are variables, so moving the builds into the lab needed no
workflow changes:

```text
RUNNER_LABELS_SMALL = ["platform-lab-packer"]
RUNNER_LABELS_LARGE = ["platform-lab-packer"]
```

The scale set has a maximum of two pods, so a build and its small resolve and summary
jobs can overlap, and zero pods while idle. Each pod installs its tools at the start of the job:
Packer and `govc` at pinned versions (1.16.0 and v0.56.0), then the plugins and ansible-core.

## Credentials and Security

- **Nothing sensitive is committed.** vCenter, build-account and Red Hat subscription
  credentials come in as GitHub secrets and reach Packer as `PKR_VAR_*` environment
  variables.
- **The build account is ephemeral** and rotated freely.
- **Known limitation, Windows on vSphere:** Packer shuts the VM down over WinRM as
  Administrator, so the template still carries the build password on that account. It
  is reset at deployment, in the vSphere customization spec.
- **The runner pods can't touch the cluster.** They run under a ServiceAccount with no
  permissions and no mounted token.

## Building Locally

Validation needs no vCenter connection:

```bash
packer init builds/vmware/linux/rhel/8.10
packer fmt -check -recursive builds/
packer validate \
  -var-file=builds/vmware/vsphere.pkrvars.hcl \
  -var-file=builds/vmware/common.pkrvars.hcl \
  -var-file=builds/vmware/linux-storage.pkrvars.hcl \
  -var-file=builds/vmware/linux/rhel/8.10/linux-rhel.pkrvars.hcl \
  -var image_version=20260101-test \
  builds/vmware/linux/rhel/8.10
```
