# Pothole Severity Labeling Guide

Use this guide while reviewing `ml/data/pothole_severity/review/review_app.html`.

The goal is fast, consistent severity labels for YOLO training. Label the visible pothole hazard inside the existing bounding box. Do not redraw boxes unless the original box is clearly unusable; in this sprint, correcting severity class is the highest-value work.

## Classes

### `small_pothole`

Use when the pothole is a minor surface defect.

- Small road occupancy, usually under about 8% of the image.
- Shallow-looking depression or broken surface.
- A vehicle could likely avoid or pass over it with low risk.
- Often a compact isolated patch, not a lane-wide damaged region.

### `medium_pothole`

Use when the pothole is clearly hazardous but not extreme.

- Moderate spread, roughly 8-22% of the image or a meaningful part of a lane.
- Visible depression, rough edges, or dark interior.
- Likely uncomfortable or risky for two-wheelers and small vehicles.
- More than a crack or patch, but not a major road collapse.

### `severe_pothole`

Use when the pothole is a major hazard.

- Large spread, often above 22% of the image or occupying a large lane region.
- Strong dark depression, broken edges, water-filled cavity, or clustered damage.
- Difficult to avoid, dangerous for motorcycles, or likely to damage vehicles.
- Multiple connected holes should be severe if they form one broad hazardous region.

## Optional Future Classes

Do not add these during the 3-hour sprint unless you have extra time and many examples.

- `crack`: thin linear road fracture without a clear depression.
- `alligator_crack`: dense connected cracking pattern, usually not an open pothole.
- `critical_pothole`: road collapse or extreme danger. For now, map these to `severe_pothole` to keep enough examples per class.

## Fast Review Rules

1. Open `ml/data/pothole_severity/review/review_app.html`.
2. Start with the filter `high-priority boundaries`; these are examples near class thresholds and are most likely to need correction.
3. Change only obvious mistakes. If the auto label is plausible, leave it.
4. Then review `severe_pothole` and `small_pothole` filters for extreme errors.
5. Export `severity_labels_reviewed.csv` from the page.
6. Rebuild the dataset with:

```bash
.venv-ml/bin/python ml/tools/prepare_pothole_severity_dataset.py \
  --review-csv /path/to/severity_labels_reviewed.csv \
  --quick
```

## Consistency Notes

- Prefer the risk to a road user over exact pixel size when size and visual severity disagree.
- If a box contains several connected potholes, label based on the combined hazard.
- If a box is too loose but still mostly contains the pothole, label severity normally.
- If a box is clearly on non-pothole background, leave it as the closest severity only if rare; otherwise remove that row from the reviewed CSV before rebuilding.
- Keep the three classes reasonably balanced. A useful training subset should not collapse into mostly `medium_pothole`.
