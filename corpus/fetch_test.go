// SPDX-License-Identifier: MIT

package corpus

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// The test documents are made up here; no vendor file is used.
const doc = `<?xml version="1.0"?><ISO15745Profile/>`

func blobID(b []byte) string {
	h := sha1.New()
	fmt.Fprintf(h, "blob %d\x00", len(b))
	h.Write(b)
	return hex.EncodeToString(h.Sum(nil))
}

func sum(b []byte) string { s := sha256.Sum256(b); return hex.EncodeToString(s[:]) }

func ptr[T any](v T) *T { return &v }

func zipOf(t *testing.T, files map[string]string) []byte {
	t.Helper()
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	for name, body := range files {
		w, err := zw.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		w.Write([]byte(body))
	}
	if err := zw.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

// server serves path → body over TLS and counts requests.
func server(t *testing.T, bodies map[string][]byte) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	var n atomic.Int32
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n.Add(1)
		switch r.URL.Path {
		case "/flaky":
			if n.Load() == 1 {
				w.WriteHeader(http.StatusServiceUnavailable)
				return
			}
			w.Write(bodies["/flaky"])
		case "/redirect-http":
			http.Redirect(w, r, "http://example.invalid/x", http.StatusFound)
		default:
			b, ok := bodies[r.URL.Path]
			if !ok {
				http.NotFound(w, r)
				return
			}
			w.Write(b)
		}
	}))
	t.Cleanup(srv.Close)
	return srv, &n
}

func fetcher(t *testing.T, srv *httptest.Server) *Fetcher {
	c := srv.Client()
	c.CheckRedirect = (&Fetcher{}).client().CheckRedirect
	return &Fetcher{Client: c, Cache: t.TempDir(), Backoff: time.Millisecond}
}

const commit = "0123456789abcdef0123456789abcdef01234567"

func ghEntry(srv *httptest.Server, path string, body []byte) Entry {
	return Entry{ID: "gh-" + blobID(body)[:12], Source: "github:o/r", URL: srv.URL + "/o/r/" + commit + path,
		Commit: ptr(commit), GitBlobSHA1: ptr(blobID(body)), Filename: "GSDML-V2.43-X-20260101.xml", Redistribution: "none"}
}

func TestFetchGitFile(t *testing.T) {
	t.Parallel()
	body := []byte(doc)
	srv, n := server(t, map[string][]byte{"/o/r/" + commit + "/a.xml": body})
	f := fetcher(t, srv)
	e := ghEntry(srv, "/a.xml", body)
	res, err := f.Fetch(context.Background(), []Entry{e})
	if err != nil || res[0].Err != nil || res[0].Unverified || len(res[0].Files) != 1 {
		t.Fatalf("%v %+v", err, res)
	}
	got, err := os.ReadFile(filepath.Join(f.Cache, filepath.FromSlash(res[0].Files[0].Path)))
	if err != nil || !bytes.Equal(got, body) || res[0].Files[0].SHA256 != sum(body) {
		t.Fatalf("%q %v", got, err)
	}
	idx, _ := os.ReadFile(filepath.Join(f.Cache, "index.jsonl"))
	if !strings.Contains(string(idx), res[0].Files[0].Path) {
		t.Fatalf("index %s", idx)
	}
	// Fetched again: from the cache, verified, no request.
	res, _ = f.Fetch(context.Background(), []Entry{e})
	if !res[0].Cached || res[0].Err != nil || n.Load() != 1 {
		t.Fatalf("cached %+v, %d requests", res[0], n.Load())
	}
	// A cache entry that was changed is fetched again.
	os.WriteFile(filepath.Join(f.Cache, "artifacts", e.ID), []byte("x"), 0o644)
	if res, _ = f.Fetch(context.Background(), []Entry{e}); res[0].Cached || res[0].Err != nil || n.Load() != 2 {
		t.Fatalf("tampered cache %+v", res[0])
	}
}

func TestFetchIntegrity(t *testing.T) {
	t.Parallel()
	body := []byte(doc)
	srv, _ := server(t, map[string][]byte{"/o/r/" + commit + "/a.xml": []byte(doc + " ")})
	f := fetcher(t, srv)
	res, err := f.Fetch(context.Background(), []Entry{ghEntry(srv, "/a.xml", body)})
	if err != nil || !errors.Is(res[0].Err, ErrIntegrity) || len(res[0].Files) != 0 {
		t.Fatalf("%v %+v", err, res)
	}
	// A recorded SHA-256 that does not match.
	e := Entry{ID: "vendor-000000000001", Source: "vendor", URL: srv.URL + "/o/r/" + commit + "/a.xml", SHA256: ptr(sum(body)), Filename: "a.xml", Redistribution: "none"}
	if res, _ = f.Fetch(context.Background(), []Entry{e}); !errors.Is(res[0].Err, ErrIntegrity) {
		t.Fatalf("sha256 %+v", res[0])
	}
	// The same file, recorded: verified, and its size kept.
	e.SHA256 = nil
	f.Record = true
	entries := []Entry{e}
	if res, _ = f.Fetch(context.Background(), entries); res[0].Err != nil || entries[0].SHA256 == nil || *entries[0].Size != int64(len(doc)+1) {
		t.Fatalf("record %+v %+v", res[0], entries[0])
	}
	// Without -record, an entry without a hash is fetched but unverified.
	f.Record = false
	e.SHA256 = nil
	if res, _ = f.Fetch(context.Background(), []Entry{e}); res[0].Err != nil || !res[0].Unverified {
		t.Fatalf("unverified %+v", res[0])
	}
}

