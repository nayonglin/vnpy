"""Copy normalized experiment inputs for local preservation, without price diagnostics."""
from pathlib import Path
import csv
import gzip
import hashlib
import json


LINE = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    manifest_path = LINE / "outputs/stage009_day_proxy_dataset/export/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    source = Path(manifest["dataset"]["path"])
    if digest(source) != manifest["dataset"]["sha256"]:
        raise ValueError("accepted dataset bytes changed")
    output = LINE / "outputs/stage013_local_registration"
    output.mkdir(exist_ok=False)
    target = output / "normalized_feature_labels.csv.gz"
    with gzip.open(source, "rt", newline="") as src, target.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            import io
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as dst:
                reader = csv.DictReader(src)
                columns = [name for name in reader.fieldnames if name != "atr20"]
                if set(columns) & {"open", "high", "low", "close", "atr20"}:
                    raise ValueError("price diagnostics in preservation projection")
                writer = csv.DictWriter(dst, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                rows = 0
                for row in reader:
                    writer.writerow({name: row[name] for name in columns})
                    rows += 1
    if rows != manifest["dataset"]["rows"]:
        raise ValueError("preservation row count changed")
    receipt = {
        "schema": "stage013_normalized_preservation_projection_v1",
        "original_manifest": {"path": str(manifest_path), "sha256": digest(manifest_path)},
        "original_dataset": manifest["dataset"],
        "projection": {"path": str(target), "sha256": digest(target),
                       "bytes": target.stat().st_size, "rows": rows, "columns": columns},
        "removed_columns": ["atr20"],
        "retained_fields": "exact CSV field strings, same row order; no numeric parsing",
        "purpose": "local reproducibility of all actual model features and targets without absolute ATR price diagnostic",
        "role": "decision_asset", "reproducibility_required": True,
        "model_fits": 0, "financial_runs": 0,
        "raw_market_files_copied": 0, "commit_push_calls": 0,
    }
    (output / "projection_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"rows": rows, "bytes": target.stat().st_size,
                      "sha256": receipt["projection"]["sha256"],
                      "model_fits": 0, "financial_runs": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
