# Security policy

Report vulnerabilities privately through GitHub Security Advisories for this
repository. Do not include credentials, access tokens, or customer data in a
public issue.

The skill must never tell users or agents to place secret values in command
arguments, chat transcripts, tracked manifests, or uploaded source trees.
Application secrets use only `KEY=@env:NAME`, `KEY=@file:PATH`, or
`KEY=@stdin`; CLI login tokens use stdin or `--from-file`.

Fresh CLI installation trusts only the SSHSIG identity committed in
[`release-signers`](release-signers). Never download or replace that trust
anchor from `host.impossibuild.ai`; the release origin is not a trust source.
Treat any repository change to `release-signers` as a trust-root rotation and
verify it out of band before accepting it.
Download `/dl/release.txt` and `/dl/release.txt.sshsig`, verify the exact
release bytes with `ssh-keygen -Y verify`, inspect the authenticated record,
and accept an archive from `/dl/` only when its SHA-256 digest matches the
signed artifact entry. Inspect the authenticated archive contents before
executing the CLI.

Do not execute `/install`, `/install.ps1`, a curl-pipe command, an unsigned
archive, or a checksum fetched without its signed release record. A release
origin compromise must not be able to substitute both executable code and the
trust decision.
