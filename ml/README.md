# Road Models

This workspace is where we train and plug in the real road-analysis models.

## Planned stack

1. Detector: Ultralytics YOLO fine-tuned for potholes and road damage
2. Optional depth helper: Depth Anything V2 or MiDaS
3. Optional severity model: small regressor/classifier trained on your own labels

## Current integration points

- Detector weights path: `backend/models/road_detector/best.pt`
- Depth checkpoint env var: `ROAD_DEPTH_MODEL`
- Severity model path: `backend/models/road_severity/severity_model.joblib`
- Backend model status endpoint: `GET /modeling/status` (admin only)

## Step 1: Train the detector

Install optional ML dependencies:

```bash
pip install -r backend/requirements-ml.txt
```

Prepare a YOLO-format dataset. A typical layout is:

```text
ml/data/road_damage/
  images/
    train/
    val/
  labels/
    train/
    val/
```

Use the example dataset config in [`ml/config/road_damage.dataset.example.yaml`](/Users/shreyas/Documents/New%20project/hotspot-prioritizer/ml/config/road_damage.dataset.example.yaml) and copy it to your real path.

Create the folder tree:

```bash
python ml/tools/create_dataset_dirs.py
```

Validate your labels before training:

```bash
python ml/tools/validate_yolo_dataset.py --root ml/data/road_damage --num-classes 5
```

Train with **YOLOv8** (recommended, default):

```bash
python ml/training/train_detector.py \
  --data ml/config/road_damage.dataset.example.yaml \
  --model yolov8n.pt \
  --epochs 100 \
  --imgsz 640
```

Train with **YOLOv5** (use `--version v5` or any `yolov5*.pt` name):

```bash
python ml/training/train_detector.py \
  --data ml/config/road_damage.dataset.example.yaml \
  --model yolov5s.pt \
  --version v5 \
  --epochs 100 \
  --imgsz 640
```

Model size shorthand (`--size n/s/m/l/x`) also works with either version:

```bash
python ml/training/train_detector.py \
  --data ml/config/road_damage.dataset.example.yaml \
  --version v8 --size s --epochs 100
```

After training, copy the best weights to:

```bash
mkdir -p backend/models/road_detector
cp ml/runs/detector/<run-name>/weights/best.pt backend/models/road_detector/best.pt
```

Or use:

```bash
python ml/tools/promote_detector_weights.py --from ml/runs/detector/<run-name>/weights/best.pt
```

## Step 2: Add the depth helper

No training is required for the first pass. Set one of these checkpoints in `backend/.env`:

- `depth-anything/Depth-Anything-V2-base-hf`
- `LiheYoung/depth-anything-base-hf`

The backend will use the depth model only when `transformers` is installed and the checkpoint is reachable.

## Step 3: Train the severity model

Create a CSV with one row per report image or report instance. Required columns:

- `depth_score`
- `spread_score`
- `emotion_score`
- `location_score`
- `upvote_score`
- `severity_score`

Train:

```bash
python ml/training/train_severity.py \
  --csv /absolute/path/to/severity_labels.csv \
  --output backend/models/road_severity/severity_model.joblib
```

## Manual work you need to do

- Gather and label road images.
- Decide the final classes for detection.
- Provide severity labels if you want a real learned severity model.
- Run the training commands on a machine with enough CPU/GPU and internet access for model downloads.
- If you do not already have annotations, use a labeling tool such as CVAT, Label Studio, or Roboflow and export in YOLO format.

## Recommended datasets

- Start with RDD2022 for road damage.
- Add your own city/device images before production use.

## Notes

- The backend already works without these models and falls back to heuristic scoring.
- Once the detector/severity weights are in place, the backend will use them automatically.
