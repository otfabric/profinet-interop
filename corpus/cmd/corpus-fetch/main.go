// SPDX-License-Identifier: MIT

// corpus-fetch downloads the GSDML corpus of a manifest into a local cache
// that is never committed or published (docs/CORPUS.md).
//
// Exit status: 0 when every entry was fetched and verified, 1 when one
// failed or (with -strict) was not verified, 2 for a usage or cache error.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"time"

	"github.com/otfabric/profinet-interop/corpus"
)

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("corpus-fetch", flag.ContinueOnError)
	fs.SetOutput(stderr)
	manifest := fs.String("manifest", "corpus/manifest.jsonl", "the manifest")
	cache := fs.String("cache", defaultCache(), "the cache directory")
	record := fs.Bool("record", false, "record the SHA-256, size and archive members of entries that have none, and rewrite the manifest")
	strict := fs.Bool("strict", false, "fail on an entry that could not be verified")
	only := fs.String("only", "", "comma-separated IDs to fetch, all when empty")
	jobs := fs.Int("jobs", 4, "concurrent downloads")
	maxBytes := fs.Int64("max-bytes", corpus.DefaultMaxBytes, "the largest download and archive member, in octets")
	timeout := fs.Duration("timeout", 30*time.Minute, "the whole fetch")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if fs.NArg() > 0 || *cache == "" || *jobs < 1 || *maxBytes < 1 {
		fmt.Fprintln(stderr, "usage: corpus-fetch [-manifest FILE] [-cache DIR] [-record] [-strict] [-only IDS] [-jobs N]")
		return 2
	}
	entries, err := corpus.ReadManifestFile(*manifest)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	selected := entries
	if *only != "" {
		want := map[string]bool{}
		for _, id := range strings.Split(*only, ",") {
			want[strings.TrimSpace(id)] = true
		}
		selected = nil
		for _, e := range entries {
			if want[e.ID] {
				selected = append(selected, e)
				delete(want, e.ID)
			}
		}
		if len(want) > 0 {
			fmt.Fprintf(stderr, "-only: %d IDs not in the manifest\n", len(want))
			return 2
		}
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	ctx, cancel := context.WithTimeout(ctx, *timeout)
	defer cancel()
	f := &corpus.Fetcher{Cache: *cache, MaxBytes: *maxBytes, Record: *record, Jobs: *jobs}
	results, err := f.Fetch(ctx, selected)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}
	failed, unverified, files := 0, 0, 0
	for _, r := range results {
		switch {
		case r.Err != nil:
			failed++
			fmt.Fprintf(stderr, "FAIL %s: %v\n", r.ID, r.Err)
		case r.Unverified:
			unverified++
			fmt.Fprintf(stderr, "UNVERIFIED %s: no recorded sha256 (-record records it)\n", r.ID)
		}
		files += len(r.Files)
	}
	if *record {
		byID := map[string]corpus.Entry{}
		for _, e := range selected {
			byID[e.ID] = e
		}
		for i, e := range entries {
			if r, ok := byID[e.ID]; ok {
				entries[i] = r
			}
		}
		if err := rewrite(*manifest, entries); err != nil {
			fmt.Fprintln(stderr, err)
			return 2
		}
	}
	fmt.Fprintf(stdout, "%d entries: %d fetched, %d failed, %d unverified; %d GSDML files in %s\n",
		len(results), len(results)-failed, failed, unverified, files, filepath.Join(*cache, "index.jsonl"))
	if failed > 0 || (*strict && unverified > 0) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return 1
	}
	return 0
}

func rewrite(name string, entries []corpus.Entry) error {
	tmp := name + ".tmp"
	f, err := os.Create(tmp)
	if err != nil {
		return err
	}
	if err := corpus.WriteManifest(f, entries); err != nil {
		f.Close()
		os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, name)
}

// defaultCache is $XDG_CACHE_HOME/otfabric/gsdml-corpus, or the system's
// user cache directory.
func defaultCache() string {
	if d := os.Getenv("XDG_CACHE_HOME"); d != "" {
		return filepath.Join(d, "otfabric", "gsdml-corpus")
	}
	if d, err := os.UserCacheDir(); err == nil {
		return filepath.Join(d, "otfabric", "gsdml-corpus")
	}
	return ""
}
