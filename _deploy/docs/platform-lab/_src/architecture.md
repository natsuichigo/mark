# Architecture
Four layers, from the workstation up to images and automation.

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>Workstation layer</strong><span>Fedora 44 (WSL 2 or native), VS Code, Git, Podman, Python and Go, a Python virtual environment for Ansible</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Infrastructure layer</strong><span>Terraform-managed infrastructure and networking definitions (planned)</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>Platform layer</strong><span>Kubernetes on kind, Helm deployments, Traefik ingress, Metrics Server; Argo CD next</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Image and automation layer</strong><span>Packer image factory, Ansible, AWX execution environments, Jenkins, n8n, GitHub Actions</span></div></div>
</div>

## Repository Layout

The structure is laid out for the whole platform up front, so new components have
an obvious home:

<pre class="dir-tree">
platform-lab/
├── bootstrap/                     <span class="cm"># Workstation setup scripts (Fedora on WSL, Ubuntu)</span>
├── <span class="hl">kubernetes/</span>
│   ├── kind/platform-lab.yaml     <span class="cm"># The Sprint 1 cluster definition</span>
│   ├── helm/  argocd/  ingress/   <span class="cm"># Charts, GitOps apps, routing</span>
│   ├── monitoring/  logging/      <span class="cm"># Prometheus/Grafana, Loki (later)</span>
│   └── backstage/                 <span class="cm"># Deferred</span>
├── images/
│   ├── packer/                    <span class="cm"># Packer templates</span>
│   ├── execution-environments/    <span class="cm"># Ansible / AWX EEs</span>
│   └── containers/                <span class="cm"># OCI image builds</span>
├── infrastructure/
│   ├── terraform/
│   └── networking/
├── automation/
│   ├── ansible/  awx/  jenkins/  n8n/
├── pipelines/                     <span class="cm"># Reusable CI/CD templates</span>
├── docs/  scripts/
└── ARCHITECTURE.MD  ROADMAP.md
</pre>

## The Sprint 1 Cluster

<div class="stage-box s1">
<h3>Deliberately small</h3>
<ul>
<li>One <code>kind</code> control-plane node that also runs workloads, with Podman as the node-container provider.</li>
<li>Traefik as the ingress controller, installed with Helm into its own namespace.</li>
<li>Metrics Server for <code>kubectl top</code> and resource-based autoscaling.</li>
<li>Services reached on <code>.localhost</code> names through a loopback-only port-forward: no public DNS, no hosts-file edits, nothing exposed beyond the machine.</li>
</ul>
</div>
