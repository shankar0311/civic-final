import argparse
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a YOLO-format dataset")
    parser.add_argument("--root", required=True, help="Dataset root, e.g. ml/data/road_damage")
    parser.add_argument("--num-classes", type=int, default=5)
    return parser.parse_args()


def validate_split(root: Path, split: str, num_classes: int) -> list[str]:
    image_dir = root / "images" / split
    label_dir = root / "labels" / split
    errors: list[str] = []

    if not image_dir.exists():
        errors.append(f"Missing image directory: {image_dir}")
        return errors
    if not label_dir.exists():
        errors.append(f"Missing label directory: {label_dir}")
        return errors

    images = [path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS]
    if not images:
        errors.append(f"No images found in {image_dir}")
        return errors

    for image_path in images:
        label_path = label_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            errors.append(f"Missing label for image: {image_path.name}")
            continue

        lines = [line.strip() for line in label_path.read_text().splitlines() if line.strip()]
        for line_no, line in enumerate(lines, start=1):
            parts = line.split()
            if len(parts) != 5:
                errors.append(f"{label_path}:{line_no} expected 5 values, got {len(parts)}")
                continue

            try:
                cls_id = int(parts[0])
                values = [float(value) for value in parts[1:]]
            except ValueError:
                errors.append(f"{label_path}:{line_no} contains non-numeric values")
                continue

            if cls_id < 0 or cls_id >= num_classes:
                errors.append(f"{label_path}:{line_no} invalid class id {cls_id}")

            for value in values:
                if value < 0.0 or value > 1.0:
                    errors.append(f"{label_path}:{line_no} normalized box value out of range: {value}")

    return errors


def main():
    args = parse_args()
    root = Path(args.root)

    all_errors: list[str] = []
    for split in ("train", "val"):
        all_errors.extend(validate_split(root, split, args.num_classes))

    if all_errors:
        print("Dataset validation failed:")
        for error in all_errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Dataset validation passed.")


if __name__ == "__main__":
    main()
