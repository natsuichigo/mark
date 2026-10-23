# Architecture
How the repository is organised, how a vSphere build is shaped, and where it runs.

## Where It Runs

<div class="flow">
<div class="flow-step"><div class="flow-num">1</div><div class="flow-text"><strong>GitHub Actions</strong><span>A push or a manual run queues jobs for <code>runs-on: platform-lab-packer</code></span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">2</div><div class="flow-text"><strong>Platform Lab cluster</strong><span>The ARC listener picks the job up over outbound HTTPS and starts an ephemeral runner pod</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">3</div><div class="flow-text"><strong>vCenter</strong><span>Packer creates the build VM through the vSphere API</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">4</div><div class="flow-text"><strong>Build VM</strong><span>Packer and Ansible connect over SSH (Linux) or WinRM (Windows), harden and validate it</span></div></div>
<div class="flow-arrow">↓</div>
<div class="flow-step"><div class="flow-num">5</div><div class="flow-text"><strong>Content library</strong><span>The template is published; old versions beyond the retention count are removed</span></div></div>
</div>

Every connection starts from the runner pod. The kickstart and autounattend files go
into the VM on a CD (`common_data_source = "disk"`), not over Packer's built-in HTTP
server, so the VM never has to reach back into a pod sitting behind WSL's NAT. That is
what lets a laptop cluster drive the builds. The runner pods have no Kubernetes API
rights, because Packer never touches the cluster.

## Repository Layout

<pre class="dir-tree">
packer-image-pipeline/
├── <span class="hl">builds/</span>
│   ├── vmware/                    <span class="cm"># vSphere, common and Linux storage variables</span>
│   │   ├── linux/rhel/8.10/
│   │   └── windows/2022/
│   ├── aws/                       <span class="cm"># Kept, switched off in the home lab</span>
│   └── _skeleton/                 <span class="cm"># Starting points for a new OS</span>
├── <span class="hl">ansible/</span>                       <span class="cm"># Playbooks and roles: base, configure, clean, rhel_cis, ...</span>
├── scripts/                       <span class="cm"># Disk, WinRM, clean-up and init scripts</span>
├── <span class="hl">tests/</span>                         <span class="cm"># Inline validators: linux/*.sh, windows/*.ps1</span>
├── docs/standards/                <span class="cm"># vSphere (and AWS) build standards</span>
├── manifests/                     <span class="cm"># Packer manifest output</span>
└── .github/
    ├── workflows/                 <span class="cm"># rhel-, windows-2022-golden-image.yml</span>
    └── actions/                   <span class="cm"># Composite actions: build, packer, vmware, summary</span>
</pre>

## Two Builds on vSphere

<div class="stage-box s1">
<h3>RHEL 8.10</h3>
<ul>
<li><code>vsphere-iso</code> boots the install ISO and reads a kickstart from an attached CD.</li>
<li>The VM registers with Red Hat Subscription Manager during the build, then Ansible applies the CIS role.</li>
<li>Packer connects as an ephemeral build user over SSH.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>Windows Server 2022</h3>
<ul>
<li><code>vsphere-iso</code> boots the install ISO with an autounattend file and init scripts on a CD (<code>cd_files</code>).</li>
<li>VMware Tools and WinRM are set up at first boot, then Ansible applies the baseline over WinRM.</li>
<li>CIS for Windows is left to GPO after domain join.</li>
</ul>
</div>

Both publish to a vSphere content library as a template.

## Pipeline Shape

<pre class="dir-tree">
.github/workflows/&lt;os&gt;-golden-image.yml        <span class="cm"># WHEN to build: triggers, inputs, job env</span>
  └── .github/actions/build/&lt;family&gt;-golden-image  <span class="cm"># HOW: orchestration</span>
        ├── packer/setup-tools                     <span class="cm"># Packer, plugins, govc</span>
        ├── packer/build-with-validation           <span class="cm"># init / validate / build</span>
        ├── vmware/content-library-cleanup         <span class="cm"># retention</span>
        └── (summary is a separate job)
</pre>

- Workflows hold **no build logic**: triggers, inputs, environment and job
  definitions only.
- `packer/build-with-validation` is shared by every OS family and is never forked,
  so the init/validate/build and manifest-parsing logic exists once.
- The summary is its own job with `if: always()`, so it publishes even when a
  build fails.
- Runner labels come from repository variables (`RUNNER_LABELS_SMALL`,
  `RUNNER_LABELS_LARGE`), so pointing the pipeline at the lab's runners is a settings
  change, not a code change.
