import argparse
import shutil
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Copy trained detector weights into backend runtime path")
    parser.add_argument("--from", dest="source", required=True, help="Path to trained best.pt")
    parser.add_argument(
        "--to",
        dest="target",
        default="backend/models/road_detector/best.pt",
        help="Runtime destination for the backend",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        raise FileNotFoundError(f"Source weights not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Copied {source} -> {target}")


if __name__ == "__main__":
    main()
