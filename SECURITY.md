# Security

## Reporting

Report vulnerabilities privately through GitHub's security advisories of this repository ("Report a vulnerability"), not in public issues. Problems of an upstream stack belong to that project; tell us too when it affects the images.

## The images

- Test tools: use them only on isolated test networks, never on a plant network. The pinned p-net tree is the last complete public GPLv3 snapshot and predates the v1.0.2 fixes of CVE-2025-32396..32405 (versions.yaml).
- They need `NET_RAW` and `NET_ADMIN` (raw Ethernet sockets), and the MRP ring set-up needs a privileged container in the host's PID and network namespaces ([docs/CONTAINER_CONTRACT.md](docs/CONTAINER_CONTRACT.md)).
- Upstreams are pinned by commit, version or hash and base images by digest; `scripts/check-versions.sh` keeps [versions.yaml](versions.yaml) in step with the Dockerfiles.
- No image is published: every user builds them (`make images`).
