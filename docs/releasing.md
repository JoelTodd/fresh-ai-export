# Releasing

Public releases are source-only. GitHub source archives and the repository
itself are the public distribution path; built EXEs, exports, manifests, logs,
runtime folders, and other local outputs stay out of source control.

## Public Release

Release notes should direct Windows users to inspect the source and build
locally with `scripts\build.ps1`.

To create a release:

1. Update app version metadata, documentation, and release notes on `main`.
2. Tag the release with a matching version, for example `v0.1.0`.
3. Create the GitHub Release from that tag without attaching built EXEs.
4. Share the repository or GitHub source archive.

## Internal Use

Internal users can build from the same tagged source checkout:

- use `scripts\build.ps1` for a portable Windows EXE;
- use the organization's approved channel for any internal build distribution;
- keep Freshdesk credentials out of release assets and deployment notes;
- keep Windows security controls enabled and use narrowly scoped allow rules if
  a locally built EXE needs organization approval.

The build can sign an internal or development EXE when a trusted local
code-signing certificate is available. The local self-signed `Freshdesk Local
Exporter Internal` certificate remains a managed test-machine convenience, not a
public distribution artifact.