func TestFetchArchive(t *testing.T) {
	t.Parallel()
	z := zipOf(t, map[string]string{
		"GSDML-V2.43-A-20260101.xml":       doc,
		`sub\GSDML-V2.35-B-20260101.XML`:   doc + "<!-- b -->",
		"readme.txt":                       "not GSDML",
		"bitmaps/GSDML-x.bmp":              "no",
		"nested/GSDML-V2.4-C-20260101.xml": doc + "<!-- c -->",
	})
	srv, _ := server(t, map[string][]byte{"/a.zip": z})
	f := fetcher(t, srv)
	f.Record = true
	entries := []Entry{{ID: "vendor-000000000002", Source: "vendor", URL: srv.URL + "/a.zip", Archive: true, Filename: "a.zip", Redistribution: "none"}}
	res, err := f.Fetch(context.Background(), entries)
	if err != nil || res[0].Err != nil || len(res[0].Files) != 3 || len(entries[0].Members) != 3 {
		t.Fatalf("%v %+v %+v", err, res, entries[0])
	}
	for _, fl := range res[0].Files {
		if strings.Count(fl.Path, "/") != 2 || fl.Member == "" {
			t.Fatalf("not flattened: %+v", fl)
		}
	}
	// Recorded members are verified: one changed member fails.
	entries[0].Members[0].SHA256 = sum([]byte("other"))
	entries[0].SHA256 = nil
	f.Record = false
	if res, _ = f.Fetch(context.Background(), entries); !errors.Is(res[0].Err, ErrIntegrity) {
		t.Fatalf("members %+v", res[0])
	}
}

func TestFetchArchiveRefused(t *testing.T) {
	t.Parallel()
	for name, z := range map[string][]byte{
		"traversal": zipOf(t, map[string]string{"../GSDML-V2.4-X-1.xml": doc}),
		"absolute":  zipOf(t, map[string]string{"/GSDML-V2.4-X-1.xml": doc}),
		"drive":     zipOf(t, map[string]string{"C:/GSDML-V2.4-X-1.xml": doc}),
		"big":       zipOf(t, map[string]string{"GSDML-V2.4-X-1.xml": strings.Repeat("x", 2048)}),
		"none":      zipOf(t, map[string]string{"readme.txt": "x"}),
		"no zip":    []byte("not a zip"),
	} {
		srv, _ := server(t, map[string][]byte{"/a.zip": z})
		f := fetcher(t, srv)
		root := t.TempDir()
		f.Cache = filepath.Join(root, "cache")
		f.MaxBytes = 1024 + int64(len(z))
		if name == "big" {
			f.MaxBytes = 1024
		}
		e := Entry{ID: "vendor-000000000003", Source: "vendor", URL: srv.URL + "/a.zip", Archive: true, Filename: "a.zip", Redistribution: "none"}
		res, err := f.Fetch(context.Background(), []Entry{e})
		if err != nil || res[0].Err == nil || len(res[0].Files) != 0 {
			t.Fatalf("%s: %v %+v", name, err, res[0])
		}
		if name == "big" && !errors.Is(res[0].Err, ErrLimit) {
			t.Fatalf("big: %v", res[0].Err)
		}
		if ents, _ := os.ReadDir(root); len(ents) != 1 || ents[0].Name() != "cache" {
			t.Fatalf("%s: wrote outside the cache: %v", name, ents)
		}
	}
}

func TestFetchHTTP(t *testing.T) {
	t.Parallel()
	body := []byte(doc)
	big := bytes.Repeat([]byte("x"), 4096)
	srv, n := server(t, map[string][]byte{"/flaky": body, "/big": big})
	f := fetcher(t, srv)
	vendor := func(path string) Entry {
		return Entry{ID: "vendor-000000000004", Source: "vendor", URL: srv.URL + path, Filename: "a.xml", Redistribution: "none"}
	}
	// A 503 is retried.
	if res, _ := f.Fetch(context.Background(), []Entry{vendor("/flaky")}); res[0].Err != nil || n.Load() != 2 {
		t.Fatalf("retry %+v, %d requests", res[0], n.Load())
	}
	// A 404 is not.
	if res, _ := f.Fetch(context.Background(), []Entry{vendor("/missing")}); res[0].Err == nil || n.Load() != 3 {
		t.Fatalf("404 %+v, %d requests", res[0], n.Load())
	}
	// A download beyond MaxBytes.
	f.MaxBytes = 1024
	if res, _ := f.Fetch(context.Background(), []Entry{vendor("/big")}); !errors.Is(res[0].Err, ErrLimit) {
		t.Fatalf("big %+v", res[0])
	}
	// A redirect away from https.
	if res, _ := f.Fetch(context.Background(), []Entry{vendor("/redirect-http")}); res[0].Err == nil || !strings.Contains(res[0].Err.Error(), "not https") {
		t.Fatalf("redirect %+v", res[0])
	}
	// A cancelled context.
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if res, _ := f.Fetch(ctx, []Entry{vendor("/flaky")}); res[0].Err == nil {
		t.Fatalf("cancelled %+v", res[0])
	}
}

func TestSafeName(t *testing.T) {
	t.Parallel()
	for in, want := range map[string]string{"a/b": "a_b", `a\b`: "a_b", "..": "_", "": "_", "C:x": "C_x", "a\x00b": "a_b", "GSDML V2.4.xml": "GSDML V2.4.xml"} {
		if got := safeName(in); got != want {
			t.Errorf("%q: %q, want %q", in, got, want)
		}
	}
}
