# Lessons & Next Steps
Design decisions that came from real failures, and what is left to do.

## Lessons

<div class="callout">
<p><strong>Check whether a dependency is real before adding a stage to work around it.</strong> The Windows build was briefly split into two stages to delete a temporary admin account that could not delete itself. The premise was wrong: <code>ValidateCredentials</code> checks the local account database in-process, not through a network logon, so the built-in Administrator can set and verify its own password in one session. That removed the extra account, the second stage and a disposable base AMI.</p>
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
- **Don't persist UserData on Windows.** EC2Launch records UserData as already run,
  and that state is captured in the AMI. Setting `<persist>true</persist>` to work
  around it would re-run the bootstrap on every production instance.
- **Narrow the path triggers per OS.** Broad paths such as `builds/aws/**` meant a
  change to a Windows template started a full RHEL build on both platforms. Each
  workflow now lists exactly the files its build consumes, and stays broad only
  where a file is genuinely shared, like the composite actions and Ansible roles.
- **One shared build action, never forked.** Keeping init/validate/build and manifest
  parsing in one composite action means a fix lands for every OS at once.

## Next Steps

| Next step | Why |
|---|---|
| Final credential step for Windows on vSphere | That template still ships with the build password on Administrator, because Packer shuts the VM down over WinRM with it. Today it is reset at deployment |
| More operating systems | `builds/_skeleton/` and the standards' checklists make a new OS a known procedure |
| Windows CIS at build time | It currently arrives by GPO after domain join; applying a baseline in the image would cover machines that never join a domain |
