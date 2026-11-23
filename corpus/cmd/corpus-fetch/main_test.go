// SPDX-License-Identifier: MIT

package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRunUsage(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	manifest := filepath.Join("..", "..", "manifest.jsonl")
	for name, args := range map[string][]string{
		"flag":       {"-no-such-flag"},
		"argument":   {"x"},
		"jobs":       {"-jobs", "0"},
		"manifest":   {"-manifest", "no-such-file"},
		"unknown id": {"-manifest", manifest, "-only", "vendor-ffffffffffff"},
	} {
		var out, errb bytes.Buffer
		if code := run(args, &out, &errb); code != 2 {
			t.Errorf("%s: exit %d, %s", name, code, errb.String())
		}
	}
}

// -record rewrites the manifest it read, canonically; an entry that fails
// (here: no network, an unresolvable host) exits 1 and keeps its fields.
func TestRunRecordFailure(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("XDG_CACHE_HOME", dir)
	const entry = `{"archive":false,"commit":null,"filename":"a.xml","git_blob_sha1":null,"gsdml_version":null,"id":"vendor-000000000001","manufacturer":"x","product":null,"provenance":"p","redistribution":"none","sha256":null,"size":null,"source":"vendor","source_page":"","url":"https://host.invalid/a.xml"}` + "\n"
	manifest := filepath.Join(dir, "manifest.jsonl")
	if err := os.WriteFile(manifest, []byte(entry), 0o644); err != nil {
		t.Fatal(err)
	}
	var out, errb bytes.Buffer
	if code := run([]string{"-manifest", manifest, "-record", "-timeout", "20s"}, &out, &errb); code != 1 || !strings.Contains(errb.String(), "FAIL vendor-000000000001") {
		t.Fatalf("exit %d: %s %s", code, out.String(), errb.String())
	}
	if b, _ := os.ReadFile(manifest); string(b) != entry {
		t.Fatalf("manifest %s", b)
	}
	if _, err := os.Stat(filepath.Join(dir, "otfabric", "gsdml-corpus", "index.jsonl")); err != nil {
		t.Fatal(err)
	}
}
