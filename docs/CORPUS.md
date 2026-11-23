# GSDML corpus

A list of public GSDML files and archives, and a tool that downloads
them into a local cache, so that a consumer can test its GSDML handling
against files it did not write. **No vendor file is in this repository**,
and none is published by it: what the tool fetches stays in the user's
cache.

Like the adapters, this part knows no library under test (REQUIREMENTS.md
R1): it fetches and verifies files, and a consumer runs its own checks over
the cache (`index.jsonl`).

## The manifest

`corpus/manifest.jsonl` has one JSON object per line, sorted by `id`:

| Field | Meaning |
|---|---|
| `id` | `gh-<first 12 hex of the git blob ID>` for a file in a git repository, `vendor-<first 12 hex of the SHA-1 of the URL>` for a vendor download |
| `source`, `source_page` | where the file was found: `github:owner/repo`, or `vendor` |
| `url` | the https URL fetched |
| `commit` | the commit a git source is pinned to (never a branch) |
| `git_blob_sha1` | the git blob ID of a git source; every fetch verifies it |
| `sha256`, `size` | the artifact as first fetched, recorded with `-record`; null until then; every later fetch verifies them |
| `archive`, `members` | a zip archive, and its GSDML members (name, SHA-256, size) as recorded |
| `filename`, `manufacturer`, `product`, `gsdml_version` | as found; the version is taken from the file name, not parsed |
| `provenance` | how the file reached its source: `vendor file copied into a third-party repository`, `vendor download page` |
| `redistribution` | none: no source states terms that allow it, and a repository's licence does not relicense a vendor's file copied into it |

The 191 entries are the distinct artifacts of the 473 candidates of
go-profinet's research (docs/research/gsdml-corpus/candidates.jsonl there)
that have a URL: 132 artifacts in 32 GitHub repositories pinned to commits
(130 files and 2 zip archives), and 59 open vendor downloads (58 of them
zip archives). Candidates behind a
login, an email form, JavaScript only or an unreachable host are left out.

## Fetching

Downloading the corpus is the user's decision (licence and network
policy): nothing downloads it implicitly, no workflow runs it on a
schedule, and CI never depends on it.

```bash
make corpus-fetch                          # every entry
make corpus-fetch CORPUS_FLAGS="-only gh-0696f031295a,vendor-…"
make corpus-fetch CORPUS_FLAGS="-record"   # record the SHA-256 of entries that have none, rewriting the manifest
```

The cache is `$XDG_CACHE_HOME/otfabric/gsdml-corpus` (or the system's user
cache directory; `CORPUS_CACHE=dir` overrides it):

```text
artifacts/<id>        the artifact as downloaded
gsdml/<id>/<name>     its GSDML files (an archive's members, their paths flattened into one name)
index.jsonl           one line per GSDML file: id, path, sha256, size, member, url, source
```

An artifact already in the cache is not downloaded again when it verifies
against the manifest (its git blob ID, or a recorded SHA-256).

Exit status: 0 when every entry was fetched and verified, 1 when one
failed (or, with `-strict`, could not be verified: a vendor download whose
SHA-256 is not recorded yet), 2 for a usage, manifest or cache error. The
index lists the files of the entries that succeeded.

## Limits

Everything fetched is untrusted:

- https only, redirects too, at most five; two minutes a download.
- A download or archive member of at most 64 MiB (`-max-bytes`); an
  archive of at most 4096 entries, its GSDML members together at most four
  times the member limit.
- Only regular members named `GSDML-*.xml` (any case) are extracted. A
  member path that is absolute, has a drive letter or climbs out (`..`)
  fails the archive; member paths are flattened into one file name, so no
  member can write outside its directory.
- A failed download is retried twice (network errors, 429 and 5xx).
- A generic User-Agent (`profinet-interop-corpus-fetch`); nothing about
  the user is sent.

The fetch does not parse the files; a consumer parses them, in a process
of its own with a timeout.
