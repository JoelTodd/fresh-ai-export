# Releasing

Public Windows releases use GitHub Release assets for the portable EXE and its
checksum. The public EXE is intentionally unsigned because public code-signing
cost is disproportionate for this personal portfolio project.

## Public Windows Release

The `Windows release` GitHub Actions workflow builds the portable EXE on
Windows, writes `SHA256SUMS.txt`, and attaches both files to a GitHub Release
for version tags such as `v0.1.0`.

Public release notes should say that the EXE is unsigned. Windows SmartScreen
or managed endpoint policy can warn or block an unsigned download. Users who do
not want to run an unsigned EXE can inspect the source and build locally with
`scripts\build.ps1`.

To create a release:

1. Update app version metadata and release notes on `main`.
2. Tag the release with a matching version, for example `v0.1.0`.
3. Push the tag to GitHub.
4. Wait for the `Windows release` workflow to finish before sharing the EXE.

Manual workflow runs build and upload the EXE and checksum as workflow
artifacts. They do not create a GitHub Release unless the run was triggered by
a version tag.

## Internal Use

Internal use can choose between the public unsigned EXE and a locally signed
build made from the same version:

- verify the public release checksum during rollout;
- use the organization's approved channel for any internal distribution;
- keep Freshdesk credentials out of release assets and deployment notes;
- keep Windows security controls enabled and use narrowly scoped allow rules if
  the unsigned public release is not acceptable on managed devices.

The build can still sign an internal or development EXE when a trusted local
code-signing certificate is available. The local self-signed
`Freshdesk Local Exporter Internal` certificate remains a managed test-machine
convenience, not a public trust signal.
