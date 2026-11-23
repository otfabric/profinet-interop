// SPDX-License-Identifier: MIT

package corpus

import (
	"bytes"
	"os"
	"strings"
	"testing"
)

// The committed manifest is valid and in its canonical form: what
// WriteManifest writes, so -record changes only the fields it records.
func TestCommittedManifest(t *testing.T) {
	t.Parallel()
	b, err := os.ReadFile("manifest.jsonl")
	if err != nil {
		t.Fatal(err)
	}
	entries, err := ReadManifest(bytes.NewReader(b))
	if err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	if err := WriteManifest(&out, entries); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(out.Bytes(), b) {
		t.Fatal("manifest.jsonl is not in canonical form: rewrite it with WriteManifest (corpus-fetch -record)")
	}
	git, archives := 0, 0
	for _, e := range entries {
		if e.GitBlobSHA1 != nil {
			git++
		}
		if e.Archive {
			archives++
		}
	}
	if git == 0 || archives == 0 {
		t.Fatalf("%d git files, %d archives", git, archives)
	}
}

func TestReadManifestRefuses(t *testing.T) {
	t.Parallel()
	const good = `{"id":"vendor-000000000001","source":"vendor","url":"https://example.com/a.zip","source_page":"","commit":null,"git_blob_sha1":null,"sha256":null,"size":null,"archive":true,"filename":"a.zip","manufacturer":"x","product":null,"gsdml_version":null,"provenance":"p","redistribution":"none"}`
	if es, err := ReadManifest(strings.NewReader(good + "\n\n")); err != nil || len(es) != 1 {
		t.Fatalf("good: %v", err)
	}
	for name, m := range map[string]string{
		"empty":     "",
		"json":      "{",
		"unknown":   strings.Replace(good, `"archive"`, `"other":1,"archive"`, 1),
		"id":        strings.Replace(good, "vendor-000000000001", "x", 1),
		"http":      strings.Replace(good, "https://", "http://", 1),
		"sha256":    strings.Replace(good, `"sha256":null`, `"sha256":"ab"`, 1),
		"redist":    strings.Replace(good, `"redistribution":"none"`, `"redistribution":""`, 1),
		"members":   strings.Replace(good, `"archive":true`, `"archive":false,"members":[{"name":"a","sha256":"","size":1}]`, 1),
		"duplicate": good + "\n" + good,
		"git unpinned": strings.NewReplacer(`"source":"vendor"`, `"source":"github:o/r"`, `"commit":null`, `"commit":"0123456789abcdef0123456789abcdef01234567"`,
			`"git_blob_sha1":null`, `"git_blob_sha1":"0123456789abcdef0123456789abcdef01234567"`).Replace(good),
		"git no blob": strings.NewReplacer(`"source":"vendor"`, `"source":"github:o/r"`, `"commit":null`, `"commit":"0123456789abcdef0123456789abcdef01234567"`,
			`a.zip"`, `0123456789abcdef0123456789abcdef01234567/a.zip"`).Replace(good),
		"git no commit": strings.Replace(good, `"source":"vendor"`, `"source":"github:o/r"`, 1),
	} {
		if _, err := ReadManifest(strings.NewReader(m)); err == nil {
			t.Errorf("%s: accepted", name)
		}
	}
	if _, err := ReadManifestFile("no-such-file"); err == nil {
		t.Error("missing file accepted")
	}
}
