# Architecture
One laptop, one node, and Git deciding what runs on it.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Workstation</strong><span>Fedora 44 on WSL 2, VS Code, Podman, kind, kubectl, Helm, k9s; QEMU/KVM, libvirt and Vagrant for VM images</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Cluster</strong><span>A single kind node on Podman, created by <code>bootstrap/cluster-up.sh</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>GitOps</strong><span>Argo CD, the only hand-installed chart, syncs everything in <code>kubernetes/argocd/apps/</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Platform</strong><span>Tailscale operator, Metrics Server, Headlamp, a container registry, GitHub runners; profiles for Prometheus/Grafana, AWX and Backstage</span></div></div>
</div>

## The GitOps Flow

A single root Application points at a folder of child Applications (the
*app-of-apps* pattern). Each child pulls a pinned chart from upstream and its values
from this repo. Sync waves bring the platform up in order:

<div class="flow">
<div class="flow-step"><div class="flow-num">0</div><div class="flow-text"><strong>Wave 0</strong><span>Metrics Server, platform-config (namespaces, quotas, RBAC)</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Wave 1</strong><span>Tailscale operator, Headlamp (the cluster UI), the lab registry</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Wave 2</strong><span>The tailnet Ingresses: one private HTTPS name per UI</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Wave 3</strong><span>Whichever heavy profile is switched on, bringing its own tailnet Ingress</span></div></div>
</div>

## Runners Inside the Cluster

A workflow job with `runs-on: platform-lab` is picked up by the ARC listener, which
long-polls GitHub over outbound HTTPS. The controller then starts an ephemeral runner
pod, which runs the job and is deleted. Because the connection is outbound only, it
works from behind WSL's NAT, and with a minimum of zero runners nothing runs while idle.
The runner pod's ServiceAccount has the read-only `view` role.

My GitHub account is personal, not an organization, and GitHub only lets a personal
account register runners **per repository**. So each repo that uses the lab gets its
own scale set: one Argo CD Application and one values file, sharing the same GitHub App.
The [Packer pipeline](../packer-image-pipeline/index.html) has its own set,
`platform-lab-packer`, whose pods get no Kubernetes API rights at all.

## Where Each Kind of Job Runs

| Job | Runs on | Why |
|---|---|---|
| Packer image builds | In-cluster runners (`platform-lab-packer`) | Packer drives vSphere remotely, so the pod only makes outbound connections and needs no KVM or Docker |
| Ansible EE and Backstage image builds | GitHub-hosted runners, pushing to a registry | Container builds would need privileged Docker-in-Docker pods |
| Platform health checks, Ansible against the lab | In-cluster runners | They need to reach the cluster |
| Terraform for the lab and GitHub settings | In-cluster runners, apply behind an approval | Close to the cluster, and a required reviewer gates every apply |

Rule of thumb: **container builds run on GitHub's machines, and jobs that drive
something in the lab (the cluster, or vSphere for Packer) run on my runners**, so
runner pods never need privileged mode.

## Reaching the UIs

