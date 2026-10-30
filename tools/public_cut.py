#!/usr/bin/env python3
"""Découpe la projection publique gnu6dotlive/blob.in depuis un commit de ce dépôt.

Ce dépôt privé reste la source de vérité ; le dépôt public en est une projection à
sens unique : un commit par version, l'historique de travail ne sort jamais. Le script
ne pousse rien. Il écrit la projection dans un dossier neuf, avec son propre dépôt Git
d'un seul commit, et peut la qualifier seule (--check : compilation et tests, à basse
priorité, dans un répertoire cible à part).

Ce qui change entre le dépôt privé et la projection est écrit ici et dans publication/ :
- les chemins de EXCLUDE ne sont pas publiés ;
- LICENSE, THIRD_PARTY_NOTICES.md et la décision de licence viennent de publication/ ;
- le README reçoit en tête l'avertissement de publication/README-PREFACE.md ;
- la licence du workspace devient MIT.

Usage : python3 tools/public_cut.py --rev main --out /chemin/neuf [--check]
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "publication"

# Non publié : dépend de chemins du dépôt privé gnu.in.labs et ne se compile pas
# ailleurs ; et le dossier de publication lui-même.
EXCLUDE = ["tools/qchain-f3-probe", "publication"]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def cut(rev: str, out: Path) -> str:
    sha = git("rev-parse", rev).strip()
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} n'est pas vide : la projection s'écrit dans un dossier neuf")
    out.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "archive", sha], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(out, filter="data")
    for rel in EXCLUDE:
        target = out / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    shutil.copyfile(PUB / "LICENSE", out / "LICENSE")
    shutil.copyfile(PUB / "THIRD_PARTY_NOTICES.md", out / "THIRD_PARTY_NOTICES.md")
    shutil.copyfile(PUB / "LICENCE-DECISION-20261030.md", out / "docs" / "LICENCE-DECISION-20261030.md")

    cargo = out / "Cargo.toml"
    text = cargo.read_text(encoding="utf-8")
    text, n = re.subn(r'^license = "LicenseRef-Proprietary"$', 'license = "MIT"', text, flags=re.M)
    if n != 1:
        sys.exit("Cargo.toml : la licence du workspace n'a pas la forme attendue")
    cargo.write_text(text, encoding="utf-8")

    readme = out / "README.md"
    text = readme.read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if not first.startswith("# blob.in showcase"):
        sys.exit("README.md : le titre n'a pas la forme attendue")
    preface = (PUB / "README-PREFACE.md").read_text(encoding="utf-8")
    readme.write_text("# blob.in — surface native Wayland\n\n" + preface + "\n" + rest, encoding="utf-8")

    version = re.search(r'^version = "([^"]+)"', cargo.read_text(encoding="utf-8"), flags=re.M).group(1)
    git("init", "-q", "-b", "main", cwd=out)
    git("add", "-A", cwd=out)
    git("-c", "user.name=tension-atoi", "-c", "user.email=dev.in@gnu6.live", "commit", "-q",
        "-m", f"blob.in {version} — projection publique de blob.in-showcase@{sha[:7]}", cwd=out)
    return sha


def check(out: Path) -> int:
    env = dict(os.environ, CARGO_TARGET_DIR=str(out.parent / (out.name + "-target")))
    for step in (["cargo", "build", "--offline", "-j", "2", "--workspace", "--all-targets"],
                 ["cargo", "test", "--offline", "-j", "2", "--workspace", "--no-fail-fast"]):
        print("$", " ".join(step), flush=True)
        code = subprocess.run(["nice", "-n", "19", *step], cwd=out, env=env).returncode
        if code:
            print(f"ÉCHEC : {' '.join(step)} ({code})")
            return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rev", default="main")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="compiler et tester la projection seule")
    args = parser.parse_args()
    sha = cut(args.rev, args.out.resolve())
    print(f"projection de {sha[:7]} écrite dans {args.out} ({git('rev-parse', '--short', 'HEAD', cwd=args.out).strip()})")
    return check(args.out.resolve()) if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
