import argparse
import csv
import hashlib
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SEVERITY_CLASSES = ["small_pothole", "medium_pothole", "severe_pothole"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(SEVERITY_CLASSES)}


@dataclass
class ObjectRow:
    object_id: str
    image_id: str
    source_split: str
    source_image: str
    source_label: str
    width: int
    height: int
    bbox_index: int
    x_center: float
    y_center: float
    box_width: float
    box_height: float
    bbox_area: float
    bbox_aspect: float
    bbox_dark_ratio: float
    bbox_edge_density: float
    bbox_contrast: float
    bbox_laplacian: float
    severity_score: float
    auto_severity: str
    reviewed_severity: str
    needs_review: str
    split: str
    base_key: str
    duplicate_key: str


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze Roboflow YOLO pothole data and build a severity-labeled subset."
    )
    parser.add_argument(
        "--source-root",
        default="ml/data/source/dataset-pothole/dataset",
        help="Source dataset root with train/test folders containing images and YOLO txt labels.",
    )
    parser.add_argument(
        "--output-root",
        default="ml/data/pothole_severity",
        help="Output root for YOLO severity dataset, review app, and reports.",
    )
    parser.add_argument("--subset-size", type=int, default=450, help="Target image count for review/training.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--review-csv",
        default=None,
        help="Optional reviewed CSV exported from the HTML app. Reviewed severities override auto labels.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip contact sheets to speed up regeneration after review edits.",
    )
    return parser.parse_args()


def image_key(path: Path) -> str:
    # Roboflow filenames commonly look like foo_png.rf.<augmentation_hash>.jpg.
    name = path.stem
    if ".rf." in name:
        return name.split(".rf.")[0]
    return name


