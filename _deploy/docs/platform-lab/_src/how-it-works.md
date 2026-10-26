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
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Argo CD takes over</strong><span>The root app syncs Metrics Server, RBAC, the Tailscale operator and the UIs from Git</span></div></div>
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
  name: tailscale-operator
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  project: platform
  sources:
    - repoURL: https://pkgs.tailscale.com/helmcharts
      chart: tailscale-operator
      targetRevision: 1.104.2
      helm:
        valueFiles:
          - $values/kubernetes/helm/values/tailscale-operator.yaml
    - repoURL: https://github.com/natsuichigo/platform-lab.git
      targetRevision: develop
      ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: tailscale
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

## Why Argo CD Comes Before Its Own Front Door

Argo CD's UI is reached over Tailscale, yet Argo CD is installed first, because it's
what installs the Tailscale operator. Until the operator is running, the UI is reached
with a temporary port-forward to `argocd-server`. Then one Ingress puts it on the
tailnet, and the port-forward is never needed again. Declare what you want, and a
controller acts on it whenever it's running: that's the pattern behind all of Kubernetes.

## Every UI on the Tailnet

The first version reached every UI through `kubectl port-forward`, which had to be
restarted after every reboot. The second used Traefik on `.localhost` names, published
by kind on `127.0.0.1` only. That kept everything on the laptop, but also meant the UIs
only worked on the laptop. Now each UI is one Ingress for the Tailscale operator:

```yaml
# kubernetes/ingress/tailnet.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-tailnet
  namespace: argocd
spec:
  ingressClassName: tailscale
  tls:
    - hosts:
        - argocd                # becomes argocd.<tailnet>.ts.net, with a real certificate
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 80
```

The operator starts a proxy pod that joins the tailnet as `argocd`, gets a Let's
Encrypt certificate and forwards to the Service. The cluster only makes outbound
connections, so it works behind WSL's NAT, from my phone, and on any network. The
operator's OAuth credentials are created from a local file by a script, never committed.

Each profile brings its own Ingress as a second source in its Application. Profiles sync
after the shared Ingress app, when their namespace doesn't exist yet, so keeping the
Ingress with the profile means it only appears while the profile is on.

## An Image From Build to Pod

The lab registry was proven end to end with one image: pushed from WSL, then started as
a pod from the same name. That first test used the registry's old `.localhost` name,
from before the move to Tailscale:

```bash
podman push registry.platform-lab.localhost/test/busybox:1.37
kubectl run regtest -n playground --restart=Never \
  --image=registry.platform-lab.localhost/test/busybox:1.37 -- echo pulled-from-lab-registry
# Successfully pulled image "registry.platform-lab.localhost/test/busybox:1.37" in 236ms
```

Today the same push goes to `registry.<tailnet>.ts.net` over HTTPS through Tailscale,
and pods still pull that name straight from the registry's ClusterIP. Execution
Environments follow the same path. One script handles both sources: an image
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
<p><strong>Lab-only shortcuts are labelled as such.</strong> Metrics Server skips kubelet TLS verification because kind's kubelet certificates are self-signed. Argo CD serves plain HTTP inside the cluster; HTTPS ends at its Tailscale proxy. The UIs are reachable only over my tailnet, and the tailnet policy grants only my own user, so nothing is exposed to the LAN or the internet. Headlamp has no login and acts as a <code>cluster-admin</code> ServiceAccount, so it relies on that policy plus a NetworkPolicy that lets only the Tailscale proxy pods connect. The registry has no authentication yet for the same reason: only the cluster and my own devices can reach it.</p>
</div>

## Practising for CKAD and CKA

CKAD drills run in a `playground` namespace with a ResourceQuota, so exercises can't
starve the platform. CKA practice uses the platform itself: reading and testing the
runner's RBAC, diagnosing `Pending` pods when a profile doesn't fit, upgrading charts
through Git, and rebuilding the whole cluster with `cluster-down.sh` and `cluster-up.sh`.
