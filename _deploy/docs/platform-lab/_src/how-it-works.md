# How It Works
The Sprint 1 runbook: from a clean Fedora shell to an app served through ingress.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Prepare WSL</strong><span>Enable systemd, confirm Podman reports cgroup v2</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Create the cluster</strong><span><code>kind create cluster --config platform-lab.yaml</code> with <code>KIND_EXPERIMENTAL_PROVIDER=podman</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Install Traefik</strong><span><code>helm upgrade --install traefik traefik/traefik --namespace traefik --create-namespace --wait</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Install Metrics Server</strong><span>Upstream manifest, patched for kind's self-signed kubelet certificates</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Deploy a sample app</strong><span><code>traefik/whoami</code> in a <code>sprint1</code> namespace, with a Service and an Ingress</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">6</div><div class="flow-text"><strong>Reach it locally</strong><span>Loopback port-forward to Traefik, then <code>http://whoami.platform-lab.localhost:8080/</code></span></div></div>
</div>

## The Cluster Definition

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: platform-lab
nodes:
  - role: control-plane
```

## Routing an App Through Ingress

```bash
kubectl create namespace sprint1
kubectl create deployment whoami --image=traefik/whoami --port=80 -n sprint1
kubectl expose deployment whoami --port=80 --target-port=80 -n sprint1
kubectl create ingress whoami --class=traefik \
  --rule='whoami.platform-lab.localhost/*=whoami:80' -n sprint1
```

Names ending in `.localhost` resolve to loopback, so the app opens in a Windows
browser through the WSL port-forward with no DNS record or hosts-file entry.

<div class="callout warn">
<p><strong>Lab-only shortcuts are labelled as such.</strong> Metrics Server runs with <code>--kubelet-insecure-tls</code> because kind's kubelet certificates are not signed by a CA it trusts. That is acceptable for a disposable local cluster and is never carried into production. The port-forward stays bound to <code>127.0.0.1</code>, not <code>0.0.0.0</code>.</p>
</div>

## Practising for CKAD

The `sprint1` namespace doubles as a practice area: scaling, rollouts and rollbacks,
probes, ConfigMaps and Secrets, resource requests and limits, scheduling and
troubleshooting. Deleting and recreating the namespace resets it between exercises.
