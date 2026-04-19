import argparse
import sys
from pathlib import Path


YOLOV8_MODELS = {"n": "yolov8n.pt", "s": "yolov8s.pt", "m": "yolov8m.pt", "l": "yolov8l.pt", "x": "yolov8x.pt"}
YOLOV5_MODELS = {"n": "yolov5n.pt", "s": "yolov5s.pt", "m": "yolov5m.pt", "l": "yolov5l.pt", "x": "yolov5x.pt"}


def parse_args():
    parser = argparse.ArgumentParser(description="Train a YOLO road-damage detector (v5 or v8)")
    parser.add_argument("--data", required=True, help="Path to YOLO dataset YAML")
    parser.add_argument(
        "--model",
        default="yolov8n.pt",
        help="Base model checkpoint (e.g. yolov8n.pt, yolov5s.pt) or local .pt file",
    )
    parser.add_argument(
        "--version",
        choices=["v5", "v8"],
        default=None,
        help="Force YOLO version (auto-detected from --model name if omitted)",
    )
    parser.add_argument("--size", choices=["n", "s", "m", "l", "x"], default=None,
                        help="Model size shorthand (overrides --model backbone size)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default=None, help="cuda device id, 'cpu', or blank for auto")
    parser.add_argument("--project", default="ml/runs/detector")
    parser.add_argument("--name", default="road_damage")
    return parser.parse_args()


def detect_version(model_name: str) -> str:
    name = model_name.lower()
    if "yolov5" in name:
        return "v5"
    return "v8"


def resolve_model(args) -> tuple[str, str]:
    """Return (model_checkpoint, version)."""
    version = args.version or detect_version(args.model)
    model = args.model
    if args.size:
        size = args.size
        model = YOLOV5_MODELS[size] if version == "v5" else YOLOV8_MODELS[size]
    return model, version


def train_v8(model_name: str, args):
    from ultralytics import YOLO

    project_dir = Path(args.project)
    project_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(model_name)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(project_dir),
        name=args.name,
    )
    best_path = project_dir / args.name / "weights" / "best.pt"
    print(f"Training finished. Best weights at: {best_path}")
    return best_path


def train_v5(model_name: str, args):
    try:
        import torch
    except ImportError:
        sys.exit("torch is required for YOLOv5 training. Install it via requirements-ml.txt")

    project_dir = Path(args.project)
    project_dir.mkdir(parents=True, exist_ok=True)

    # YOLOv5 via ultralytics unified API (ultralytics>=8.x supports yolov5*.pt)
    try:
        from ultralytics import YOLO
        model = YOLO(model_name)
        model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            project=str(project_dir),
            name=args.name,
        )
        best_path = project_dir / args.name / "weights" / "best.pt"
        print(f"Training finished. Best weights at: {best_path}")
        return best_path
    except Exception as exc:
        print(f"ultralytics unified API failed ({exc}), falling back to torch.hub YOLOv5...")

    # Fallback: original YOLOv5 repo via torch.hub
    model = torch.hub.load("ultralytics/yolov5", model_name.replace(".pt", ""), pretrained=True)
    print("torch.hub YOLOv5 loaded — use the official YOLOv5 train.py for full training control.")
    print("  git clone https://github.com/ultralytics/yolov5 && cd yolov5")
    print(f"  python train.py --data {args.data} --weights {model_name} "
          f"--epochs {args.epochs} --imgsz {args.imgsz} --batch-size {args.batch}")
    sys.exit(0)


def main():
    args = parse_args()
    model_name, version = resolve_model(args)
    print(f"YOLO version: {version}  |  checkpoint: {model_name}")

    if version == "v5":
        train_v5(model_name, args)
    else:
        train_v8(model_name, args)


if __name__ == "__main__":
    main()
