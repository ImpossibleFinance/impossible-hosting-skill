# Security policy

Report vulnerabilities privately through GitHub Security Advisories for this
repository. Do not include credentials, access tokens, or customer data in a
public issue.

The skill must never tell users or agents to place secret values in command
arguments, chat transcripts, tracked manifests, or uploaded source trees.
Application secrets use only `KEY=@env:NAME`, `KEY=@file:PATH`, or
`KEY=@stdin`; CLI login tokens use stdin or `--from-file`.

The remote MCP server is trusted only at `https://innstance.impossibuild.ai/mcp`,
on the control plane. An MCP endpoint under a tenant address is a customer's
application, never Innstance, and a client's server named `innstance` is
trusted by its URL, never by its name. Configuration examples in these guides
carry the name of an environment variable that the client expands, never a
token value. A tool that stores a token for a client keeps it in an
owner-only file in the user's home directory, never in a project, a tracked
file, or a command argument.

Run `npx innstance` only with the user's agreement, from a directory outside
any project, and only at a version whose npm registry entry shows a provenance
attestation and whose `repository.url` is exactly
`git+https://github.com/ImpossibleFinance/impossible-hosting-cli.git`. A
package without provenance, or one with a similar name, is not ours. That
check relies on npm and its provenance attestation, which is weaker than the
SSHSIG release record that guards the CLI below.

Fresh CLI installation trusts only the SSHSIG identity committed in
[`release-signers`](release-signers). Never download or replace that trust
anchor from `innstance.impossibuild.ai`; the release origin is not a trust source.
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
