# Lessons & Next Steps
Decisions, the problems hit along the way, and the roadmap.

## Decisions So Far

- **GitOps from day one.** The first version was a runbook of `kubectl create`
  commands and a demo app in a `sprint1` namespace. Now only kind and Argo CD are
  installed by hand, and everything else is a file in Git. The cluster is disposable:
  one script rebuilds it.
- **Profiles instead of "not enough RAM".** Rather than deferring Prometheus, AWX and
  Backstage indefinitely, each is a ready-made app that switches on with a `git mv`. The
  laptop runs the whole stack, just not all of it at the same time.
- **Builds run where the RAM is.** Building a Backstage image needs about 3 GB, so it
  runs on a GitHub-hosted runner and pushes to GHCR. The laptop only pulls and runs it.
- **Runners without Docker-in-Docker.** DinD needs privileged pods, which are awkward
  under rootless Podman, and a lot of memory. In-cluster runners do cluster-facing jobs
  and scale to zero when idle.
- **A GitHub App, not a personal token.** Scoped permissions and short-lived tokens. One
  app serves both Argo CD and the runners. Splitting it into least-privilege apps is on
  the hardening list.
- **Secrets stay off Git.** They're created from a local file by a script. Sealed
  Secrets will make them GitOps too.
- **Tailscale for access, Traefik parked.** The lab first used Traefik (chosen over
  ingress-nginx, which was retired in March 2026) on `.localhost` names. Moving to the
  Tailscale operator gave every UI its own private name and a real HTTPS certificate,
  reachable from my phone as well as the laptop, with no open ports, and the same files
  will carry over to a home server. The lab still uses the Ingress API and will evaluate
  Gateway API later.
- **Podman as the kind provider.** It keeps the lab free of a Windows-side container
  runtime. The trade-off is rootless networking quirks.
- **Private by default, without a port-forward.** Nothing listens on the laptop or the
  LAN: the cluster only makes outbound connections, and the tailnet policy decides who
  can reach each UI. The Ingresses live in Git, so the UIs come back after a reboot or a
  rebuild with nothing left running in a terminal.
- **A profile ships its own way in.** Profiles sync after the shared tailnet Ingresses,
  when their namespace doesn't exist yet, so each one brings its own Ingress as a second
  source in its Application. A profile that's switched off doesn't leave a machine on the
  tailnet.
- **Headlamp as the cluster UI.** The Kubernetes Dashboard project has been retired and
  points to Headlamp. It's light enough for the core (under 200 MB). I started with
  token sign-in, then switched to no login at all, which made access the real control.
  It's enforced twice: the tailnet policy lets only my user reach it, and a NetworkPolicy
  lets only the Tailscale proxy pods connect to it. Argo CD's self-heal undoes edits made in the
  UI to anything it manages, so lasting changes still go through Git.
- **One runner scale set per repo.** A personal GitHub account can't share runners
  across repos the way an organization can. Each repo that uses the lab gets its own
  small scale set (one Application, one values file, the same GitHub App), and each can
  have its own rights: the Packer runners get no Kubernetes API access at all.
- **WSL 2 rather than a full VM.** WSL is already a lightweight VM whose memory grows
  and shrinks. A Hyper-V or VirtualBox VM would lock away a fixed share of the 8 GB, plus
  about 0.5–1 GB for a second OS, which is the size of a whole profile. The next step up
  is a dedicated second-hand home server, not a VM on the same laptop.
- **GitHub, not self-hosted GitLab.** GitLab needs 4–8 GB on its own, and running Git
  inside the cluster it rebuilds would mean losing both together. GitLab CI experience
  can come later from free gitlab.com plus a GitLab Runner in the cluster, which is
  light and also outbound-only.
- **zot as the lab registry.** Harbor needs about 2 GB across half a dozen pods; zot is
  one small binary with a UI and search. It has no authentication for now, because it's
  reachable only from the cluster and, over Tailscale, from my own devices. That's written down as a gap, not
  forgotten.
- **A fixed ClusterIP for containerd.** containerd runs on the node, outside cluster DNS,
  so it can't resolve `zot.registry.svc`. A pinned Service address and a `hosts.toml`
  give it something stable to point at, without exposing the registry on another port.
- **KVM in WSL rather than a VM beside it.** Nested virtualization makes WSL a working KVM
  host, so VM images build with the same Linux tooling a real hypervisor host would use.
  Vagrant on libvirt turns a built image into a test VM with one command.
- **AWS kept as reference code.** Building on AWS costs money I'm not spending yet, so the
  pipelines keep their AWS code commented out with `#AWS#` markers rather than deleting it.
- **Security controls are tested, not assumed.** A NetworkPolicy does nothing if the
  network plugin doesn't enforce it, so the hardening steps start by proving
  enforcement with a deny-all policy.

## Problems Hit (and What They Taught)

