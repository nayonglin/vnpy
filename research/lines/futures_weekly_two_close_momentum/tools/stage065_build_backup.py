"""Build one explicit research-only backup; never read credentials or production state."""
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from zoneinfo import ZoneInfo

from restore_s21_backup import digest

REPO = Path(__file__).resolve().parents[4]
LINE = Path(__file__).resolve().parents[1]
SNAPSHOT = LINE / "backups/stage065_s21_200k_20261105"
RECAPS = ("stage061_s21_200k_touch_2022_recap_v1", "stage063_s21_200k_touch_2022_recap_aligned_v1",
          "stage064_s21_200k_continuous_2017_recap_v1")
PART_BYTES = 45 * 1024 * 1024


def ordinary(path):
    return path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo")


def build():
    if SNAPSHOT.exists():
        raise FileExistsError(SNAPSHOT)
    source_inputs = json.loads((LINE / "outputs/stage060_s21_200k_touch_halfyear_20261104/S21_20w/2015-01-01/inputs.json").read_text())
    files = {}
    def add(path, role):
        path = path.resolve()
        if not ordinary(path):
            raise ValueError(f"unsupported snapshot source: {path}")
        if path.is_relative_to(REPO):
            member = "repo/" + str(path.relative_to(REPO))
        elif path.is_relative_to(Path('/Users/mac/.codex/worktrees')):
            member = "external/codex-worktrees/" + str(path.relative_to(Path('/Users/mac/.codex/worktrees')))
        else:
            raise ValueError(f"source outside the explicit research allowlist: {path}")
        item = files.setdefault(member, dict(member=member, original_path=str(path), size=path.stat().st_size,
                                             sha256=digest(path), roles=[]))
        if role not in item["roles"]:
            item["roles"].append(role)
    trees = [LINE / "outputs", REPO / "research/lines/futures_weekly19_stop_reversal/outputs"]
    trees += [REPO / "research/lines/futures_trend_winner_trade_forensics/outputs" / name for name in RECAPS]
    for tree in trees:
        for path in sorted(tree.rglob("*")):
            if ordinary(path):
                add(path, "frozen_research_artifact")
    for name, expected in source_inputs["inputs_sha256"].items():
        path = Path(name)
        if digest(path) != expected:
            raise ValueError(f"frozen market input changed: {path}")
        add(path, "required_current_market_input")
    # load_market reads these parent proofs before loading the 35 hash-pinned inputs.
    for name in ("stage003_D_20261103_attempt01/inputs.json", "stage003_independent_review.json"):
        add(REPO / "research/lines/futures_weekly19_stop_reversal/outputs" / name, "required_parent_proof")
    rows = [files[key] for key in sorted(files)]
    code = set()
    for base in (LINE, REPO / "research/lines/futures_weekly19_stop_reversal"):
        for path in base.rglob("*"):
            if ordinary(path) and not set(path.relative_to(base).parts).intersection(("outputs", "backups")):
                code.add(path)
    for relative in ("research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py",
                     "examples/portfolio_backtesting/qmt_roll_official_live_config.py", "skills/HANDOFF_MANIFEST.json", "skills/README.md",
                     "skills/futures-recap-html/SKILL.md", "skills/futures-recap-html/references/recap-contract.md"):
        code.add(REPO / relative)
    code_rows = [dict(path=str(p.relative_to(REPO)), size=p.stat().st_size, sha256=digest(p)) for p in sorted(code)]
    print(json.dumps(dict(phase="sources_pinned", files=len(rows), bytes=sum(r["size"] for r in rows), code_files=len(code_rows))), flush=True)
    SNAPSHOT.mkdir(parents=True)
    parts = []
    with tempfile.TemporaryDirectory(prefix="s21-pack-") as temp:
        archive_path = Path(temp) / "snapshot.tar.gz"
        with archive_path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for i, row in enumerate(rows):
                    path = Path(row["original_path"])
                    info = archive.gettarinfo(str(path), arcname=row["member"])
                    info.uid = info.gid = 0; info.uname = info.gname = ""; info.mtime = 0
                    with path.open("rb") as source:
                        archive.addfile(info, source)
                    if (i + 1) % 2500 == 0:
                        print(json.dumps(dict(phase="packing", files=i + 1, total=len(rows))), flush=True)
        packed_sha = digest(archive_path)
        packed_bytes = archive_path.stat().st_size
        with archive_path.open("rb") as packed:
            index = 0
            while block := packed.read(PART_BYTES):
                name = f"snapshot.tar.gz.part{index:03d}"
                (SNAPSHOT / name).write_bytes(block)
                parts.append(dict(path=name, size=len(block), sha256=hashlib.sha256(block).hexdigest()))
                index += 1
    manifest = dict(schema=1, created_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                    branch=subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
                    previous_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
                    source_version="Stage060/S21_20w/2015-01-01; 24 half-year starts; Stage061/063/064 recaps",
                    initial=200000, products=source_inputs["products"], cutoff="2026-11-04",
                    archive_sha256=packed_sha, archive_bytes=packed_bytes, parts=parts, files=rows, code_files=code_rows,
                    exclusions=["virtual environments", "credentials and account configuration", "production runtime state", "compiled caches"],
                    recovery_note="Code is normal Git content; payload paths start with repo/ or external/. Use a normal history-preserving clone and recovery-path-map.json. Frozen manifests retain original absolute paths; do not rewrite them to claim matching hashes.")
    (SNAPSHOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(phase="complete", files=len(rows), uncompressed_bytes=sum(r["size"] for r in rows),
                          archive_bytes=packed_bytes, parts=len(parts), archive_sha256=packed_sha)), flush=True)


if __name__ == "__main__":
    build()
