from pathlib import Path


DIRECTORIES = [
    "ml/data/road_damage/images/train",
    "ml/data/road_damage/images/val",
    "ml/data/road_damage/labels/train",
    "ml/data/road_damage/labels/val",
]


def main():
    for directory in DIRECTORIES:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("")
        print(f"Ready: {path}")


if __name__ == "__main__":
    main()
