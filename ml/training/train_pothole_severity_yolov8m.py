import argparse
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLOv8m for pothole severity detection.")
    parser.add_argument("--data", default="ml/data/pothole_severity/data.yaml")
    parser.add_argument("--model", default="yolov8m.pt")
    parser.add_argument("--epochs", type=int, default=70)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", default="8", help="Batch size integer or 'auto'.")
    parser.add_argument("--device", default="auto", help="'auto', 'cpu', cuda id, or mps where available.")
    parser.add_argument("--project", default="ml/runs/pothole_severity")
    parser.add_argument("--name", default="yolov8m_severity")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--freeze", type=int, default=10)
    return parser.parse_args()


def normalize_device(device: str):
    if device == "auto":
        return None
    return device


def normalize_batch(batch: str):
    if batch == "auto":
        return -1
    return int(batch)


def main():
    args = parse_args()

    from ultralytics import YOLO

    project = Path(args.project).resolve()
    project.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=normalize_batch(args.batch),
        device=normalize_device(args.device),
        project=str(project),
        name=args.name,
        workers=args.workers,
        resume=args.resume,
        patience=18,
        pretrained=True,
        optimizer="AdamW",
        cos_lr=True,
        lr0=0.0012,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3,
        warmup_momentum=0.8,
        box=7.5,
        cls=1.0,
        dfl=1.5,
        freeze=args.freeze,
        close_mosaic=10,
        cache="disk",
        hsv_h=0.015,
        hsv_s=0.45,
        hsv_v=0.30,
        degrees=4.0,
        translate=0.08,
        scale=0.45,
        shear=1.5,
        perspective=0.0004,
        fliplr=0.5,
        flipud=0.0,
        mosaic=0.85,
        mixup=0.05,
        copy_paste=0.0,
        erasing=0.15,
        seed=42,
        deterministic=True,
        val=True,
        plots=True,
    )

    best_path = project / args.name / "weights" / "best.pt"
    print(f"Best weights: {best_path}")


if __name__ == "__main__":
    main()
