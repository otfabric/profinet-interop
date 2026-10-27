#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compares the upstream pin of every adapter with the latest upstream.

    scripts/latest-upstream.py <adapter>
    scripts/latest-upstream.py [--json FILE] [--markdown FILE]

With an adapter, prints key=value lines (the format of $GITHUB_OUTPUT):

    pin=<UPSTREAM_VERSION of the adapter Dockerfile, or the short commit>
    pin_sha=<UPSTREAM_SHA of the adapter Dockerfile, where it has one>
    latest=<the latest upstream, as a label of the same form as the pin>
    latest_sha=<its commit, where it is known>
    latest_sha256=<the sha256 of its wheel (pnio-dcp only)>
    update=yes|no|unknown
    candidate=yes|no   (whether make candidate-<adapter> can build it)
    flag=<a reason not to take the latest at face value, or nothing>
    source=<where the latest upstream was looked up>
    note=<anything worth knowing about that lookup, or nothing>

Without one, looks up every adapter and prints the decision table as
Markdown (for a Job Summary); --json writes the same as JSON, --markdown
the table to a file.

How each upstream is looked up:

- p-net (pinned by commit, the last complete GPLv3 tree): the newest GPL
  release tag (vX.Y.Z) of rtlabs-com/p-net is compared with the pin by
  commit date; update = a GPL release newer than the pin exists. The head
  of the default branch and the "public/" releases are reported but
  flagged: they are evaluation snapshots without ports, not GPL-complete,
  and are never a candidate by themselves.
- pnio-rs (pinned by tag and commit): the newest GitHub release (else
  tag) of core-engineering/pnio-rs; the head of main is reported.
- profinet-py, pnio-dcp, scapy (pinned by version): the newest stable,
  non-yanked PyPI release; for pnio-dcp also the sha256 of its wheel.
