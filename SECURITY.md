# Security policy

Report vulnerabilities privately through GitHub Security Advisories for this
repository. Do not include credentials, access tokens, or customer data in a
public issue.

The skill must never tell users or agents to place secret values in command
arguments, chat transcripts, tracked manifests, or uploaded source trees.
Application secrets use only `KEY=@env:NAME`, `KEY=@file:PATH`, or
`KEY=@stdin`; CLI login tokens use stdin or `--from-file`.

CLI artifacts are trusted only after the independent SSHSIG release record and
artifact digest verify. A checksum fetched from the same origin as an artifact
is not an authentication boundary and direct archive pipes are not supported.
