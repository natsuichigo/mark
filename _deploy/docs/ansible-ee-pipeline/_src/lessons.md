# Lessons & Next Steps
Decisions that shaped the pipeline, and what comes next.

## Lessons

<div class="callout">
<p><strong>Promote the artefact you tested.</strong> Rebuilding for production would pull collection and package versions again and produce an image nobody tested. Copying by tag means prod runs exactly what soaked in dev.</p>
</div>

- **Keep a compat track for as long as old hosts exist.** ansible-core 2.16 is the
  last series that manages Python 3.6, so RHEL 8 hosts still need it. Every collection
  bump on the compat EE checks `requires_ansible` in the collection's
  `meta/runtime.yml` first.
- **Test against real targets, not just the image.** A validation playbook proves the
  image contains the right things; the target tests prove modules like firewalld,
  systemd and sysctl actually work against the operating systems being managed.
- **Build arguments work differently in Podman.** `--build-arg NAME` with no value
  reads from the environment in Docker, but Podman takes the name literally. Local
  builds with Podman have to pass `NAME=value`.
- **A build-only token still needs a home.** The intermediate galaxy stage stays in
  the runner's local image cache, so ephemeral runners or a cache prune keep the
  token from lingering.
- **Pin actions to SHAs and let Dependabot move them.** Pinned actions cannot change
  underneath a build; Dependabot proposes updates weekly against `dev`.

## Moving It to the Home Lab

- **Builds stay on GitHub-hosted runners.** `ansible-builder` builds container images,
  and the lab's in-cluster runners deliberately have no Docker. Running these builds
  in the cluster would need privileged Docker-in-Docker pods and about 1 GB more RAM,
  against the lab's hardening. The workflows read their runner from a `RUNNER_LABELS`
  variable that defaults to `ubuntu-latest`, so that choice stays a setting.
- **Trim what the lab doesn't manage.** The lab has no AWS, so the AWS collections,
  CLI, SSM plugin and the Amazon Linux 2023 target are switched off. Each check that
  tested them is switched off with it, so validation still means something.
- **Switch off, don't delete.** `#AWS#` markers keep the AWS content readable in place
  and easy to restore.

## Next Steps

| Next step | Why |
|---|---|
| Add a core 2.19 track | The repo already documents the steps: copy a base folder, add a pipeline, a job, a derived build and a promotion variant |
| Retire the compat track | Once no Python 3.6 hosts remain, the 2.16 images and their tests can go |
| Run the EE in AWX in Platform Lab | The lab now has its own registry; copying an EE there with `skopeo` is the hand-off, and AWX's automation profile (Phase 5) runs it |
| Enable ARA reporting | Each definition has a commented ARA block for recording playbook runs |
