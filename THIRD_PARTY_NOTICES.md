# Third-party notices

This repository contains no code of the implementations below (one file
written for umrp is GPL-2.0: see the end). Its images
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
| Net-SNMP 5.9.3 (Debian bookworm package `snmp` 5.9.3+dfsg-2+deb12u1) | Net-SNMP's BSD-style licences (CMU/UCD, Networks Associates, Sun, Sparta, Cisco, Fabasoft, ...: `/licenses/net-snmp/copyright`) | Debian bookworm | may be |
| umrp v4.0 `fb193eac1a2df51fe42e19d4ea36bb0157bda09f` (Rodolfo Giometti; a fork of microchip-ung/mrp) | GPL-2.0 | https://github.com/giometti/umrp | no: build it locally (`make image-umrp`) |
| microchip-ung/mrp `177717ee893d5ccc6e31147b1b8a720c9b798b81` (after v1.2) | GPL-2.0 | https://github.com/microchip-ung/mrp | no: build it locally (`make image-mrp`) |
| microchip-ung/cfm `7a50f4adcccf2d2e910816ea6d78446fea8fe7d8` (libcfm_netlink, linked by umrp and mrp) | GPL-2.0 | https://github.com/microchip-ung/cfm | no |
| Debian, Python and Rust base images | their respective licences | Docker Hub | — |

The p-net build patches two lines of the p-net sources inside the image
(the Ethernet speed check of Connect, `-Werror`); the patched source is not
distributed. GPL images are not published so that nobody receives GPL
binaries from this project without the corresponding source offer; each
user builds them from the upstream source.

`adapters/umrp/ifdriver_bridge.c` is an exception to this repository's MIT
licence: it is GPL-2.0 (its SPDX header says so), written for this project
as a driver of umrp's `ifdriver` interface and compiled only into the umrp
image. It applies umrp's ring port states to a Linux bridge without the
kernel's MRP support. No upstream file of umrp is changed. It is never part
of go-profinet, which tests against the image only over the network.
