// SPDX-License-Identifier: MIT

package corpus

import (
	"archive/zip"
	"bytes"
	"context"
	"crypto/sha1" // git blob IDs are SHA-1
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"
)

// Limits of a fetch. Files from the internet are untrusted: every size is
// bounded before it is read.
const (
	// DefaultMaxBytes bounds one download and one archive member: the
	// largest known GSDML file is about 40 MB.
	DefaultMaxBytes = 64 << 20
	// MaxMembers bounds the entries of one archive.
	MaxMembers = 4096
	// maxRedirects bounds the redirects of one download.
	maxRedirects = 5
)

// gsdmlName is the name of a GSDML file in an archive.
var gsdmlName = regexp.MustCompile(`(?i)^gsdml-.*\.xml$`)

// Fetcher downloads the entries of a manifest into Cache.
type Fetcher struct {
	// Client is the HTTP client; nil for one that follows at most five
	// https redirects and times out a download after two minutes.
	Client *http.Client
	// Cache is the cache directory: artifacts/<id> holds what was
	// downloaded, gsdml/<id>/ the GSDML files, index.jsonl the list.
	Cache string
	// MaxBytes bounds a download and an archive member (DefaultMaxBytes
	// when 0); an archive's GSDML members together get four times it.
	MaxBytes int64
	// Record fills in the SHA-256, size and members of entries that have
	// none; without it an entry without them is fetched but reported
	// unverified.
	Record bool
	// Jobs is the number of concurrent downloads (4 when 0).
	Jobs int
	// Retries is the number of retries of a download that failed on the
	// network or with a 429 or 5xx status (2 when 0, none when negative).
	Retries int
	// Backoff is the wait before the first retry, doubled for each next
	// (2 s when 0).
	Backoff time.Duration
}

// File is a GSDML file in the cache.
type File struct {
	ID     string `json:"id"`
	Path   string `json:"path"` // relative to the cache, with slashes
	SHA256 string `json:"sha256"`
	Size   int64  `json:"size"`
	Member string `json:"member,omitempty"` // the name in the archive
	URL    string `json:"url"`
	Source string `json:"source"`
}

// Result is the fetch of one entry.
type Result struct {
	ID string
	// Files are the GSDML files of the entry; Err why there are none.
	Files []File
	Err   error
	// Unverified: the entry has no recorded SHA-256 and Record was off.
	Unverified bool
	// Cached: the artifact was in the cache already and verified.
	Cached bool
}

// ErrIntegrity is the error of an artifact that does not match its
// manifest entry.
var ErrIntegrity = errors.New("integrity check failed")

// ErrLimit is the error of an artifact beyond a limit of the fetch.
var ErrLimit = errors.New("limit exceeded")

func (f *Fetcher) maxBytes() int64 {
	if f.MaxBytes > 0 {
		return f.MaxBytes
	}
	return DefaultMaxBytes
}

func (f *Fetcher) client() *http.Client {
	if f.Client != nil {
		return f.Client
	}
	return &http.Client{
		Timeout: 2 * time.Minute,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			if len(via) >= maxRedirects {
				return fmt.Errorf("more than %d redirects", maxRedirects)
			}
			if req.URL.Scheme != "https" {
				return fmt.Errorf("redirect to %s, not https", req.URL.Redacted())
			}
			return nil
		},
	}
}

// Fetch fetches every entry, updating the entries' recorded hashes when
// Record is set, and writes index.jsonl with the files of the entries that
// succeeded. One result per entry, in the order of entries; the error is
// only that of the cache itself.
func (f *Fetcher) Fetch(ctx context.Context, entries []Entry) ([]Result, error) {
	for _, d := range []string{"artifacts", "gsdml"} {
		if err := os.MkdirAll(filepath.Join(f.Cache, d), 0o755); err != nil {
			return nil, err
		}
	}
	jobs := f.Jobs
	if jobs <= 0 {
		jobs = 4
	}
	results := make([]Result, len(entries))
	sem := make(chan struct{}, jobs)
	var wg sync.WaitGroup
	for i := range entries {
		wg.Add(1)
		go func() {
			defer wg.Done()
			select {
			case sem <- struct{}{}:
			case <-ctx.Done():
				results[i] = Result{ID: entries[i].ID, Err: ctx.Err()}
				return
			}
			defer func() { <-sem }()
			results[i] = f.fetchOne(ctx, &entries[i])
		}()
	}
	wg.Wait()
	var files []File
	for _, r := range results {
		if r.Err == nil {
			files = append(files, r.Files...)
		}
	}
	sort.Slice(files, func(i, j int) bool { return files[i].Path < files[j].Path })
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	for _, fl := range files {
		if err := enc.Encode(fl); err != nil {
			return results, err
		}
	}
	return results, writeAtomic(filepath.Join(f.Cache, "index.jsonl"), buf.Bytes())
}

