# Third-party notices

This repository contains no code of the implementations below. Its images
obtain them at build time from their upstream, by pinned commit or by
version and hash (see [versions.yaml](versions.yaml)), and keep their
licence files under `/licenses/` in the image.

| Implementation | Licence | Obtained from | Image published |
|----------------|---------|---------------|-----------------|
| rt-labs p-net `ea5e5540b2be55c4dfadffda39b948632c104daa`, with cmake-tools `5f104ff` and osal `e960068` (BSD-3-Clause) | GPL-3.0-only, or a commercial licence from rt-labs | https://github.com/rtlabs-com/p-net | no: build it locally (`make image-pnet`) |
| pnio-rs v0.1.0 `798500c1bf3726a1bf015c43f39c6ae2a2d55b28` | MIT OR Apache-2.0 | https://github.com/core-engineering/pnio-rs | may be |
| profinet-py 0.6.6 | GPL-3.0-only, or a commercial licence | PyPI | no |
| pnio-dcp 1.2.0 | MIT, © 2020-2023 Codewerk GmbH | PyPI (sha256 pinned) | may be |
| scapy 2.6.1 | GPL-2.0-only | PyPI | no |
| tshark (Wireshark) 4.0.17 | GPL-2.0-or-later | Debian bookworm | no |
| Debian, Python and Rust base images | their respective licences | Docker Hub | — |

The p-net build patches two lines of the p-net sources inside the image
(the Ethernet speed check of Connect, `-Werror`); the patched source is not
distributed. GPL images are not published so that nobody receives GPL
binaries from this project without the corresponding source offer; each
user builds them from the upstream source.
