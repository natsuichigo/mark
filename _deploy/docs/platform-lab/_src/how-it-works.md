# How It Works
From a clean Fedora shell to a platform that rebuilds itself from Git.

The whole build is written as a [step-by-step guide](https://github.com/natsuichigo/platform-lab/blob/develop/docs/step-by-step-guide.md)
with no scripts. Every step has three parts: **do** (the commands), **why** (what it
changes and why the platform needs it) and **check** (proof it worked). The repository's
manifests act as the answer key: I write each file from the explanation, then compare.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Prepare WSL</strong><span>Cap memory in <code>.wslconfig</code>, enable systemd, confirm Podman reports cgroup v2</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Create a GitHub App</strong><span>One app lets Argo CD read the private repo and lets the runners register</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Bootstrap</strong><span>Create the kind cluster and install Argo CD with Helm, by hand from the guide (<code>./bootstrap/cluster-up.sh</code> is the same steps scripted)</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Argo CD takes over</strong><span>The root app syncs Traefik, Metrics Server, RBAC and the runner controller from Git</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Run a job in the cluster</strong><span>The <code>platform-health</code> workflow runs on <code>runs-on: platform-lab</code> in an ephemeral pod</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">6</div><div class="flow-text"><strong>Switch on a profile</strong><span><code>git mv</code> an app from <code>deferred/</code> to <code>apps/</code> and push</span></div></div>
</div>

## A Component Is One File

Every component is an Argo CD Application: an upstream chart at a pinned version, plus
values from this repo.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: traefik
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  project: platform
  sources:
    - repoURL: https://traefik.github.io/charts
      chart: traefik
      targetRevision: 42.1.3
      helm:
        valueFiles:
          - $values/kubernetes/helm/values/traefik.yaml
    - repoURL: https://github.com/natsuichigo/platform-lab.git
      targetRevision: develop
      ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: traefik
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [CreateNamespace=true]
```

## Switching a Profile On

```bash
./scripts/lab-capacity.sh       # enough memory free?
git mv kubernetes/argocd/deferred/kube-prometheus-stack.yaml kubernetes/argocd/apps/
git commit -m "feat(monitoring): enable observability profile" && git push
```

Moving the file back and pushing switches the profile off. Argo CD's prune removes
everything the profile created, so the Git history is also a log of what the lab ran.

## A Job Running Inside the Cluster

```yaml
jobs:
  health:
    runs-on: platform-lab          # the in-cluster runner scale set
    steps:
      - run: kubectl wait deployment --all -A --for=condition=Available --timeout=5m
```

No kubeconfig is needed: the runner pod uses its own read-only ServiceAccount.

## Why Argo CD Comes Before Traefik

Argo CD's own UI is routed through Traefik, yet Argo CD is installed first, because
it's what installs Traefik. That works because an Ingress is only a stored record of
a route. The Argo CD chart creates an Ingress for `argocd.platform-lab.localhost`
before any ingress controller exists. When Traefik arrives, it watches the API for
Ingresses with its class and picks that one up. Until then, the UI is reached with a
temporary port-forward to `argocd-server`. Once Traefik is up, that port-forward is
never needed again: the cluster itself publishes Traefik on `127.0.0.1:80`. Declare what you want, and a controller acts
on it whenever it's running: that's the pattern behind all of Kubernetes.

## No Port-Forward: the Cluster Publishes Traefik

The first version reached every UI through `kubectl port-forward` to Traefik, which had
to be restarted after every reboot. Now the port is part of the cluster definition:

```yaml
# kubernetes/kind/platform-lab.yaml
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30080      # Traefik's NodePort
        hostPort: 80
        listenAddress: 127.0.0.1  # loopback only: the routes are plain HTTP
```

```yaml
# kubernetes/helm/values/traefik.yaml
service:
  spec:
    type: NodePort
ports:
  web:
    nodePort: 30080
providers:
  kubernetesIngress:
    publishedService: { enabled: false }
    ingressEndpoint: { ip: 127.0.0.1 }   # gives every Ingress an address (see Lessons)
```

Port mappings are fixed when kind creates the cluster, so `cluster-up.sh` warns if an
existing cluster lacks the mapping. Rebuilding takes one command because everything else
comes back from Git.

## An Image From Build to Pod

The lab registry was proven end to end with one image: pushed from WSL through Traefik,
then started as a pod from the same name.

```bash
podman push registry.platform-lab.localhost/test/busybox:1.37
kubectl run regtest -n playground --restart=Never \
  --image=registry.platform-lab.localhost/test/busybox:1.37 -- echo pulled-from-lab-registry
# Successfully pulled image "registry.platform-lab.localhost/test/busybox:1.37" in 236ms
```

Execution Environments follow the same path. One script handles both sources: an image
built locally with Podman, or a copy (with `skopeo`) of one the pipeline built on GitHub.

```bash
./scripts/lab-registry.sh push localhost/ee-base-core-2.18:dev ee/base-core-2.18:dev
./scripts/lab-registry.sh copy ghcr.io/<owner>/<ee>:<tag>
```

## VM Images on KVM in WSL

```bash
./bootstrap/vm-tools-setup.sh                  # QEMU/KVM, libvirt, Vagrant, skopeo
cd images/packer/almalinux-9
packer init . && packer build .                # qcow2 + Vagrant box, validated in the build
vagrant box add --name platform-lab/almalinux-9 output/almalinux-9.box
vagrant up --provider=libvirt && vagrant ssh
```

## Hardening, Tested Layer by Layer

Each control is proven by trying to break it:

```bash
# Pod Security "restricted" on arc-runners: a privileged pod mounting the node's disk
kubectl apply -f kubernetes/platform/hardening/tests/privileged-pod.yaml
# Error from server (Forbidden): violates PodSecurity "restricted:latest": privileged, hostPath volumes

# NetworkPolicy: first prove the cluster enforces policies at all (a deny-all must block),
# then compare reachability from a test pod before and after
t https://github.com                  # ok        internet over HTTPS still works
t http://argocd-server.argocd.svc     # BLOCKED   the platform is out of reach
```

The order matters. Runner pods are made non-root first, and the API server's
`--dry-run=server` label check confirms nothing running would break, before the namespace
starts enforcing.

<div class="callout warn">
<p><strong>Lab-only shortcuts are labelled as such.</strong> Metrics Server skips kubelet TLS verification because kind's kubelet certificates are self-signed. Argo CD serves plain HTTP behind Traefik. All UIs are reached through a kind port mapping bound to <code>127.0.0.1</code>, so nothing is exposed beyond the machine. Headlamp has no login and acts as a <code>cluster-admin</code> ServiceAccount, so it is locked to the laptop's browser by a Traefik IP allow-list and a NetworkPolicy.</p>
</div>

## Practising for CKAD and CKA

CKAD drills run in a `playground` namespace with a ResourceQuota, so exercises can't
starve the platform. CKA practice uses the platform itself: reading and testing the
runner's RBAC, diagnosing `Pending` pods when a profile doesn't fit, upgrading charts
through Git, and rebuilding the whole cluster with `cluster-down.sh` and `cluster-up.sh`.