func (f *Fetcher) fetchOne(ctx context.Context, e *Entry) Result {
	r := Result{ID: e.ID}
	artifact := filepath.Join(f.Cache, "artifacts", e.ID)
	data, err := os.ReadFile(artifact)
	if err == nil && (e.SHA256 != nil || e.GitBlobSHA1 != nil) && verify(e, data) == nil {
		r.Cached = true
	} else {
		if data, err = f.download(ctx, e.URL); err != nil {
			r.Err = err
			return r
		}
		if err := verify(e, data); err != nil {
			r.Err = err
			return r
		}
		if err := writeAtomic(artifact, data); err != nil {
			r.Err = err
			return r
		}
	}
	sum := sha256.Sum256(data)
	if e.SHA256 == nil {
		if f.Record {
			s, n := hex.EncodeToString(sum[:]), int64(len(data))
			e.SHA256, e.Size = &s, &n
		} else if e.GitBlobSHA1 == nil {
			r.Unverified = true
		}
	}
	dir := filepath.Join(f.Cache, "gsdml", e.ID)
	if err := os.RemoveAll(dir); err != nil {
		r.Err = err
		return r
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		r.Err = err
		return r
	}
	if !e.Archive {
		name := safeName(e.Filename)
		if !strings.HasSuffix(strings.ToLower(name), ".xml") {
			name += ".xml"
		}
		if err := writeAtomic(filepath.Join(dir, name), data); err != nil {
			r.Err = err
			return r
		}
		r.Files = []File{{ID: e.ID, Path: "gsdml/" + e.ID + "/" + name, SHA256: hex.EncodeToString(sum[:]), Size: int64(len(data)), URL: e.URL, Source: e.Source}}
		return r
	}
	members, files, err := f.unzip(data, dir, e)
	if err != nil {
		r.Err = err
		return r
	}
	switch {
	case len(e.Members) == 0 && f.Record:
		e.Members = members
	case len(e.Members) > 0:
		if err := sameMembers(e.Members, members); err != nil {
			r.Err = fmt.Errorf("%s: %w: %v", e.ID, ErrIntegrity, err)
			return r
		}
	}
	if len(files) == 0 {
		r.Err = fmt.Errorf("%s: the archive holds no GSDML-*.xml file", e.ID)
		return r
	}
	r.Files = files
	return r
}

// verify checks data against what the entry records: its git blob ID, its
// SHA-256 and size.
func verify(e *Entry, data []byte) error {
	if e.GitBlobSHA1 != nil {
		h := sha1.New()
		fmt.Fprintf(h, "blob %d\x00", len(data))
		h.Write(data)
		if got := hex.EncodeToString(h.Sum(nil)); got != *e.GitBlobSHA1 {
			return fmt.Errorf("%s: %w: git blob %s, the manifest has %s", e.ID, ErrIntegrity, got, *e.GitBlobSHA1)
		}
	}
	if e.SHA256 != nil {
		sum := sha256.Sum256(data)
		if got := hex.EncodeToString(sum[:]); got != *e.SHA256 {
			return fmt.Errorf("%s: %w: sha256 %s, the manifest has %s", e.ID, ErrIntegrity, got, *e.SHA256)
		}
	}
	if e.Size != nil && int64(len(data)) != *e.Size {
		return fmt.Errorf("%s: %w: %d octets, the manifest has %d", e.ID, ErrIntegrity, len(data), *e.Size)
	}
	return nil
}

func (f *Fetcher) download(ctx context.Context, url string) ([]byte, error) {
	retries := f.Retries
	if retries == 0 {
		retries = 2
	}
	if retries < 0 {
		retries = 0
	}
	wait := f.Backoff
	if wait <= 0 {
		wait = 2 * time.Second
	}
	for attempt := 0; ; attempt++ {
		data, retry, err := f.get(ctx, url)
		if err == nil || !retry || attempt >= retries {
			return data, err
		}
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(wait):
		}
		wait *= 2
	}
}

// get downloads url once; retry reports an error worth retrying.
func (f *Fetcher) get(ctx context.Context, url string) (data []byte, retry bool, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, false, err
	}
	// A generic client name: nothing about the user.
	req.Header.Set("User-Agent", "profinet-interop-corpus-fetch")
	resp, err := f.client().Do(req)
	if err != nil {
		return nil, ctx.Err() == nil, fmt.Errorf("GET %s: %w", url, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500, fmt.Errorf("GET %s: %s", url, resp.Status)
	}
	limit := f.maxBytes()
	if resp.ContentLength > limit {
		return nil, false, fmt.Errorf("GET %s: %w: %d octets, more than %d", url, ErrLimit, resp.ContentLength, limit)
	}
	data, err = io.ReadAll(io.LimitReader(resp.Body, limit+1))
	if err != nil {
		return nil, ctx.Err() == nil, fmt.Errorf("GET %s: %w", url, err)
	}
	if int64(len(data)) > limit {
		return nil, false, fmt.Errorf("GET %s: %w: more than %d octets", url, ErrLimit, limit)
	}
	return data, false, nil
}

