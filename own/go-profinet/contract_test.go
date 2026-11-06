// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"encoding/json"
	"slices"
	"strings"
	"testing"
)

func TestCapabilitiesSayNotIndependent(t *testing.T) {
	var out, errOut bytes.Buffer
	if code := dispatch([]string{"print-capabilities"}, &out, &errOut); code != 0 {
		t.Fatalf("exit %d: %s", code, errOut.String())
	}
	var doc map[string]any
	if err := json.Unmarshal(out.Bytes(), &doc); err != nil {
		t.Fatal(err)
	}
	if doc["schemaVersion"] != "1.0" || doc["adapter"] != "otfabric" || doc["implementation"] != "go-profinet" {
		t.Fatalf("capabilities = %s", out.String())
	}
	up, _ := doc["upstream"].(map[string]any)
	if up["name"] != "go-profinet" || up["independentEngine"] != false {
		t.Fatalf("upstream = %v, want go-profinet, independentEngine false", up)
	}
	roles, _ := doc["roles"].([]any)
	if len(roles) != 3 {
		t.Fatalf("roles = %v", roles)
	}
}

func TestVersionIsOneLine(t *testing.T) {
	old := upstreamVersion
	t.Cleanup(func() { upstreamVersion = old })
	upstreamVersion = "v9.9.9"
	var out bytes.Buffer
	if code := dispatch([]string{"version"}, &out, &out); code != 0 || out.String() != "go-profinet v9.9.9\n" {
		t.Fatalf("exit %d, %q", code, out.String())
	}
}

func TestUnknownCommandExits2(t *testing.T) {
	var out, errOut bytes.Buffer
	if code := dispatch([]string{"no-such-command"}, &out, &errOut); code != 2 || !strings.Contains(errOut.String(), "unknown command") {
		t.Fatalf("exit %d, %q", code, errOut.String())
	}
	if code := dispatch(nil, &out, &errOut); code != 2 {
		t.Fatalf("no command: exit %d", code)
	}
}

func TestContractFlags(t *testing.T) {
	got := contractFlags([]string{"--iface", "eth1", "--iface=eth2", "-iface=eth3", "--station", "x"})
	want := []string{"-i", "eth1", "-i=eth2", "-i=eth3", "--station", "x"}
	if !slices.Equal(got, want) {
		t.Fatalf("contractFlags = %v, want %v", got, want)
	}
}
