// SPDX-License-Identifier: MIT

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
)

// Set by the build (Dockerfile): the go-profinet release and its commit.
var (
	adapterVersion   = "dev"
	upstreamVersion  = "unknown"
	upstreamRevision = ""
)

// version is the go-profinet release the image is built from.
func version() string { return upstreamVersion }

// capabilitiesDoc is the capability document (docs/CONTAINER_CONTRACT.md).
// It declares only what the commands of this image do; go-profinet's MRP
// ring node is not behind the contract's node command here.
func capabilitiesDoc() map[string]any {
	up := map[string]any{"name": "go-profinet", "version": upstreamVersion, "independentEngine": false}
	if upstreamRevision != "" {
		up["revision"] = upstreamRevision
	}
	return map[string]any{
		"schemaVersion":  "1.0",
		"adapter":        "otfabric",
		"implementation": "go-profinet",
		"version":        upstreamVersion,
		"adapterVersion": adapterVersion,
		"license":        "MIT",
		"roles":          []string{"device", "controller", "dcp-tool"},
		"features": map[string]any{
			"dcpIdentify": true, "dcpGet": true, "dcpSetName": true, "dcpSetIP": true, "dcpSignal": true, "dcpReset": true,
			"lldp": true, "connect": true, "advancedStartup": true, "legacyStartup": true, "cyclic": true,
			"recordRead": true, "recordWrite": true, "readImplicit": true, "writeMultiple": true, "im0": true,
			"diagnosis": true, "alarms": true, "reparameterize": true, "gsdml": true, "snmp": true,
		},
		"upstream": up,
	}
}

// contractFlags maps the contract's flag names to the node's: --iface is -i.
func contractFlags(args []string) []string {
	out := make([]string, 0, len(args))
	for _, a := range args {
		switch {
		case a == "--iface" || a == "-iface":
			a = "-i"
		case strings.HasPrefix(a, "--iface="):
			a = "-i=" + strings.TrimPrefix(a, "--iface=")
		case strings.HasPrefix(a, "-iface="):
			a = "-i=" + strings.TrimPrefix(a, "-iface=")
		}
		out = append(out, a)
	}
	return out
}

// run dispatches one command and returns the exit status: 2 for an
// unknown command (contract), 1 when the command fails (fail exits).
func run(args []string) int {
	return dispatch(args, os.Stdout, os.Stderr)
}

func dispatch(args []string, stdout, stderr io.Writer) int {
	if len(args) < 1 {
		fmt.Fprintln(stderr, "usage: profinet-interop print-capabilities|version|device|controller|dcp|lldp [flags]")
		return 2
	}
	rest := contractFlags(args[1:])
	var err error
	switch args[0] {
	case "version":
		fmt.Fprintf(stdout, "go-profinet %s\n", version())
		return 0
	case "print-capabilities":
		b, _ := json.Marshal(capabilitiesDoc())
		fmt.Fprintf(stdout, "%s\n", b)
		return 0
	case "controller":
		err = runController(rest)
	case "device":
		err = runDevice(rest)
	case "dcp":
		err = runDCP(rest)
	case "lldp":
		err = runLLDP(rest)
	default:
		fmt.Fprintf(stderr, "unknown command %q: profinet-interop print-capabilities|version|device|controller|dcp|lldp\n", args[0])
		return 2
	}
	if err != nil {
		fail(err)
	}
	return 0
}