- tshark: the Debian bookworm package (Debian's madison service); the
  image installs whatever bookworm ships when it is built, so it is pinned
  by Debian: reported, never a candidate build.

Pre-releases are never "latest". GITHUB_TOKEN, when set, authenticates
GitHub API calls. A failed lookup makes that adapter "unknown" without
stopping the others. Exit status: 0 when every lookup succeeded, 1 when
any is unknown (everything else is still printed), 2 on a usage error.
Nothing is modified.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = "profinet-interop latest-upstream (https://github.com/otfabric/profinet-interop)"
ADAPTERS = ["pnet", "pnio-rs", "profinet-py", "pnio-dcp", "scapy", "tshark"]


def fetch(url):
    headers = {"User-Agent": AGENT, "Accept": "application/json, */*"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode()


def fetch_json(url):
    return json.loads(fetch(url))


def key(version):
    """Sort key of a stable version (v1.2.3 or 1.2.3); None for anything else."""
    match = re.fullmatch(r"[vV]?(\d+(?:\.\d+)*)", version)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def newest(versions):
    found = [v for v in versions if key(v) is not None]
    if not found:
        raise LookupError("no release found upstream")
    return max(found, key=key)


def git_refs(repository):
    """Refs of repository: ({tag: commit}, head commit, default branch)."""
    out = subprocess.check_output(["git", "ls-remote", "--symref", repository], text=True, timeout=60)
    tags, head, branch = {}, "", ""
    for line in out.splitlines():
        if line.startswith("ref: "):
            branch = line.split()[1].removeprefix("refs/heads/")
            continue
        sha, ref = line.split()
        if ref == "HEAD":
            head = sha
        elif ref.startswith("refs/tags/"):
            tag = ref.removeprefix("refs/tags/")
            if tag.endswith("^{}"):
                tags[tag[:-3]] = sha
            else:
                tags.setdefault(tag, sha)
    return tags, head, branch


def tag_commit(repository, version):
    """The commit of the release tag of version (v1.2.3 or 1.2.3), or ""."""
    try:
        tags, _, _ = git_refs(repository)
    except (OSError, subprocess.SubprocessError):
        return ""
    for tag in (f"v{version}", version, f"V{version}"):
        if tag in tags:
            return tags[tag]
    return ""


def commit_date(slug, sha):
    """The commit date (YYYY-MM-DD) of sha in the GitHub repository slug."""
    commit = fetch_json(f"https://api.github.com/repos/{slug}/commits/{sha}")
    return commit["commit"]["committer"]["date"][:10]


def result(latest, latest_sha="", source="", note="", update=None, candidate=True, flag="", latest_sha256=""):
    return {"latest": latest, "latest_sha": latest_sha, "latest_sha256": latest_sha256, "update": update,
            "candidate": candidate, "flag": flag, "source": source, "note": note}


# ── Pinned by commit ──────────────────────────────────────────────────────────

def pnet(pin):
    slug = "rtlabs-com/p-net"
    tags, head, branch = git_refs(f"https://github.com/{slug}.git")
    pin_date = commit_date(slug, pin["pin_sha"])
    notes = [f"pin {pin['pin_sha'][:7]} ({pin_date}), the last complete GPLv3 tree"]
    gpl = [t for t in tags if key(t) is not None]
    newer = []
    for tag in gpl:
        if commit_date(slug, tags[tag]) > pin_date:
            newer.append(tag)
    if gpl:
        tag = newest(gpl)
        notes.append(f"newest GPL release tag {tag} ({commit_date(slug, tags[tag])})")
    flags = []
    snapshots = [t.removeprefix("public/") for t in tags if t.startswith("public/") and key(t.removeprefix("public/"))]
    if snapshots:
        snap = "public/" + newest(snapshots)
        flags.append(f"release {snap} ({commit_date(slug, tags[snap])})")
    if head and head != pin["pin_sha"]:
        flags.append(f"head {head[:7]} of {branch or 'the default branch'} ({commit_date(slug, head)})")
    flag = ""
    if flags:
        flag = " and ".join(flags) + " are evaluation snapshots without ports, not GPL-complete: not a candidate"
    if newer:
        latest = newest(newer)
        return result(latest, tags[latest], f"GPL release tags of {slug}", "; ".join(notes), update=True, flag=flag)
    notes.append("no GPL release newer than the pin")
    return result(pin["pin"], pin["pin_sha"], f"GPL release tags of {slug}", "; ".join(notes), update=False, flag=flag)


# ── Pinned by release ─────────────────────────────────────────────────────────

def pnio_rs(pin):
    slug = "core-engineering/pnio-rs"
    tags, head, branch = git_refs(f"https://github.com/{slug}.git")
    source = f"GitHub releases of {slug}"
    try:
        releases = fetch_json(f"https://api.github.com/repos/{slug}/releases?per_page=100")
        names = [r["tag_name"] for r in releases if not r.get("draft") and not r.get("prerelease")]
        latest = newest(names)
    except (OSError, ValueError, LookupError, KeyError):
        latest, source = newest(tags), f"git tags of {slug}"
    notes = []
    if head and head != tags.get(latest):
        notes.append(f"head {head[:7]} of {branch or 'the default branch'} is past {latest}")
    return result(latest, tags.get(latest, ""), source, "; ".join(notes), update=latest != pin["pin"])


def pypi_releases(package):
    meta = fetch_json(f"https://pypi.org/pypi/{package}/json")
    live = [v for v, files in meta["releases"].items() if files and not all(f.get("yanked") for f in files)]
    return newest(live), meta["releases"]


def pypi(package, repository, pin):
    latest, _ = pypi_releases(package)
    sha = tag_commit(repository, latest) if repository else ""
    note = "" if sha or not repository else f"no git tag for {latest}: find its commit by hand"
    return result(latest, sha, "PyPI", note, update=latest != pin["pin"])


def profinet_py(pin):
    return pypi("profinet-py", "https://github.com/f0rw4rd/profinet-py.git", pin)


def scapy(pin):
    return pypi("scapy", "https://github.com/secdev/scapy.git", pin)


def pnio_dcp(pin):
    latest, releases = pypi_releases("pnio-dcp")
    files = releases[latest]
    wheels = [f for f in files if f["packagetype"] == "bdist_wheel"]
    sdists = [f for f in files if f["packagetype"] == "sdist"]
    sha256 = (wheels or sdists or [{}])[0].get("digests", {}).get("sha256", "")
    notes = [f"{f['filename']} sha256 {f['digests']['sha256']}" for f in wheels + sdists]
    if latest == pin["pin"] and wheels and sha256 != pin.get("pin_sha256"):
        notes.append("the wheel hash of the pin differs from the Dockerfile's UPSTREAM_SHA256")
    return result(latest, "", "PyPI", "; ".join(notes), update=latest != pin["pin"], latest_sha256=sha256)


# ── Pinned by Debian ──────────────────────────────────────────────────────────

def debian_key(version):
    upstream = version.split(":", 1)[-1].rsplit("-", 1)[0]
    return (key(upstream) or (), version)


def tshark(pin):
    note = "pinned by Debian: the image installs the bookworm package current at build time, so a rebuild picks it up"
    try:
        data = fetch_json("https://api.ftp-master.debian.org/madison?package=wireshark"
                          "&s=bookworm,bookworm-security,bookworm-updates&f=json")
        versions = [v for entry in data for suites in entry.get("wireshark", {}).values() for v in suites]
        package = max(versions, key=debian_key)
    except (OSError, ValueError, KeyError) as error:
        return result("unknown", "", "Debian bookworm (madison)", f"{note}; package version not determinable ({error})",
                      update=None, candidate=False)
    latest = package.split(":", 1)[-1].rsplit("-", 1)[0]
    if latest != pin["pin"]:
        note += f"; versions.yaml records {pin['pin']}: update it"
    return result(latest, "", "Debian bookworm (madison)", f"{note}; package {package}",
                  update=latest != pin["pin"], candidate=False)


LOOKUPS = {
    "pnet": pnet,
    "pnio-rs": pnio_rs,
    "profinet-py": profinet_py,
    "pnio-dcp": pnio_dcp,
    "scapy": scapy,
    "tshark": tshark,
}


def arg(dockerfile, name):
    match = re.search(rf"^ARG {name}=(.+)$", dockerfile, re.M)
    return match.group(1).strip() if match else ""


def yaml_version(adapter):
    """The version of an adapter in versions.yaml (tshark has no Dockerfile pin)."""
    inside = False
    for line in (ROOT / "versions.yaml").read_text().splitlines():
        if line.strip() == f"{adapter}:":
            inside = True
        elif inside and re.match(r"^  [a-z]", line):
            break
        elif inside and line.strip().startswith("version:"):
            return line.split(":", 1)[1].split("#")[0].strip().strip('"')
    return ""


def pin_of(adapter):
    dockerfile = (ROOT / "adapters" / adapter / "Dockerfile").read_text()
    sha = arg(dockerfile, "UPSTREAM_SHA")
    version = arg(dockerfile, "UPSTREAM_VERSION") or (sha[:7] if sha else yaml_version(adapter))
    return {"pin": version, "pin_sha": sha, "pin_sha256": arg(dockerfile, "UPSTREAM_SHA256")}


def resolve(adapter):
    pin = pin_of(adapter)
    try:
        found = LOOKUPS[adapter](pin)
    except Exception as error:  # one failed lookup must not stop the others
        found = result("unknown", source="lookup failed", note=f"{type(error).__name__}: {error}",
                       candidate=adapter != "tshark")
    update = found.pop("update")
    found["update"] = "unknown" if update is None else ("yes" if update else "no")
    found["candidate"] = "yes" if found["candidate"] else "no"
    return {"adapter": adapter, **pin, **found}


def markdown(rows):
    def cell(text):
        return str(text).replace("|", "\\|").replace("\n", " ")

    lines = ["| Adapter | Looked up in | Pin | Latest upstream | Update? | Candidate build | Notes |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        pin = f"`{r['pin']}`" + (f"<br>`{r['pin_sha'][:7]}`" if r["pin_sha"] and r["pin"] != r["pin_sha"][:7] else "")
        latest = f"`{r['latest']}`" + (f"<br>`{r['latest_sha'][:7]}`" if r["latest_sha"] and r["latest"] != r["latest_sha"][:7] else "")
        notes = r["note"] + (f"{'<br>' if r['note'] else ''}**flagged**: {r['flag']}" if r["flag"] else "")
        lines.append(f"| {r['adapter']} | {cell(r['source'])} | {pin} | {latest} | **{r['update']}** | "
                     f"{'possible' if r['candidate'] == 'yes' else 'not checkable'} | {cell(notes)} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Compare every upstream pin with the latest upstream.")
    parser.add_argument("adapter", nargs="?", choices=ADAPTERS, help="one adapter: key=value lines")
    parser.add_argument("--json", metavar="FILE", help="write the results as JSON")
    parser.add_argument("--markdown", metavar="FILE", help="write the decision table as Markdown")
    args = parser.parse_args()  # exits 2 on a usage error

    rows = [resolve(a) for a in ([args.adapter] if args.adapter else ADAPTERS)]
    if args.adapter:
        r = rows[0]
        for name in ("pin", "pin_sha", "latest", "latest_sha", "latest_sha256", "update", "candidate", "flag",
                     "source", "note"):
            print(f"{name}={r[name]}".replace("\n", " "))
    else:
        sys.stdout.write(markdown(rows))
    if args.markdown:
        Path(args.markdown).write_text(markdown(rows))
    if args.json:
        doc = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "adapters": rows}
        Path(args.json).write_text(json.dumps(doc, indent=2) + "\n")
    return 1 if any(r["update"] == "unknown" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
