// SPDX-License-Identifier: MIT

// Package corpus fetches the GSDML corpus of manifest.jsonl into a local
// cache that is never committed or published (docs/CORPUS.md).
package corpus

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"regexp"
	"sort"
	"strings"
)

// Entry is one line of the manifest: one artifact, a GSDML file or a zip
// archive that holds GSDML files.
type Entry struct {
	// ID is stable and unique: gh-<git blob prefix> for a file in a git
	// repository, vendor-<URL hash prefix> for a vendor download.
	ID         string `json:"id"`
	Source     string `json:"source"`
	URL        string `json:"url"`
	SourcePage string `json:"source_page"`
	// Commit pins a git source; a branch is never used.
	Commit *string `json:"commit"`
	// GitBlobSHA1 is the git blob ID of a file in a git repository, known
	// before it is fetched: the fetch verifies it.
	GitBlobSHA1 *string `json:"git_blob_sha1"`
	// SHA256 and Size are those of the artifact as fetched. Null until it
	// was first fetched with -record; then every fetch verifies them.
	SHA256 *string `json:"sha256"`
	Size   *int64  `json:"size"`
	// Archive is a zip archive; Members are its GSDML files, recorded
	// with -record.
	Archive bool     `json:"archive"`
	Members []Member `json:"members,omitempty"`

	Filename       string  `json:"filename"`
	Manufacturer   string  `json:"manufacturer"`
	Product        *string `json:"product"`
	GSDMLVersion   *string `json:"gsdml_version"`
	Provenance     string  `json:"provenance"`
	Redistribution string  `json:"redistribution"`
}

// Member is a GSDML file in an archive.
type Member struct {
	Name   string `json:"name"`
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
}

var (
	idPattern  = regexp.MustCompile(`^(gh|vendor)-[0-9a-f]{12}$`)
	hexPattern = regexp.MustCompile(`^[0-9a-f]+$`)
	commitPin  = regexp.MustCompile(`/[0-9a-f]{40}/`)
)

// Check reports what makes an entry unusable: a missing or malformed
// field, a URL that is not https, a git source not pinned to a commit.
func (e *Entry) Check() error {
	if !idPattern.MatchString(e.ID) {
		return fmt.Errorf("id %q: not gh-<12 hex> or vendor-<12 hex>", e.ID)
	}
	u, err := url.Parse(e.URL)
	if err != nil || u.Scheme != "https" || u.Host == "" {
		return fmt.Errorf("%s: url %q is not https", e.ID, e.URL)
	}
	if strings.HasPrefix(e.Source, "github:") {
		if e.Commit == nil || len(*e.Commit) != 40 || !hexPattern.MatchString(*e.Commit) {
			return fmt.Errorf("%s: a git source needs a 40-hex commit", e.ID)
		}
		if !commitPin.MatchString(u.Path) || !strings.Contains(u.Path, "/"+*e.Commit+"/") {
			return fmt.Errorf("%s: url is not pinned to commit %s", e.ID, *e.Commit)
		}
		if e.GitBlobSHA1 == nil || len(*e.GitBlobSHA1) != 40 || !hexPattern.MatchString(*e.GitBlobSHA1) {
			return fmt.Errorf("%s: a git source needs its 40-hex blob ID", e.ID)
		}
	}
	if e.SHA256 != nil && (len(*e.SHA256) != 64 || !hexPattern.MatchString(*e.SHA256)) {
		return fmt.Errorf("%s: sha256 %q is not 64 hex", e.ID, *e.SHA256)
	}
	if !e.Archive && len(e.Members) > 0 {
		return fmt.Errorf("%s: members of a file that is no archive", e.ID)
	}
	if e.Redistribution == "" {
		return fmt.Errorf("%s: no redistribution statement", e.ID)
	}
	return nil
}

// ReadManifest reads a manifest and checks every entry, and that the IDs
// are unique.
func ReadManifest(r io.Reader) ([]Entry, error) {
	var out []Entry
	seen := map[string]bool{}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64<<10), 1<<20)
	for n := 1; sc.Scan(); n++ {
		line := bytes.TrimSpace(sc.Bytes())
		if len(line) == 0 {
			continue
		}
		var e Entry
		dec := json.NewDecoder(bytes.NewReader(line))
		dec.DisallowUnknownFields()
		if err := dec.Decode(&e); err != nil {
			return nil, fmt.Errorf("manifest line %d: %w", n, err)
		}
		if err := e.Check(); err != nil {
			return nil, fmt.Errorf("manifest line %d: %w", n, err)
		}
		if seen[e.ID] {
			return nil, fmt.Errorf("manifest line %d: duplicate id %s", n, e.ID)
		}
		seen[e.ID] = true
		out = append(out, e)
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("manifest: %w", err)
	}
	if len(out) == 0 {
		return nil, errors.New("manifest: no entries")
	}
	return out, nil
}

// ReadManifestFile reads the manifest at path.
func ReadManifestFile(path string) ([]Entry, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return ReadManifest(f)
}

// WriteManifest writes entries one per line, sorted by ID, with sorted
// keys, as the committed file is.
func WriteManifest(w io.Writer, entries []Entry) error {
	sorted := append([]Entry(nil), entries...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].ID < sorted[j].ID })
	for _, e := range sorted {
		b, err := json.Marshal(e)
		if err != nil {
			return err
		}
		// Sorted keys: through a map, which encoding/json sorts.
		var m map[string]any
		if err := json.Unmarshal(b, &m); err != nil {
			return err
		}
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		enc.SetEscapeHTML(false)
		if err := enc.Encode(m); err != nil {
			return err
		}
		if _, err := w.Write(buf.Bytes()); err != nil {
			return err
		}
	}
	return nil
}