def read_yolo_label(path: Path) -> list[list[float]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        try:
            rows.append([float(value) for value in parts])
        except ValueError:
            continue
    return rows


def md5_prefix(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()[:16]


def ahash(gray: np.ndarray) -> str:
    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    bits = small > small.mean()
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def clamp_box(x1: int, y1: int, x2: int, y2: int, width: int, height: int):
    return max(0, x1), max(0, y1), min(width - 1, x2), min(height - 1, y2)


def bbox_to_pixels(xc: float, yc: float, bw: float, bh: float, width: int, height: int):
    x1 = int(round((xc - bw / 2) * width))
    y1 = int(round((yc - bh / 2) * height))
    x2 = int(round((xc + bw / 2) * width))
    y2 = int(round((yc + bh / 2) * height))
    return clamp_box(x1, y1, x2, y2, width, height)


def crop_stats(gray: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, float]:
    x1, y1, x2, y2 = box
    crop = gray[y1 : y2 + 1, x1 : x2 + 1]
    if crop.size == 0:
        return {
            "dark_ratio": 0.0,
            "edge_density": 0.0,
            "contrast": 0.0,
            "laplacian": 0.0,
        }
    edges = cv2.Canny(crop, 60, 160)
    lap = cv2.Laplacian(crop, cv2.CV_64F)
    return {
        "dark_ratio": float((crop < 85).mean()),
        "edge_density": float((edges > 0).mean()),
        "contrast": float(crop.std() / 255.0),
        "laplacian": float(min(lap.var() / 2500.0, 1.0)),
    }


def percentile_rank(sorted_values: list[float], value: float) -> float:
    if not sorted_values:
        return 0.0
    lo, hi = 0, len(sorted_values)
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_values[mid] <= value:
            lo = mid + 1
        else:
            hi = mid
    return lo / len(sorted_values)


def severity_from_score(score: float) -> str:
    if score < 0.38:
        return "small_pothole"
    if score < 0.68:
        return "medium_pothole"
    return "severe_pothole"


def collect_pairs(source_root: Path):
    pairs = []
    for split_dir in sorted(path for path in source_root.iterdir() if path.is_dir()):
        split = split_dir.name
        for image_path in sorted(split_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            pairs.append((split, image_path, image_path.with_suffix(".txt")))
    return pairs


def inspect_dataset(source_root: Path):
    pairs = collect_pairs(source_root)
    object_raw = []
    image_rows = []
    label_lengths = Counter()
    class_counts = Counter()
    bad_images = []
    missing_labels = []
    empty_labels = []
    exact_md5 = defaultdict(list)
    ahashes = defaultdict(list)

    for split, image_path, label_path in pairs:
        try:
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("cv2.imread returned None")
            height, width = image.shape[:2]
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except Exception as exc:
            bad_images.append({"path": str(image_path), "error": str(exc)})
            continue

        labels = read_yolo_label(label_path)
        if not label_path.exists():
            missing_labels.append(str(image_path))
        if not labels:
            empty_labels.append(str(image_path))

        duplicate_key = md5_prefix(image_path)
        perceptual_key = ahash(gray)
        exact_md5[duplicate_key].append(str(image_path))
        ahashes[perceptual_key].append(str(image_path))

        bbox_areas = []
        for idx, values in enumerate(labels):
            label_lengths[len(values)] += 1
            if len(values) < 5:
                continue
            class_id = int(values[0])
            class_counts[class_id] += 1
            xc, yc, bw, bh = values[1:5]
            area = max(0.0, bw * bh)
            bbox_areas.append(area)
            box = bbox_to_pixels(xc, yc, bw, bh, width, height)
            stats = crop_stats(gray, box)
            object_raw.append(
                {
                    "source_split": split,
                    "source_image": str(image_path),
                    "source_label": str(label_path),
                    "width": width,
                    "height": height,
                    "bbox_index": idx,
                    "x_center": float(xc),
                    "y_center": float(yc),
                    "box_width": float(bw),
                    "box_height": float(bh),
                    "bbox_area": float(area),
                    "bbox_aspect": float(bw / max(bh, 1e-6)),
                    "base_key": image_key(image_path),
                    "duplicate_key": duplicate_key,
                    "perceptual_key": perceptual_key,
                    "bbox_dark_ratio": stats["dark_ratio"],
                    "bbox_edge_density": stats["edge_density"],
                    "bbox_contrast": stats["contrast"],
                    "bbox_laplacian": stats["laplacian"],
                }
            )

        image_rows.append(
            {
                "source_split": split,
                "source_image": str(image_path),
                "source_label": str(label_path),
                "width": width,
                "height": height,
                "label_count": len(labels),
                "bbox_area_sum": float(sum(bbox_areas)),
                "bbox_area_max": float(max(bbox_areas) if bbox_areas else 0.0),
                "brightness": float(gray.mean() / 255.0),
                "contrast": float(gray.std() / 255.0),
                "base_key": image_key(image_path),
                "duplicate_key": duplicate_key,
                "perceptual_key": perceptual_key,
            }
        )

    return {
        "pairs": pairs,
        "objects": object_raw,
        "images": image_rows,
        "label_lengths": label_lengths,
        "class_counts": class_counts,
        "bad_images": bad_images,
        "missing_labels": missing_labels,
        "empty_labels": empty_labels,
        "exact_duplicates": {key: paths for key, paths in exact_md5.items() if len(paths) > 1},
        "perceptual_duplicates": {key: paths for key, paths in ahashes.items() if len(paths) > 1},
    }


def add_auto_severity(objects: list[dict]) -> list[dict]:
    areas = sorted(obj["bbox_area"] for obj in objects)
    darks = sorted(obj["bbox_dark_ratio"] for obj in objects)
    edges = sorted(obj["bbox_edge_density"] for obj in objects)
    contrasts = sorted(obj["bbox_contrast"] for obj in objects)
    laps = sorted(obj["bbox_laplacian"] for obj in objects)

    out = []
    for obj in objects:
        area_rank = percentile_rank(areas, obj["bbox_area"])
        dark_rank = percentile_rank(darks, obj["bbox_dark_ratio"])
        edge_rank = percentile_rank(edges, obj["bbox_edge_density"])
        contrast_rank = percentile_rank(contrasts, obj["bbox_contrast"])
        lap_rank = percentile_rank(laps, obj["bbox_laplacian"])
        occupancy = min(math.sqrt(max(obj["bbox_area"], 0.0)) / 0.75, 1.0)
        aspect_penalty = min(abs(math.log(max(obj["bbox_aspect"], 1e-3))) / 2.0, 1.0)
        score = (
            0.52 * area_rank
            + 0.18 * occupancy
            + 0.10 * dark_rank
            + 0.08 * edge_rank
            + 0.07 * contrast_rank
            + 0.03 * lap_rank
            + 0.02 * aspect_penalty
        )
        score = float(max(0.0, min(1.0, score)))
        obj = dict(obj)
        obj["severity_score"] = score
        obj["auto_severity"] = severity_from_score(score)
        out.append(obj)
    return out


def load_review_overrides(path: Optional[Path]) -> dict[str, str]:
    if not path:
        return {}
    overrides = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            object_id = row.get("object_id", "").strip()
            severity = (row.get("reviewed_severity") or row.get("severity") or "").strip()
            if object_id and severity in CLASS_TO_ID:
                overrides[object_id] = severity
    return overrides


def choose_subset(images: list[dict], objects: list[dict], target_size: int, seed: int):
    random.seed(seed)
    by_image = defaultdict(list)
    for obj in objects:
        by_image[obj["source_image"]].append(obj)

    eligible = []
    for image in images:
        objs = by_image.get(image["source_image"], [])
        if not objs:
            continue
        image = dict(image)
        image["max_score"] = max(obj["severity_score"] for obj in objs)
        image["mean_score"] = float(sum(obj["severity_score"] for obj in objs) / len(objs))
        image["dominant_auto_severity"] = Counter(obj["auto_severity"] for obj in objs).most_common(1)[0][0]
        image["object_count"] = len(objs)
        eligible.append(image)

    # One image per original base_key first, avoiding Roboflow augmentation over-representation.
    grouped = defaultdict(list)
    for image in eligible:
        grouped[image["base_key"]].append(image)

    representatives = []
    for base_key, rows in grouped.items():
        rows.sort(
            key=lambda row: (
                row["bbox_area_max"],
                row["contrast"],
                row["object_count"],
                -abs(row["brightness"] - 0.5),
            ),
            reverse=True,
        )
        representatives.append(rows[0])

    severity_buckets = defaultdict(list)
    for row in representatives:
        severity_buckets[row["dominant_auto_severity"]].append(row)

    selected = []
    seen_sources = set()
    target_per_class = max(1, target_size // len(SEVERITY_CLASSES))
    for severity in SEVERITY_CLASSES:
        bucket = severity_buckets[severity]
        bucket.sort(
            key=lambda row: (
                row["max_score"] if severity != "small_pothole" else 1.0 - row["max_score"],
                row["object_count"],
                row["contrast"],
            ),
            reverse=True,
        )
        for row in bucket[:target_per_class]:
            selected.append(row)
            seen_sources.add(row["source_image"])

    # Fill remaining slots by diversity bins across size, brightness, contrast, and source split.
    remainder = [row for row in representatives if row["source_image"] not in seen_sources]
    remainder.sort(
        key=lambda row: (
            row["bbox_area_max"],
            row["contrast"],
            abs(row["brightness"] - 0.5),
            row["object_count"],
        ),
        reverse=True,
    )
    for row in remainder:
        if len(selected) >= min(target_size, len(representatives)):
            break
        selected.append(row)
        seen_sources.add(row["source_image"])

    # If the original unique-image count is smaller than target, allow extra augmentations but keep them late.
    if len(selected) < target_size:
        extra = [row for row in eligible if row["source_image"] not in seen_sources]
        extra.sort(key=lambda row: (row["bbox_area_max"], row["contrast"], row["object_count"]), reverse=True)
        for row in extra:
            if len(selected) >= target_size:
                break
            selected.append(row)
            seen_sources.add(row["source_image"])

    selected.sort(key=lambda row: row["source_image"])
    return selected[:target_size]


def assign_splits(selected_images: list[dict], seed: int):
    random.seed(seed)
    by_severity = defaultdict(list)
    for row in selected_images:
        by_severity[row["dominant_auto_severity"]].append(row)

    split_by_source = {}
    for severity, rows in by_severity.items():
        random.shuffle(rows)
        n = len(rows)
        n_train = max(1, int(n * 0.72))
        n_val = max(1, int(n * 0.18)) if n >= 6 else 0
        for idx, row in enumerate(rows):
            if idx < n_train:
                split = "train"
            elif idx < n_train + n_val:
                split = "val"
            else:
                split = "test"
            split_by_source[row["source_image"]] = split
    return split_by_source


def object_id_for(obj: dict) -> str:
    source = Path(obj["source_image"]).stem
    return f"{source}__box{obj['bbox_index']:02d}"


def build_rows(selected_images: list[dict], objects: list[dict], split_by_source: dict, overrides: dict):
    selected_sources = {row["source_image"] for row in selected_images}
    rows = []
    for obj in objects:
        if obj["source_image"] not in selected_sources:
            continue
        object_id = object_id_for(obj)
        reviewed = overrides.get(object_id, obj["auto_severity"])
        needs_review = "yes"
        if obj["severity_score"] < 0.18 or obj["severity_score"] > 0.82:
            needs_review = "low"
        elif 0.34 <= obj["severity_score"] <= 0.42 or 0.64 <= obj["severity_score"] <= 0.72:
            needs_review = "high"
        rows.append(
            ObjectRow(
                object_id=object_id,
                image_id=Path(obj["source_image"]).stem,
                source_split=obj["source_split"],
                source_image=obj["source_image"],
                source_label=obj["source_label"],
                width=int(obj["width"]),
                height=int(obj["height"]),
                bbox_index=int(obj["bbox_index"]),
                x_center=float(obj["x_center"]),
                y_center=float(obj["y_center"]),
                box_width=float(obj["box_width"]),
                box_height=float(obj["box_height"]),
                bbox_area=float(obj["bbox_area"]),
                bbox_aspect=float(obj["bbox_aspect"]),
                bbox_dark_ratio=float(obj["bbox_dark_ratio"]),
                bbox_edge_density=float(obj["bbox_edge_density"]),
                bbox_contrast=float(obj["bbox_contrast"]),
                bbox_laplacian=float(obj["bbox_laplacian"]),
                severity_score=float(obj["severity_score"]),
                auto_severity=obj["auto_severity"],
                reviewed_severity=reviewed,
                needs_review=needs_review,
                split=split_by_source[obj["source_image"]],
                base_key=obj["base_key"],
                duplicate_key=obj["duplicate_key"],
            )
        )
    return rows


def reset_output_dirs(output_root: Path):
    for rel in [
        "images/train",
        "images/val",
        "images/test",
        "labels/train",
        "labels/val",
        "labels/test",
        "review/images",
        "analysis",
    ]:
        path = output_root / rel
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def copy_dataset(rows: list[ObjectRow], output_root: Path):
    by_image = defaultdict(list)
    for row in rows:
        by_image[row.source_image].append(row)

    copied = []
    for source_image, object_rows in by_image.items():
        split = object_rows[0].split
        source_path = Path(source_image)
        dest_image = output_root / "images" / split / source_path.name
        shutil.copy2(source_path, dest_image)
        label_lines = []
        for row in object_rows:
            class_id = CLASS_TO_ID[row.reviewed_severity]
            label_lines.append(
                f"{class_id} {row.x_center:.8f} {row.y_center:.8f} {row.box_width:.8f} {row.box_height:.8f}"
            )
        dest_label = output_root / "labels" / split / f"{source_path.stem}.txt"
        dest_label.write_text("\n".join(label_lines) + "\n")
        copied.append(str(dest_image))
    return copied


def draw_overlay(source_image: Path, rows: list[ObjectRow], dest_path: Path, compact: bool = False):
    image = Image.open(source_image).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    colors = {
        "small_pothole": (43, 164, 86),
        "medium_pothole": (230, 155, 36),
        "severe_pothole": (214, 54, 64),
    }
    try:
        font = ImageFont.truetype("Arial.ttf", 16 if not compact else 12)
    except OSError:
        font = ImageFont.load_default()
    for row in rows:
        x1, y1, x2, y2 = bbox_to_pixels(row.x_center, row.y_center, row.box_width, row.box_height, width, height)
        color = colors[row.reviewed_severity]
        for offset in range(3):
            draw.rectangle((x1 - offset, y1 - offset, x2 + offset, y2 + offset), outline=color)
        label = f"{row.bbox_index}:{row.reviewed_severity.replace('_pothole', '')} {row.severity_score:.2f}"
        text_box = draw.textbbox((x1, max(0, y1 - 18)), label, font=font)
        draw.rectangle(text_box, fill=color)
        draw.text((x1, max(0, y1 - 18)), label, fill=(255, 255, 255), font=font)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest_path, quality=88)


def create_contact_sheets(review_images: list[Path], output_root: Path, columns: int = 5):
    sheets_dir = output_root / "review" / "contact_sheets"
    if sheets_dir.exists():
        shutil.rmtree(sheets_dir)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    thumb_w, thumb_h = 260, 190
    rows_per_sheet = 5
    per_sheet = columns * rows_per_sheet
    for sheet_idx in range(0, len(review_images), per_sheet):
        chunk = review_images[sheet_idx : sheet_idx + per_sheet]
        canvas = Image.new("RGB", (columns * thumb_w, rows_per_sheet * thumb_h), (245, 245, 245))
        draw = ImageDraw.Draw(canvas)
        for idx, path in enumerate(chunk):
            image = Image.open(path).convert("RGB")
            image.thumbnail((thumb_w, thumb_h - 18), Image.Resampling.LANCZOS)
            x = (idx % columns) * thumb_w
            y = (idx // columns) * thumb_h
            canvas.paste(image, (x + (thumb_w - image.width) // 2, y))
            draw.text((x + 6, y + thumb_h - 16), path.stem[:34], fill=(20, 20, 20))
        canvas.save(sheets_dir / f"contact_sheet_{sheet_idx // per_sheet + 1:02d}.jpg", quality=88)


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_review_app(output_root: Path, rows: list[ObjectRow], by_image: dict[str, list[ObjectRow]]):
    app_rows = []
    for source_image, object_rows in by_image.items():
        overlay = Path("images") / f"{Path(source_image).stem}.jpg"
        for row in object_rows:
            item = asdict(row)
            item["overlay_image"] = str(overlay)
            item["source_filename"] = Path(source_image).name
            app_rows.append(item)

    data_json = json.dumps(app_rows)
    class_options = "".join(
        f'<option value="{name}">{name.replace("_", " ")}</option>' for name in SEVERITY_CLASSES
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pothole Severity Review</title>
  <style>
    :root {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; }}
    body {{ margin: 0; background: #f6f7f9; }}
    header {{ position: sticky; top: 0; z-index: 2; background: #ffffff; border-bottom: 1px solid #d9dee7; padding: 12px 18px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
    h1 {{ font-size: 18px; margin: 0 10px 0 0; }}
    button, select, input {{ font-size: 14px; padding: 8px 10px; border: 1px solid #b7c0cc; border-radius: 6px; background: #fff; }}
    button {{ cursor: pointer; background: #17202a; color: #fff; border-color: #17202a; }}
    main {{ padding: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 14px; }}
    .card {{ background: #fff; border: 1px solid #d9dee7; border-radius: 8px; overflow: hidden; }}
    .card img {{ width: 100%; display: block; background: #111; }}
    .meta {{ padding: 10px 12px; display: grid; gap: 8px; }}
    .row {{ display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; }}
    .badge {{ font-size: 12px; padding: 3px 6px; border-radius: 999px; background: #eef2f7; }}
    .high {{ background: #fff0d8; }}
    .low {{ background: #e7f7ed; }}
    .stats {{ color: #586475; font-size: 12px; }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
  <header>
    <h1>Pothole Severity Review</h1>
    <select id="filter">
      <option value="all">all rows</option>
      <option value="high">high-priority boundaries</option>
      <option value="yes">normal review</option>
      <option value="low">low-priority confident</option>
      {class_options}
    </select>
    <input id="search" placeholder="search filename or object id">
    <button id="export">Export reviewed CSV</button>
    <span id="count"></span>
  </header>
  <main><div id="grid" class="grid"></div></main>
  <script>
    const rows = {data_json};
    const classes = {json.dumps(SEVERITY_CLASSES)};
    const stateKey = "pothole-severity-review-v1";
    const saved = JSON.parse(localStorage.getItem(stateKey) || "{{}}");
    for (const row of rows) {{
      if (saved[row.object_id]) row.reviewed_severity = saved[row.object_id];
    }}
    const grid = document.getElementById("grid");
    const filter = document.getElementById("filter");
    const search = document.getElementById("search");
    const count = document.getElementById("count");
    function persist() {{
      const data = Object.fromEntries(rows.map(row => [row.object_id, row.reviewed_severity]));
      localStorage.setItem(stateKey, JSON.stringify(data));
    }}
    function render() {{
      const f = filter.value;
      const q = search.value.trim().toLowerCase();
      grid.innerHTML = "";
      let shown = 0;
      for (const row of rows) {{
        const matchesFilter = f === "all" || row.needs_review === f || row.reviewed_severity === f;
        const matchesSearch = !q || row.object_id.toLowerCase().includes(q) || row.source_filename.toLowerCase().includes(q);
        if (!matchesFilter || !matchesSearch) continue;
        shown += 1;
        const card = document.createElement("section");
        card.className = "card";
        const options = classes.map(name => `<option value="${{name}}" ${{row.reviewed_severity === name ? "selected" : ""}}>${{name.replaceAll("_", " ")}}</option>`).join("");
        card.innerHTML = `
          <img src="${{row.overlay_image}}" loading="lazy">
          <div class="meta">
            <div class="row"><strong>${{row.object_id}}</strong><span class="badge ${{row.needs_review}}">${{row.needs_review}}</span></div>
            <div class="row">
              <span>auto: ${{row.auto_severity.replaceAll("_", " ")}}</span>
              <select data-object-id="${{row.object_id}}">${{options}}</select>
            </div>
            <div class="stats">score ${{Number(row.severity_score).toFixed(2)}} | area ${{Number(row.bbox_area).toFixed(3)}} | dark ${{Number(row.bbox_dark_ratio).toFixed(2)}} | edge ${{Number(row.bbox_edge_density).toFixed(2)}} | ${{row.split}}</div>
          </div>`;
        grid.appendChild(card);
      }}
      count.textContent = `${{shown}} / ${{rows.length}} objects`;
      for (const select of grid.querySelectorAll("select[data-object-id]")) {{
        select.addEventListener("change", event => {{
          const row = rows.find(item => item.object_id === event.target.dataset.objectId);
          row.reviewed_severity = event.target.value;
          persist();
        }});
      }}
    }}
    function csvEscape(value) {{
      const text = String(value ?? "");
      return /[",\\n]/.test(text) ? `"${{text.replaceAll('"', '""')}}"` : text;
    }}
    document.getElementById("export").addEventListener("click", () => {{
      const fields = Object.keys(rows[0]);
      const csv = [fields.join(",")].concat(rows.map(row => fields.map(field => csvEscape(row[field])).join(","))).join("\\n");
      const blob = new Blob([csv], {{type: "text/csv"}});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "severity_labels_reviewed.csv";
      link.click();
      URL.revokeObjectURL(url);
    }});
    filter.addEventListener("change", render);
    search.addEventListener("input", render);
    render();
  </script>
</body>
</html>
"""
    (output_root / "review" / "review_app.html").write_text(html)


def write_yaml(output_root: Path):
    yaml = "\n".join(
        [
            f"path: {output_root.resolve()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: small_pothole",
            "  1: medium_pothole",
            "  2: severe_pothole",
            "",
        ]
    )
    (output_root / "data.yaml").write_text(yaml)


def write_train_script(output_root: Path):
    script = f"""#!/usr/bin/env bash
set -euo pipefail

export YOLO_CONFIG_DIR="${{YOLO_CONFIG_DIR:-/tmp/Ultralytics}}"
export MPLCONFIGDIR="${{MPLCONFIGDIR:-/tmp/matplotlib}}"

.venv-ml/bin/python ml/training/train_pothole_severity_yolov8m.py \\
  --data {output_root / 'data.yaml'} \\
  --epochs 70 \\
  --imgsz 640 \\
  --batch 8 \\
  --device auto
"""
    path = output_root / "train_yolov8m.sh"
    path.write_text(script)
    path.chmod(0o755)


def write_summary(
    output_root: Path,
    inspection: dict,
    rows: list[ObjectRow],
    selected_images: list[dict],
    copied: list[str],
):
    image_rows = inspection["images"]
    widths = [row["width"] for row in image_rows]
    heights = [row["height"] for row in image_rows]
    label_format = "unknown"
    if inspection["label_lengths"]:
        label_format = "YOLO bbox" if set(inspection["label_lengths"].keys()) == {5} else "mixed/segmentation-like"

    split_counts = Counter(row.split for row in rows)
    severity_counts = Counter(row.reviewed_severity for row in rows)
    auto_counts = Counter(row.auto_severity for row in rows)
    selected_image_counts = Counter()
    for row in rows:
        selected_image_counts[row.split] += 0
    for image_path in {row.source_image for row in rows}:
        split = next(row.split for row in rows if row.source_image == image_path)
        selected_image_counts[split] += 1

    summary = {
        "source_images": len(image_rows),
        "source_objects": len(inspection["objects"]),
        "source_splits": Counter(row["source_split"] for row in image_rows),
        "label_format": label_format,
        "label_value_counts": dict(inspection["label_lengths"]),
        "source_class_counts": dict(inspection["class_counts"]),
        "missing_labels": len(inspection["missing_labels"]),
        "empty_labels": len(inspection["empty_labels"]),
        "bad_images": len(inspection["bad_images"]),
        "unique_base_keys": len(set(row["base_key"] for row in image_rows)),
        "exact_duplicate_groups": len(inspection["exact_duplicates"]),
        "perceptual_duplicate_groups": len(inspection["perceptual_duplicates"]),
        "resolution": {
            "min_width": min(widths) if widths else None,
            "max_width": max(widths) if widths else None,
            "min_height": min(heights) if heights else None,
            "max_height": max(heights) if heights else None,
            "unique": sorted([list(item) for item in set(zip(widths, heights))])[:20],
        },
        "selected_images": len({row.source_image for row in rows}),
        "selected_objects": len(rows),
        "selected_image_split_counts": dict(selected_image_counts),
        "selected_object_split_counts": dict(split_counts),
        "reviewed_class_counts": dict(severity_counts),
        "auto_class_counts": dict(auto_counts),
        "copied_images": len(copied),
        "classes": SEVERITY_CLASSES,
    }

    analysis_dir = output_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    write_csv(analysis_dir / "selected_subset.csv", [asdict(row) for row in rows])
    write_csv(
        analysis_dir / "class_distribution.csv",
        [
            {"class": name, "objects": severity_counts.get(name, 0)}
            for name in SEVERITY_CLASSES
        ],
    )

    md = f"""# Pothole Severity Dataset Summary

## Source Dataset

- Source images: {summary["source_images"]}
- Source annotations/objects: {summary["source_objects"]}
- Existing format: {summary["label_format"]}
- Existing source classes: {summary["source_class_counts"]}
- Source splits: {dict(summary["source_splits"])}
- Missing labels: {summary["missing_labels"]}
- Empty labels: {summary["empty_labels"]}
- Bad/unreadable images: {summary["bad_images"]}
- Unique original base keys: {summary["unique_base_keys"]}
- Exact duplicate groups: {summary["exact_duplicate_groups"]}
- Perceptual duplicate groups: {summary["perceptual_duplicate_groups"]}
- Resolution range: {summary["resolution"]["min_width"]}x{summary["resolution"]["min_height"]} to {summary["resolution"]["max_width"]}x{summary["resolution"]["max_height"]}

## Generated Severity Subset

- Selected images: {summary["selected_images"]}
- Selected objects: {summary["selected_objects"]}
- Image splits: {summary["selected_image_split_counts"]}
- Object splits: {summary["selected_object_split_counts"]}
- Auto/reviewed class counts: {summary["reviewed_class_counts"]}

## Strategy

This subset is duplicate-aware. It first takes one strong representative per Roboflow original image key, then balances across estimated small, medium, and severe potholes. Ranking favors high-information examples: larger pothole spread, multiple objects, stronger local contrast, darker depression cues, edge density, and global brightness diversity.

## Label Format Decision

The source labels are YOLO bounding boxes, not segmentation masks. Use `yolov8m.pt` for detection. Do not use `yolov8m-seg.pt` unless polygon masks are added later.
"""
    (analysis_dir / "dataset_summary.md").write_text(md)
    return summary


def main():
    args = parse_args()
    source_root = Path(args.source_root)
    output_root = Path(args.output_root)
    if not source_root.exists():
        raise FileNotFoundError(f"Source root not found: {source_root}")

    inspection = inspect_dataset(source_root)
    objects = add_auto_severity(inspection["objects"])
    selected_images = choose_subset(inspection["images"], objects, args.subset_size, args.seed)
    split_by_source = assign_splits(selected_images, args.seed)
    overrides = load_review_overrides(Path(args.review_csv) if args.review_csv else None)
    rows = build_rows(selected_images, objects, split_by_source, overrides)

    reset_output_dirs(output_root)
    copied = copy_dataset(rows, output_root)

    by_image = defaultdict(list)
    for row in rows:
        by_image[row.source_image].append(row)
    review_images = []
    for source_image, object_rows in by_image.items():
        overlay_path = output_root / "review" / "images" / f"{Path(source_image).stem}.jpg"
        draw_overlay(Path(source_image), object_rows, overlay_path)
        review_images.append(overlay_path)
    if not args.quick:
        create_contact_sheets(review_images, output_root)

    write_csv(output_root / "severity_labels.csv", [asdict(row) for row in rows])
    write_review_app(output_root, rows, by_image)
    write_yaml(output_root)
    write_train_script(output_root)
    summary = write_summary(output_root, inspection, rows, selected_images, copied)

    print(json.dumps(summary, indent=2, default=str))
    print(f"\nReview app: {output_root / 'review' / 'review_app.html'}")
    print(f"YOLO data config: {output_root / 'data.yaml'}")
    print(f"CSV labels: {output_root / 'severity_labels.csv'}")


if __name__ == "__main__":
    main()
