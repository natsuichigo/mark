# How It Works
One build, from a workflow run to a published, validated image.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Trigger</strong><span>A push to <code>dev</code> touching that OS's build files, or a manual run choosing the target (<code>aws</code>, <code>vmware</code> or <code>both</code>) and the environment (<code>dev</code> / <code>prd</code>)</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Resolve</strong><span>A small-runner job works out the image version and run parameters</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Build (AWS and vSphere in parallel)</strong><span>Large self-hosted runners run Packer; Ansible configures and hardens the image</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Validate inline</strong><span>The OS's validator runs as the last provisioner before clean-up. Any failure aborts the build</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Publish and tidy</strong><span>The AMI or template is published; old AMIs beyond the retention count are removed</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">6</div><div class="flow-text"><strong>Summarise</strong><span>A separate job merges both platforms' results into one run summary, even on failure</span></div></div>
</div>

## Validation Inside the Build

Each OS has a validator in `tests/`: `validate-rhel-image.sh`,
`validate-al2023-image.sh` and `validate-windows-image.ps1`. They print records in a
shared vocabulary that the summary action understands:

| Record | Example |
|---|---|
| Section header | `━━━ Operating System ━━━` or `--- Operating System ---` |
| Check | `PASS : SSM agent installed`, with `FAIL`, `WARN`, `SKIP` or `INFO` |
| Benchmark | `🔧 Disk write speed: …` |
| Summary | A closing block with `Passed:`, `Failed:` and `Warnings:` counts |

One summary parser handles every OS family, so adding an OS means emitting the same
records, not writing a new parser.

## Credentials and Security

- **AWS access through OIDC.** Workflows assume an IAM role; there are no stored
  AWS access keys.
- **The build account is ephemeral.** Its password passes through EC2 UserData, so it
  is treated as disposable and rotated freely.
- **Windows on AWS never ships the build password.** The final provisioner replaces it
  with a bootstrap password, if one is configured, or with a random 32-character
  password that is never recorded. Instances are reached through SSM Session Manager.
- **Nothing sensitive is committed.** Certificates, keys and passwords come in as
  `PKR_VAR_*` environment variables or secrets.

## Building Locally

Validation needs no cloud or vCenter connection:

```bash
packer init builds/aws/linux/rhel/8.10
packer fmt -check -recursive builds/
packer validate \
  -var-file=builds/aws/common.pkrvars.hcl \
  -var-file=builds/aws/linux/rhel/8.10/linux-rhel.pkrvars.hcl \
  -var image_version=20260101-test -var ami_name=rhel-8-10-test \
  builds/aws/linux/rhel/8.10
```
