# Lessons & Next Steps
Design decisions that came from real failures, moving to the home lab, and what is left to do.

## Lessons

<div class="callout">
<p><strong>Check whether a dependency is real before adding a stage to work around it.</strong> The Windows build was briefly split into two stages to delete a temporary admin account that could not delete itself. The premise was wrong: <code>ValidateCredentials</code> checks the local account database in-process, not through a network logon, so the built-in Administrator can set and verify its own password in one session. That removed the extra account, the second stage and a disposable base AMI from the AWS build.</p>
</div>

- **Windows validator output must stay ASCII.** Over WinRM there is no console to set
  the output encoding on, so multi-byte characters arrived mangled and split the
  `Validation Summary` line in two, which broke the summary parser. Linux validators
  keep their box-drawing characters; Windows uses `---` markers.
- **A `-var-file` outranks `PKR_VAR_*`.** A value left in a pkrvars file silently
  wins over the secret passed in the environment, so credentials must never appear
  in var files, even as placeholders.
- **`PACKER_LOG=1` can leak secrets.** It can print Base64-encoded values that
  Packer's exact-match redaction misses, so those logs are not kept.
- **Don't persist UserData on Windows** (from the AWS build). EC2Launch records
  UserData as already run, and that state is captured in the AMI. Setting
  `<persist>true</persist>` to work around it would re-run the bootstrap on every
  production instance.
- **Narrow the path triggers per OS.** Broad paths such as `builds/aws/**` meant a
  change to a Windows template started a full RHEL build on both platforms. Each
  workflow now lists exactly the files its build consumes, and stays broad only where a file is genuinely
  shared, like the composite actions and Ansible roles.
- **One shared build action, never forked.** Keeping init/validate/build and manifest
  parsing in one composite action means a fix lands for every OS at once.

## Moving It to the Home Lab

- **Switch off, don't delete.** The AWS jobs and steps are commented out with `#AWS#`
  markers, and switched-off values are tagged `#AWS-OFF#`. One `sed` per file restores them,
  and the AWS code stays readable next to the vSphere code it mirrors.
- **Runner labels as variables paid off.** The workflows read their runner labels from
  repository variables, so moving every job onto the lab's runners was a settings change.
- **ARC matches on the scale set name.** Jobs that ask for `["self-hosted", "linux"]`
  never reach an ARC scale set. The variables have to name the scale set itself.
- **Pick the boot-file delivery that suits the network.** Packer can serve kickstart and
  autounattend files over HTTP, but then the build VM must connect back to the runner.
  A pod behind WSL's NAT can't be reached from the LAN, so the files go in on a CD and
  every connection starts from the runner.

## Next Steps

| Next step | Why |
|---|---|
| Final credential step for Windows on vSphere | That template still ships with the build password on Administrator, because Packer shuts the VM down over WinRM with it. Today it is reset at deployment |
| A `qemu` target for the home lab | Platform Lab now runs KVM inside WSL; a `qemu` source next to `vsphere-iso` would let the same kickstart, roles and validators build images there, no vCenter needed |
| More operating systems | `builds/_skeleton/` and the standards' checklists make a new OS a known procedure |
| Bake the tools into the runner image | Each job installs Packer, `govc` and ansible-core with `sudo`; a custom image would let the runner pods drop privilege escalation, as the rest of the lab's hardening expects |
| Windows CIS at build time | It currently arrives by GPO after domain join; applying a baseline in the image would cover machines that never join a domain |
