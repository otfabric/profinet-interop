// SPDX-License-Identifier: (GPL-2.0)
// Copyright (c) 2026 OT Fabric contributors
//
// An ifdriver for giometti/umrp that needs no kernel MRP support
// (CONFIG_BRIDGE_MRP). A blocked or disabled ring port is put in the
// nftables set "blocked" of the bridge table "mrp", whose rules drop every
// frame the bridge would receive from or send to it; a forwarding port is
// taken out of it. (The bridge's own port states cannot be used: without
// STP the kernel makes every port forwarding again, and the user-space STP
// mode is not available in a network namespace.) An FDB flush flushes the
// bridge's dynamic entries. umrp itself sends, receives and forwards every
// MRP frame on raw sockets, which see a frame before the bridge does; the
// table also keeps the bridge from forwarding MRP frames. Part of the profinet-interop umrp adapter
// (GPL-2.0, like umrp); it is never linked into go-profinet.

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <net/if.h>

#include "ifdriver.h"
#include "state_machine.h"
#include "utils.h"

__printf(1, 2) static int run(const char *fmt, ...)
{
	char *cmd;
	va_list args;
	int ret;

	va_start(args, fmt);
	ret = vasprintf(&cmd, fmt, args);
	va_end(args);
	if (ret < 0)
		return -1;
	pr_debug_v("executing: %s", cmd);
	ret = system(cmd);
	if (ret != 0)
		pr_err("%s: exit %d", cmd, ret);
	free(cmd);
	return ret == 0 ? 0 : -1;
}

int bridge_port_set_state(struct mrp_port *p,
			  enum br_mrp_port_state_type state)
{
	const char *s;
	int ret;

	switch (state) {
	case BR_MRP_PORT_STATE_BLOCKED:    s = "blocked"; break;
	case BR_MRP_PORT_STATE_DISABLED:   s = "disabled"; break;
	case BR_MRP_PORT_STATE_FORWARDING: s = "forwarding"; break;
	default:
		return -1;
	}
	ret = run("nft add element bridge mrp blocked '{ \"%s\" }'", p->ifname);
	if (ret == 0 && state == BR_MRP_PORT_STATE_FORWARDING)
		ret = run("nft delete element bridge mrp blocked '{ \"%s\" }'", p->ifname);
	if (ret == 0)
		ret = run("echo %s > /run/profinet-interop/state-%s", s, p->ifname);
	return ret;
}
alias_ifdriver_port_set_state(bridge_port_set_state);

int bridge_set_ring_role(struct mrp *mrp, enum br_mrp_ring_role_type role)
{
	pr_debug("bridge: %s ring role %d", mrp->ifname, role);
	return 0;
}
alias_ifdriver_set_ring_role(bridge_set_ring_role);

int bridge_set_in_role(struct mrp *mrp, enum br_mrp_in_role_type role)
{
	pr_debug("bridge: %s in role %d", mrp->ifname, role);
	return 0;
}
alias_ifdriver_set_in_role(bridge_set_in_role);

int bridge_flush(struct mrp *mrp)
{
	FILE *f;

	/* Counted for the tests: one line per flush. */
	f = fopen("/run/profinet-interop/flushes", "a");
	if (f) {
		fputs("flush\n", f);
		fclose(f);
	}
	return run("ip link set dev %s type bridge fdb_flush", mrp->ifname);
}
alias_ifdriver_flush(bridge_flush);

int bridge_init(void)
{
	return 0;
}
alias_ifdriver_init(bridge_init);

void bridge_uninit(void)
{
}
alias_ifdriver_uninit(bridge_uninit);