<div class="stage-box s1">
<h3>TLS to GitHub failed: "certificate is valid for *.aserv.co.za"</h3>
<ul>
<li><strong>Symptom:</strong> Argo CD couldn't read the repo, and later couldn't get a GitHub App token. GitHub was serving the wrong certificate.</li>
<li><strong>Cause:</strong> pods use <code>ndots:5</code>, so <code>github.com</code> (one dot) is tried with each search domain first. The laptop's search list, inherited from Windows through WSL and Podman, included a domain with a wildcard DNS record. <code>github.com.&lt;that domain&gt;</code> resolved to a web host, and the TLS check rightly refused it. WSL itself resolved correctly, because outside Kubernetes the default <code>ndots:1</code> doesn't search first.</li>
<li><strong>Diagnosis:</strong> I compared <code>/etc/resolv.conf</code> in WSL, the kind node and an Argo CD pod, then resolved <code>github.com.&lt;search domain&gt;</code> for each domain in the list until one answered.</li>
<li><strong>Fix:</strong> stop WSL generating <code>resolv.conf</code> and keep only the search domains that are needed, then clean the node and restart the pods. The root fix is removing the wildcard record. Rebuilding the cluster alone doesn't help, because each new node copies the host's DNS settings again.</li>
<li><strong>It came back:</strong> Tailscale rewrites WSL's <code>resolv.conf</code> with the network's search domains, which brought a wildcard domain back. Now <code>cluster-up.sh</code> gives kubelet its own <code>resolv.conf</code>, whose only extra search domain is the tailnet's, so pods never try the others.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>"Resource not found in cluster: Application arc-runners"</h3>
<ul>
<li><strong>Symptom:</strong> after moving Traefik to a NodePort and adding Headlamp, the root app never created the <code>arc-runners</code> Application.</li>
<li><strong>Cause:</strong> sync waves. Wave 2 waits for every wave 1 app to be Healthy, and Headlamp sat at <em>Progressing</em>. Its pod was fine, but Argo CD only calls an Ingress Healthy once it has an address, and Traefik copies that address from its own Service. A NodePort Service has no load balancer address, so there was nothing to copy.</li>
<li><strong>Diagnosis:</strong> the root app's operation message (<code>waiting for healthy state of Application/headlamp</code>), then an empty <code>ADDRESS</code> column in <code>kubectl get ingress</code>.</li>
<li><strong>Fix:</strong> tell Traefik to publish a fixed endpoint (<code>ingressEndpoint.ip: 127.0.0.1</code>, which is where the routes really are). One setting fixed every Ingress in the lab. Traefik has since been replaced by Tailscale, where the operator writes each tailnet name into the Ingress status, so the same health check passes.</li>
</ul>
</div>

- **"Revision develop must be resolved" isn't about the branch.** Argo CD couldn't reach
  GitHub at all. Reading the application's status conditions
  (`kubectl get application -o jsonpath='{.status.conditions}'`) gave the real error.
- **Argo CD reads GitHub, not the laptop.** Manifests that only exist locally don't
  exist for Argo CD. The rule is: change, commit, push, then sync.
- **A private repo needs credentials.** The same GitHub App serves Argo CD (read access)
  and the runners (registration). Splitting it into least-privilege apps is on the
  hardening list.
- **A warning isn't an error.** Helm prints `unrecognized format "int64"` when installing
  charts with CRDs. It's the API server noting a schema format label it doesn't check,
  and the install still succeeds. Check the result (`helm list`, the pods), not the noise.
- **Don't hand-install what GitOps owns.** A manually installed Traefik (a `LoadBalancer`
  Service stuck on `<pending>` in kind) would clash with the Argo CD-managed one
  (a fixed `NodePort`). Hand installs are for troubleshooting only, and removed before
  the sync.
- **"Healthy" depends on what the controller reports.** A running pod isn't enough for
  Argo CD. Each resource kind has its own health check, and an Ingress needs a status
  address. With sync waves, one Progressing app quietly holds back everything after it.

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| 0 | Workstation tooling, repository structure, GitHub metadata | Done |
| 1 | kind cluster and Argo CD bootstrap; GitHub App | Done: DNS issue fixed, Argo CD syncing from GitHub |
| 2 | Core platform from Git: Metrics Server, namespaces and RBAC, Headlamp; private UIs over Tailscale | In progress: deployed from Git, UIs on the tailnet; rebuild test next |
| 3 | GitHub Actions runners in the cluster (ARC), one scale set per repo | In progress: controller running; `platform-lab` and `platform-lab-packer` scale sets defined |
| 4 | Observability profile: Prometheus and Grafana, then Loki | Planned |
| 5 | Automation profile: AWX with my own execution environment, stored in the lab registry | In progress: registry tested end to end; AWX next |
| 6 | Developer portal: my own Backstage app | Planned |
| 7 | Hardening: threat model, Pod Security, NetworkPolicy, SHA-pinned actions, approvals; then Sealed Secrets, cert-manager, Gateway API | Planned (guide written) |
| 8 | Jenkins, n8n; optional GitLab Runner against gitlab.com | Planned |
| 9 | VM images on KVM in WSL (Packer `qemu`, Vagrant); Terraform with GitHub OIDC | In progress: AlmaLinux 9 template written, first build next |

## Goals Behind It

The lab supports working towards the **CKAD**, **CKA** and an **AWS Associate**
certification, and it gives the other projects on this site a place to run. The
[Ansible EE pipeline](../ansible-ee-pipeline/index.html) image becomes AWX's execution
environment in Phase 5. The [Packer pipeline](../packer-image-pipeline/index.html)
already uses it: its builds run on the lab's own runner scale set.