Every UI is private to my tailnet, the WireGuard network
[Tailscale](https://tailscale.com/) builds between my own devices. Each UI has an
Ingress with `ingressClassName: tailscale`. The Tailscale operator turns each one into
its own tailnet machine (`argocd`, `headlamp`, `registry`, and `grafana`, `awx` or
`backstage` when that profile is on) with a MagicDNS name and a real Let's Encrypt
certificate. HTTPS ends at a small proxy pod, which forwards plain HTTP to the Service
inside the cluster.

<pre class="dir-tree">
phone / laptop ─► WireGuard ─► proxy pod "argocd" ─► Service argocd-server
<span class="cm"># Tailscale on      # tailnet      # HTTPS ends here     # plain HTTP inside the cluster</span>
</pre>

All connections are outbound from the cluster, so there are no port mappings and
nothing listens on the laptop or the LAN. The UIs work the same from the laptop or my
phone, and the same files will work unchanged on a home server. Who may connect is set
in the tailnet policy, which grants only my own user access to the UI machines.

**Headlamp** is the cluster UI: workloads, logs, events, a shell into pods and YAML
editing. It has no login: it acts as its own `cluster-admin` ServiceAccount, so access
is decided by who can reach it. Two layers decide that. The tailnet policy lets only my
user reach the `headlamp` machine, and a NetworkPolicy lets only the Tailscale proxy pods
connect to the Headlamp pod, so nothing else inside the cluster can reach it either.

## Where Images Live

| Kind | Built where | Stored where |
|---|---|---|
| Ansible EEs for AWX | GitHub-hosted runners, or locally with Podman | The lab registry (zot), at `registry.<tailnet>.ts.net/<name>:<tag>` |
| VM images | In WSL with Packer's `qemu` builder on KVM; tested with Vagrant | qcow2 files and Vagrant boxes on the laptop |
| vSphere templates | The Packer pipeline, on the lab's runners | The vSphere content library |

**One registry name works from both sides.** From WSL and my other devices, the name is
the registry's own tailnet machine, with a real HTTPS certificate, so Podman needs no
"insecure registry" setting. Pods are pulled by containerd on the
node, which sits outside cluster DNS, so a `hosts.toml` on the node points the same name
at the registry's fixed ClusterIP. A push from the laptop and a pull from AWX use one
image reference.

**KVM inside WSL.** WSL 2 runs a real Linux kernel with nested virtualization, so
`/dev/kvm` is there. Packer's `qemu` builder installs an AlmaLinux 9 image from a
kickstart on a CD, validates it inside the build, and writes a qcow2 disk and a Vagrant
box. No Hyper-V VM, VirtualBox or cloud account is involved.

## Security Layers

Nothing connects in. The UIs are reached over Tailscale, which only needs outbound
connections, and the runner listener long-polls GitHub over HTTPS. So the lab has no
open ports, and only my tailnet user can reach a UI. The rest of the threat model is
about who can run code on the runners and what that code can reach:

| Risk | Control | How it's tested |
|---|---|---|
| Someone else triggers a job | Fork PRs need approval; only approved actions; read-only default token | Repo settings; the health workflow still passes |
| A trusted action is hijacked | Actions pinned to commit SHAs, Dependabot keeps them current | `grep uses:` shows only SHAs |
| Job code escapes its pod | Non-root runners; namespace enforces Pod Security `restricted` | A privileged pod mounting the node's disk is refused |
| Job code attacks the platform | NetworkPolicy: DNS, HTTPS to the internet and the API only; read-only RBAC | Before/after reachability test from a test pod; `kubectl auth can-i` |
| Job code steals credentials | No Secrets mounted in job pods; the GitHub App key stays with the listener | Inspect a live runner pod's volumes |
| Infrastructure changed by mistake | Terraform applies wait for a required reviewer | Environment protection rule |

## Repository Layout

<pre class="dir-tree">
platform-lab/
├── bootstrap/                     <span class="cm"># cluster-up.sh, cluster-down.sh, secret scripts</span>
├── <span class="hl">kubernetes/</span>
│   ├── kind/platform-lab.yaml     <span class="cm"># The one-node cluster</span>
│   ├── argocd/
│   │   ├── root-app.yaml          <span class="cm"># App-of-apps root</span>
│   │   ├── apps/                  <span class="cm"># Enabled components: Argo CD syncs these</span>
│   │   └── deferred/              <span class="cm"># Switched-off profiles: git mv to enable</span>
│   ├── helm/values/               <span class="cm"># One values file per component</span>
│   ├── ingress/                   <span class="cm"># Tailnet Ingresses: one private HTTPS name per UI</span>
│   ├── platform/                  <span class="cm"># Namespaces, quotas, RBAC</span>
│   │   └── hardening/             <span class="cm"># NetworkPolicies and security test pods</span>
│   └── backstage/                 <span class="cm"># Portal source and catalog</span>
├── scripts/lab-capacity.sh        <span class="cm"># Usage vs the RAM budget</span>
├── .github/workflows/             <span class="cm"># In-cluster health check, Backstage image build</span>
├── docs/step-by-step-guide.md     <span class="cm"># The whole build by hand, no scripts</span>
├── docs/runbooks/                 <span class="cm"># One runbook per phase</span>
├── images/  infrastructure/  automation/  pipelines/
└── ARCHITECTURE.MD  ROADMAP.md
</pre>

## Namespaces by Purpose

| Namespace | Runs |
|---|---|
| `argocd` | Argo CD |
| `tailscale` | Tailscale operator, plus one proxy pod per UI |
| `headlamp` | Cluster management UI |
| `registry` | The lab's container registry (zot) |
| `arc-systems` / `arc-runners` | Runner controller / ephemeral runner pods for each repo's scale set |
| `monitoring` | Prometheus, Grafana (profile) |
| `awx` | AWX (profile) |
| `backstage` | Developer portal (profile) |
| `playground` | CKAD/CKA practice, under a ResourceQuota |

<div class="stage-box s1">
<h3>Capacity model</h3>
<ul>
<li>Core, always on: kind node, Argo CD, Tailscale operator, Metrics Server, Headlamp, the registry, ARC. About 1.5–1.8 GB, plus runner pods only while a job runs.</li>
<li>One heavy profile at a time: observability ~1.0–1.4 GB, AWX ~1.5–2.0 GB, Backstage ~0.6–1.0 GB.</li>
<li>Every chart sets requests and limits; container builds that need lots of memory run on GitHub-hosted runners instead. A 2 GB VM build in WSL means switching the heavy profile off first.</li>
</ul>
</div>
