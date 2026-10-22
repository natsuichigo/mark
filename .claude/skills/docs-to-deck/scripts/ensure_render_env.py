#!/usr/bin/env python3
"""
ensure_render_env.py — makes deck rendering possible on this machine, whatever
this machine is.

A deck is HTML and CSS, so the only real review is looking at it. Without a
browser you are reasoning about a cascade instead of seeing it, which is how
a deck once shipped with overlapping content (SKILL.md 4a).

This bootstraps, idempotently, on Windows / macOS / Linux:

  1. a venv outside the repo, so nothing is installed into the checkout
  2. `playwright` into that venv
  3. the Firefox build Playwright pins

and then the part that is only a problem on Linux: the browser's **system**
libraries. `pip install` cannot supply those. On a workstation they come from
the package manager; on a locked-down server `sudo` is not available, and
Playwright's advice ("sudo npx playwright install-deps") is a dead end.

So on Linux, when libraries are missing and there is no root, it resolves each
missing soname to the package that provides it, downloads that package from a
public mirror, and extracts it into a user-owned prefix that is handed to the
browser through LD_LIBRARY_PATH. No root, nothing installed system-wide.

Firefox rather than Chromium, deliberately: on a RHEL 9 host with no desktop
packages, Chromium needed a wider set of libraries and Firefox reached a
working render in 39 packages.

Usage:
    python3 ensure_render_env.py                 # set it up, print the descriptor
    python3 ensure_render_env.py --check         # report only, change nothing
    python3 ensure_render_env.py --json          # descriptor for another script
    python3 ensure_render_env.py --no-system-libs  # skip the rootless fallback

Writes a descriptor to <cache>/render-env.json which screenshot_deck.py reads.

Exit codes:
    0 = a browser can be launched
    1 = it cannot, and the reason is printed with what to ask for
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

PLAYWRIGHT_PIN = "playwright==1.59.0"

# Resolved empirically on RHEL 9 with no desktop packages: the closure that got
# Firefox from "Couldn't load XPCOM" to a rendered PNG. Used as the starting set;
# anything still missing afterwards is resolved by soname from repo metadata,
# which is what turned up libtracker-sparql (in its own subpackage, not gtk3).
RPM_SEED = [
    "alsa-lib", "atk", "at-spi2-atk", "at-spi2-core", "cairo", "cairo-gobject",
    "gdk-pixbuf2", "gtk3", "pango", "harfbuzz", "fribidi", "libthai",
    "libdatrie", "graphite2", "libepoxy", "libXcomposite", "libXcursor",
    "libXdamage", "libXi", "libXrandr", "libXinerama", "libXtst",
    "libxkbcommon", "libXfixes", "libXrender", "libXext", "libX11", "libxcb",
    "libXau", "pixman", "libpng", "freetype", "fontconfig", "dbus-libs",
    "json-glib", "icu", "libstemmer", "tracker", "libtracker-sparql",
]
DEB_SEED = [
    "libasound2", "libatk1.0-0", "libatk-bridge2.0-0", "libatspi2.0-0",
    "libcairo2", "libcairo-gobject2", "libgdk-pixbuf-2.0-0", "libgtk-3-0",
    "libpango-1.0-0", "libpangocairo-1.0-0", "libharfbuzz0b", "libfribidi0",
    "libthai0", "libdatrie1", "libgraphite2-3", "libepoxy0",
    "libxcomposite1", "libxcursor1", "libxdamage1", "libxi6", "libxrandr2",
    "libxinerama1", "libxtst6", "libxkbcommon0", "libxfixes3", "libxrender1",
    "libdbus-1-3", "libjson-glib-1.0-0", "libtracker-sparql-3.0-0",
]

# Public, unauthenticated, ABI-compatible with RHEL 9. A subscribed RHEL host
# often still cannot reach cdn.redhat.com without entitlement (403), so a
# public rebuild is the reliable source for a rootless fetch.
ROCKY = "https://dl.rockylinux.org/pub/rocky/9"
ROCKY_REPOS = ("BaseOS", "AppStream")


def cache_root() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "deck-render"


def venv_python(vdir: Path) -> Path:
    return (vdir / "Scripts" / "python.exe") if platform.system() == "Windows" \
        else (vdir / "bin" / "python")


def run(cmd, **kw):
    kw.setdefault("check", False)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run([str(c) for c in cmd], **kw)


def ensure_venv(root: Path, quiet=False) -> Path:
    vdir = root / "venv"
    py = venv_python(vdir)
    if not py.is_file():
        if not quiet:
            print(f"  creating venv at {vdir}")
        venv.EnvBuilder(with_pip=True, clear=False).create(vdir)
    have = run([py, "-c", "import playwright,sys;print(playwright.__version__)"])
    if have.returncode != 0:
        if not quiet:
            print(f"  installing {PLAYWRIGHT_PIN}")
        r = run([py, "-m", "pip", "install", "--quiet", PLAYWRIGHT_PIN])
        if r.returncode != 0:
            sys.exit(f"error: pip install failed:\n{r.stderr.strip()[:800]}")
    elif not quiet:
        print(f"  playwright {have.stdout.strip()} present")
    return py


def ensure_browser(py: Path, quiet=False) -> Path:
    """Install the Firefox build this Playwright pins, and return its executable."""
    probe = ("from playwright.sync_api import sync_playwright\n"
             "with sync_playwright() as p: print(p.firefox.executable_path)\n")
    r = run([py, "-c", probe])
    exe = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    if exe is None or not exe.is_file():
        if not quiet:
            print("  downloading the Firefox build playwright pins")
        d = run([py, "-m", "playwright", "install", "firefox"])
        if d.returncode != 0:
            sys.exit(f"error: browser download failed:\n{d.stderr.strip()[:800]}")
        r = run([py, "-c", probe])
        exe = Path(r.stdout.strip()) if r.stdout.strip() else None
    if exe is None or not exe.is_file():
        sys.exit("error: playwright reports no firefox executable after install")
    return exe


def missing_sonames(exe: Path, extra_paths=()) -> list:
    """
    What the dynamic linker still cannot find. Checked across the browser's own
    shared objects, not just the launcher: firefox's GTK dependencies arrive via
    libxul.so, so `ldd firefox` alone reports nothing missing and is misleading.
    """
    if not shutil.which("ldd"):
        return []
    env = dict(os.environ)
    paths = [str(exe.parent), str(exe.parent / "gtk")] + [str(p) for p in extra_paths]
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in paths if p] + [env.get("LD_LIBRARY_PATH", "")])
    out = set()
    # Every shared object beside the launcher, not a slice of them. Firefox's GTK
    # dependencies come in through libxul.so, which sorts late enough that a
    # truncated list reported 2 missing where 13 actually were.
    targets = [exe] + sorted(exe.parent.glob("*.so"))
    for t in targets:
        r = subprocess.run(["ldd", str(t)], capture_output=True, text=True,
                           env=env, check=False)
        for line in r.stdout.splitlines():
            if "not found" in line:
                out.add(line.split("=>")[0].strip())
    # Firefox's own libs sit beside the binary; they are on the path above, so
    # anything still unresolved is genuinely a system library.
    return sorted(s for s in out if not (exe.parent / s).exists())


def distro_family() -> str:
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8")
    except OSError:
        return "unknown"
    fields = dict(
        line.split("=", 1) for line in text.splitlines() if "=" in line)
    ident = (fields.get("ID", "") + " " + fields.get("ID_LIKE", "")).lower()
    if any(k in ident for k in ("rhel", "centos", "rocky", "almalinux", "fedora")):
        return "rpm"
    if any(k in ident for k in ("debian", "ubuntu")):
        return "deb"
    return "unknown"


def _rocky_metadata(root: Path, quiet=False) -> dict:
    """repo -> decompressed primary.xml text, cached on disk."""
    import gzip
    import re
    meta = {}
    cache = root / "repodata"
    cache.mkdir(parents=True, exist_ok=True)
    for repo in ROCKY_REPOS:
        local = cache / f"primary-{repo}.xml.gz"
        if not local.is_file():
            idx = run(["curl", "-sf", "--max-time", "120",
                       f"{ROCKY}/{repo}/x86_64/os/repodata/"])
            names = re.findall(r"[a-f0-9]{64}-primary\.xml\.gz", idx.stdout or "")
            if not names:
                continue
            if not quiet:
                print(f"    fetching {repo} package index")
            run(["curl", "-sf", "--max-time", "300",
                 f"{ROCKY}/{repo}/x86_64/os/repodata/{names[0]}",
                 "-o", str(local)])
        if local.is_file():
            try:
                meta[repo] = gzip.open(local, "rt", errors="replace").read()
            except OSError:
                pass
    return meta


def _rocky_fetch(names, sonames, root: Path, quiet=False) -> int:
    """
    Download packages by name, and by the sonames they PROVIDE.

    The soname must be matched inside <rpm:provides> and nowhere else. Matching
    the whole package block instead catches every package that *requires* the
    library: 236 packages mention libgtk-3.so.0, but only 4 provide it, so the
    broad match pulled ~200 RPMs including webkit2gtk3 — 1.6 GB before it was
    stopped.
    """
    import re
    meta = _rocky_metadata(root, quiet)
    if not meta:
        return 0
    rpms = root / "rpms"
    prefix = root / "prefix"
    rpms.mkdir(parents=True, exist_ok=True)
    prefix.mkdir(parents=True, exist_ok=True)
    wanted = set(names)
    # A soname maps to few real providers; take the shortest-named one, which is
    # the library package rather than an application that bundles a copy.
    providers = {}
    got = 0
    for repo, data in meta.items():
        for m in re.finditer(r'<package type="rpm">(.*?)</package>', data, re.S):
            blk = m.group(1)
            nm = re.search(r"<name>([^<]+)</name>", blk)
            loc = re.search(r'<location href="([^"]+)"', blk)
            arch = re.search(r"<arch>([^<]+)</arch>", blk)
            if not (nm and loc and arch) or arch.group(1) not in ("x86_64", "noarch"):
                continue
            entry = (repo, loc.group(1), nm.group(1))
            if nm.group(1) in wanted:
                providers.setdefault("name:" + nm.group(1), entry)
            if sonames:
                pm = re.search(r"<rpm:provides>(.*?)</rpm:provides>", blk, re.S)
                if pm:
                    body = pm.group(1)
                    for s in sonames:
                        if s not in body:
                            continue
                        key = "so:" + s
                        prev = providers.get(key)
                        if prev is None or len(nm.group(1)) < len(prev[2]):
                            providers[key] = entry
    for key, (repo, href, pkg) in sorted(providers.items()):
        out = rpms / Path(href).name
        if out.is_file():
            continue
        if not quiet:
            print(f"      {pkg}  ({key.split(':', 1)[0]})")
        r = run(["curl", "-sf", "--max-time", "180",
                 f"{ROCKY}/{repo}/x86_64/os/{href}", "-o", str(out)])
        if r.returncode == 0:
            got += 1
    for rpm in sorted(rpms.glob("*.rpm")):
        p1 = subprocess.Popen(["rpm2cpio", str(rpm)], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        subprocess.run(["cpio", "-idmu", "--quiet"], stdin=p1.stdout, cwd=prefix,
                       stderr=subprocess.DEVNULL, check=False)
        if p1.stdout:
            p1.stdout.close()
    return got


def _deb_fetch(names, root: Path, quiet=False) -> int:
    """
    Debian/Ubuntu: `apt-get download` needs no root. Extracted with dpkg-deb if
    present, otherwise ar+tar, which every base image has.
    """
    debs = root / "debs"
    prefix = root / "prefix"
    debs.mkdir(parents=True, exist_ok=True)
    prefix.mkdir(parents=True, exist_ok=True)
    got = 0
    for name in names:
        if list(debs.glob(f"{name}_*.deb")):
            continue
        if run(["apt-get", "download", name], cwd=debs).returncode == 0:
            got += 1
        elif not quiet:
            print(f"    could not download {name}")
    for deb in sorted(debs.glob("*.deb")):
        if shutil.which("dpkg-deb"):
            run(["dpkg-deb", "-x", str(deb), str(prefix)])
        elif shutil.which("ar"):
            tmp = root / "unpack"
            tmp.mkdir(exist_ok=True)
            run(["ar", "x", str(deb)], cwd=tmp)
            for tar in list(tmp.glob("data.tar*")):
                run(["tar", "-xf", str(tar), "-C", str(prefix)])
                tar.unlink(missing_ok=True)
    return got


def lib_dirs(prefix: Path) -> list:
    """Every directory under the prefix that actually holds a shared object."""
    if not prefix.is_dir():
        return []
    seen = []
    for so in prefix.rglob("*.so*"):
        d = so.parent
        if d not in seen:
            seen.append(d)
    return seen


def ensure_system_libs(exe: Path, root: Path, quiet=False) -> tuple:
    """
    Returns (ld_library_path_entries, still_missing). Loops because resolving one
    package can reveal the next — gtk3 needs libtracker-sparql, which lives in
    its own subpackage and only surfaced after gtk3 was in place.
    """
    prefix = root / "libs"
    extra = lib_dirs(prefix / "prefix")
    missing = missing_sonames(exe, extra)
    if not missing:
        return extra, []
    family = distro_family()
    if family == "unknown":
        return extra, missing
    if not quiet:
        print(f"  {len(missing)} system library(ies) missing; fetching "
              f"rootless ({family})")
    seed = RPM_SEED if family == "rpm" else DEB_SEED
    for attempt in range(4):
        if family == "rpm":
            if not shutil.which("rpm2cpio") or not shutil.which("cpio"):
                break
            _rocky_fetch(seed if attempt == 0 else [], missing, prefix, quiet)
        else:
            if not shutil.which("apt-get"):
                break
            _deb_fetch(seed if attempt == 0 else [], prefix, quiet)
        extra = lib_dirs(prefix / "prefix")
        still = missing_sonames(exe, extra)
        if not quiet:
            print(f"    pass {attempt + 1}: {len(still)} still missing")
        if not still or still == missing:
            missing = still
            break
        missing = still
    return extra, missing


def verify(py: Path, exe: Path, ld: list, quiet=False) -> bool:
    script = ("from playwright.sync_api import sync_playwright\n"
              "with sync_playwright() as p:\n"
              "    b = p.firefox.launch()\n"
              "    pg = b.new_page()\n"
              "    pg.set_content('<h1>ok</h1>')\n"
              "    assert pg.title() is not None\n"
              "    b.close()\n"
              "print('RENDER_OK')\n")
    env = dict(os.environ)
    if ld:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(
            [str(p) for p in ld] + [str(exe.parent), str(exe.parent / "gtk"),
                                    env.get("LD_LIBRARY_PATH", "")])
    r = subprocess.run([str(py), "-c", script], capture_output=True, text=True,
                       env=env, check=False)
    ok = "RENDER_OK" in (r.stdout or "")
    if not ok and not quiet:
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        print("  launch failed:")
        for line in tail[:6]:
            print(f"    {line}")
    return ok


def advice(family: str, missing: list) -> str:
    if family == "rpm":
        cmd = "sudo dnf install -y gtk3 alsa-lib libXcomposite libXdamage libXrandr libXcursor libXi libtracker-sparql"
    elif family == "deb":
        cmd = "sudo apt-get install -y libgtk-3-0 libasound2 libxcomposite1 libxdamage1 libxrandr2 libxcursor1 libxi6"
    else:
        cmd = "install the GTK/X11 runtime for your distribution"
    return (f"Could not resolve {len(missing)} library(ies) without root: "
            f"{', '.join(missing[:6])}\n"
            f"  Ask an administrator to run:\n    {cmd}\n"
            f"  Until then, decks cannot be rendered here — follow SKILL.md "
            f"section 4a and rely on validate_deck.py.")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="Report what is present; install nothing")
    ap.add_argument("--json", action="store_true",
                    help="Print only the descriptor JSON")
    ap.add_argument("--no-system-libs", action="store_true",
                    help="Skip the rootless system-library fallback on Linux")
    args = ap.parse_args()
    quiet = args.json
    root = cache_root()

    if not quiet:
        print(f"\n  render environment  [{platform.system()} "
              f"{platform.machine()}]")
        print(f"  cache: {root}")

    if args.check:
        py = venv_python(root / "venv")
        desc = root / "render-env.json"
        print(f"    venv       : {'present' if py.is_file() else 'absent'}")
        print(f"    descriptor : {'present' if desc.is_file() else 'absent'}")
        if desc.is_file():
            d = json.loads(desc.read_text())
            print(f"    verified   : {d.get('verified')}")
        return 0

    root.mkdir(parents=True, exist_ok=True)
    py = ensure_venv(root, quiet)
    exe = ensure_browser(py, quiet)
    if not quiet:
        print(f"  browser: {exe}")

    ld, missing = ([], [])
    if platform.system() == "Linux" and not args.no_system_libs:
        ld, missing = ensure_system_libs(exe, root, quiet)

    ok = verify(py, exe, ld, quiet)
    descriptor = {
        "platform": platform.system(),
        "python": str(py),
        "browser": str(exe),
        "ld_library_path": [str(p) for p in ld],
        "verified": ok,
        "missing_libraries": missing,
    }
    (root / "render-env.json").write_text(json.dumps(descriptor, indent=1),
                                          encoding="utf-8")
    if args.json:
        print(json.dumps(descriptor, indent=1))
        return 0 if ok else 1

    if ok:
        print("\n  PASS  a browser launches — screenshot_deck.py can run")
        print(f"        descriptor: {root / 'render-env.json'}")
        return 0
    print("\n  FAIL  no browser could be launched")
    print("  " + advice(distro_family(), missing or ["unknown"]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
