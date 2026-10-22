# Architecture
How the repository is organised, and the two build shapes it uses.

## Repository Layout

<pre class="dir-tree">
packer-image-pipeline/
├── <span class="hl">builds/</span>
│   ├── aws/                       <span class="cm"># common.pkrvars.hcl + one folder per OS</span>
│   │   ├── linux/rhel/8.10/
│   │   ├── linux/aml23/
│   │   └── windows/2022/
│   ├── vmware/                    <span class="cm"># vSphere, common and Linux storage variables</span>
│   │   ├── linux/rhel/8.10/
│   │   └── windows/2022/
│   └── _skeleton/                 <span class="cm"># Starting points for a new OS</span>
├── <span class="hl">ansible/</span>                       <span class="cm"># Playbooks and roles: base, configure, clean, rhel_cis, aml23_cis, ...</span>
├── scripts/                       <span class="cm"># Bootloader, disk, WinRM, clean-up and credential scripts</span>
├── <span class="hl">tests/</span>                         <span class="cm"># Inline validators: linux/*.sh, windows/*.ps1</span>
├── docs/standards/                <span class="cm"># AWS and vSphere build standards</span>
├── manifests/                     <span class="cm"># Packer manifest output</span>
└── .github/
    ├── workflows/                 <span class="cm"># rhel-, aml23-, windows-2022-golden-image.yml</span>
    └── actions/                   <span class="cm"># Composite actions: build, packer, summary, clean-up</span>
</pre>

## Two Build Shapes on AWS

<div class="stage-box s1">
<h3>Two-stage (Linux)</h3>
<ul>
<li>Stage 1, <code>amazon-ebssurrogate</code>, builds the disk from scratch so the OS gets a custom, CIS-compliant partition layout.</li>
<li>Stage 2, <code>amazon-ebs</code>, starts from that base AMI and configures, hardens and validates it.</li>
<li>Two manifests: <code>manifest-aws-base.json</code> and <code>manifest-aws-final.json</code>.</li>
</ul>
</div>

<div class="stage-box s2">
<h3>Single stage (Windows)</h3>
<ul>
<li>Starts from the vendor AMI and only configures it, because no custom partitioning is needed.</li>
<li>The credential change is the <strong>last</strong> provisioner, with <code>skip_clean = true</code>, so Packer does not try to clean up using a password it just replaced.</li>
<li>One manifest: <code>manifest-aws-final.json</code>.</li>
</ul>
</div>

On vSphere, Linux builds boot from a kickstart ISO and Windows from an autounattend
ISO, and the result is published to a content library as a template.

## Pipeline Shape

<pre class="dir-tree">
.github/workflows/&lt;os&gt;-golden-image.yml        <span class="cm"># WHEN to build: triggers, inputs, job env</span>
  └── .github/actions/build/&lt;family&gt;-golden-image  <span class="cm"># HOW: orchestration</span>
        ├── packer/setup-tools                     <span class="cm"># tools and plugins</span>
        ├── packer/build-with-validation           <span class="cm"># init / validate / build</span>
        ├── aws/validate                           <span class="cm"># optional post-build EC2 test</span>
        ├── aws/ami-cleanup                        <span class="cm"># retention, once per name prefix</span>
        └── (summary is a separate job)
</pre>

- Workflows hold **no build logic**: triggers, inputs, environment and job
  definitions only.
- `packer/build-with-validation` is shared by every OS family and is never forked,
  so the init/validate/build and manifest-parsing logic exists once.
- The summary is its own job with `if: always()`, so it publishes even when a
  build fails.