// unzip extracts the GSDML members of an archive into dir, flattened: a
// member's path becomes one file name, so no member can write outside dir.
func (f *Fetcher) unzip(data []byte, dir string, e *Entry) ([]Member, []File, error) {
	zr, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return nil, nil, fmt.Errorf("%s: not a zip archive: %w", e.ID, err)
	}
	if len(zr.File) > MaxMembers {
		return nil, nil, fmt.Errorf("%s: %w: %d archive entries, more than %d", e.ID, ErrLimit, len(zr.File), MaxMembers)
	}
	limit := f.maxBytes()
	total := int64(0)
	var members []Member
	var files []File
	seen := map[string]bool{}
	for _, zf := range zr.File {
		name := strings.ReplaceAll(zf.Name, `\`, "/")
		if !zf.Mode().IsRegular() || !gsdmlName.MatchString(path.Base(name)) {
			continue
		}
		clean := path.Clean(name)
		if path.IsAbs(clean) || clean == ".." || strings.HasPrefix(clean, "../") || strings.Contains(clean, ":") {
			return nil, nil, fmt.Errorf("%s: archive member %q: unsafe path", e.ID, zf.Name)
		}
		if zf.UncompressedSize64 > uint64(limit) {
			return nil, nil, fmt.Errorf("%s: %w: archive member %q of %d octets", e.ID, ErrLimit, zf.Name, zf.UncompressedSize64)
		}
		rc, err := zf.Open()
		if err != nil {
			return nil, nil, fmt.Errorf("%s: archive member %q: %w", e.ID, zf.Name, err)
		}
		b, err := io.ReadAll(io.LimitReader(rc, limit+1))
		rc.Close()
		if err != nil {
			return nil, nil, fmt.Errorf("%s: archive member %q: %w", e.ID, zf.Name, err)
		}
		if int64(len(b)) > limit {
			return nil, nil, fmt.Errorf("%s: %w: archive member %q of more than %d octets", e.ID, ErrLimit, zf.Name, limit)
		}
		if total += int64(len(b)); total > 4*limit {
			return nil, nil, fmt.Errorf("%s: %w: GSDML members of more than %d octets", e.ID, ErrLimit, 4*limit)
		}
		flat := safeName(strings.ReplaceAll(clean, "/", "__"))
		if seen[flat] {
			return nil, nil, fmt.Errorf("%s: archive member %q twice", e.ID, clean)
		}
		seen[flat] = true
		if err := writeAtomic(filepath.Join(dir, flat), b); err != nil {
			return nil, nil, err
		}
		sum := sha256.Sum256(b)
		s := hex.EncodeToString(sum[:])
		members = append(members, Member{Name: clean, SHA256: s, Size: int64(len(b))})
		files = append(files, File{ID: e.ID, Path: "gsdml/" + e.ID + "/" + flat, SHA256: s, Size: int64(len(b)), Member: clean, URL: e.URL, Source: e.Source})
	}
	sort.Slice(members, func(i, j int) bool { return members[i].Name < members[j].Name })
	return members, files, nil
}

func sameMembers(want, got []Member) error {
	w := map[string]Member{}
	for _, m := range want {
		w[m.Name] = m
	}
	if len(want) != len(got) {
		return fmt.Errorf("%d GSDML members, the manifest has %d", len(got), len(want))
	}
	for _, m := range got {
		if r, ok := w[m.Name]; !ok || r != m {
			return fmt.Errorf("member %q differs from the manifest", m.Name)
		}
	}
	return nil
}

// safeName is a file name with the characters that are unsafe in a path
// on any system replaced.
func safeName(s string) string {
	s = strings.Map(func(r rune) rune {
		switch {
		case r < 0x20, strings.ContainsRune(`/\:*?"<>|`, r):
			return '_'
		}
		return r
	}, s)
	if s == "" || s == "." || s == ".." {
		return "_"
	}
	return s
}

func writeAtomic(name string, data []byte) error {
	tmp, err := os.CreateTemp(filepath.Dir(name), ".tmp-*")
	if err != nil {
		return err
	}
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		os.Remove(tmp.Name())
		return err
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmp.Name())
		return err
	}
	return os.Rename(tmp.Name(), name)
}
