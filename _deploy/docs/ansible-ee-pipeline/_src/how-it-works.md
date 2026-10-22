# How It Works
What happens between a push to dev and an image AAP can run.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Push to <code>dev</code></strong><span>Touching <code>execution-environments/**</code>, the workflow or the shared actions</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Build the two bases</strong><span><code>ansible-builder</code> builds core 2.18 and core 2.16 from their definitions</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Validate and target-test</strong><span><code>ansible-navigator</code> runs each validation playbook, then target tests against real OS containers</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Build the derived EEs</strong><span>One per base, with certified collections from Automation Hub, then validated</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Push to dev</strong><span>Only images that passed every check, with version and SHA tags; a run summary lists them</span></div></div>
</div>

## Validation Before Anything Is Pushed

| EE | Check | What it proves |
|---|---|---|
| Base 2.18 / 2.16 | `validation.yml` via `ansible-navigator` | ansible-core version, collections, AWS CLI, Helm, SSM plugin |
| Base 2.18 | `latest-target-test.yml` | firewalld, systemd, sysctl and boto3 work against AlmaLinux 9 and Ubuntu 22.04 |
| Base 2.16 | `compat-target-test.yml` | The same against AlmaLinux 8 (Python 3.6) and Amazon Linux 2023 |
| Derived | `derived/validation.yml` | ansible, collections, `ansible.platform`, AWS CLI |

The target tests run **inside** the EE and reach the target containers through the
`community.docker.docker_api` connection plugin over the mounted Docker socket, so
no SSH is involved.

## Keeping the Automation Hub Token Out of the Image

Certified collections need an Automation Hub token at build time, and that token
must not end up in a pushed image.

- The build action exports the hub settings as `ANSIBLE_GALAXY_SERVER_*`
  environment variables and passes them as `--build-arg NAME`, so Docker reads the
  value from the environment and the token never appears on a command line.
- The EE definitions declare those build arguments only in an intermediate
  **galaxy** stage. The pushed image is built from a different stage and holds no
  token.

## Trusting a Corporate CA

Runners behind a TLS-inspecting proxy need its CA. A `CUSTOM_CA_BUNDLE` secret, or
committed certificate files, are added to the system trust store in the image's
first build stage, before any `dnf` or `ansible-galaxy` download, so the final image
and the target test containers trust them too.
