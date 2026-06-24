# TerraWard Vision Layer — design and honest roadmap

This document plans the on-device vision layer: letting a farmer point a camera at a leaf, a
trap, or a bee frame and get a grounded read — *late-blight lesion*, *Colorado potato beetle*,
*Varroa mite load* — that feeds the same risk board and trust loop as the weather modules.

It is deliberately a **design document, not a shipped feature**. No vision model ships with
TerraWard today, and this file is honest about why, and about the real work between here and a
model a farmer should trust.

## Why this is a climb, not a module

Every other TerraWard module is grounded in a published threshold (a THI table, the Mills
criteria, a degree-day model). You can read the paper, encode the numbers, and test the logic
against known inputs. A vision model is different: its "thresholds" are millions of learned
weights, and they are only as good as the data they were trained on. That changes the work:

- It needs **labelled datasets** — thousands of correctly identified field images per class.
- It needs **training and validation**, not just coding.
- It is only honest if its **field accuracy is measured**, because a model that scores 99% on a
  clean lab dataset can collapse on a real phone photo in mud and shadow (the *domain gap*).
- The cost of a wrong answer is asymmetric: a false "all clear" on blight is worse than no scan
  at all, because it replaces healthy caution with false confidence.

So the rule for this layer is the same as the rest of the tool, only stricter: **ship nothing
until it is validated, and never let a model speak with more confidence than its measured field
performance earns.**

## The seam that already exists

The plug points are built and tested; only the model is missing.

- `Detection` (dataclass): `label`, `confidence` (0–1), optional `note`.
- `@detector("name")`: registers a detector function `fn(image_path, crop) -> List[Detection]`.
- `run_scan(...)`: runs a detector over one image; a confident detection becomes an alert **and**
  is auto-logged as a confirmed sighting, so the camera feeds the existing
  `--report-sighting` / `--accuracy` precision–recall loop.
- CLI: `--scan-image PATH [--scan-crop CROP] [--detector NAME]`.
- The shipped `placeholder` detector returns a single informational "no model installed" note and
  fails gracefully. That is the honest default.

A real model plugs in by registering a new detector — no core changes required:

```python
@detector("blight-v1")
def blight_v1(image_path, crop=None):
    model = load_model("models/blight-v1.onnx")   # see "Loading models safely" below
    score = model.run(preprocess(image_path))
    if score < 0.85:                               # below measured field threshold -> say nothing
        return [Detection("late_blight", score, note="no confident lesion")]
    return [Detection("late_blight", score, note="possible blight lesion — scout to confirm")]
```

## Loading models safely

Model files are untrusted input, exactly like the weather API and the config file.

- **Never `pickle`/`torch.load` an untrusted checkpoint** — pickle executes arbitrary code on load.
- Prefer formats that cannot execute code: **`safetensors`** for weights, **ONNX** or **TFLite**
  for full models. Verify a checksum before loading (the repo already ships `scripts/checksums.sh`).
- Keep inference **fully local**. No image and no embedding leaves the device — consistent with
  `DATA_GOVERNANCE.md`. Vision must not become the thing that quietly phones home.

## Model approach

- **On-device, small, quantized.** Target a phone or a Raspberry Pi in a shed, offline. That means
  MobileNet/EfficientNet-Lite-class backbones, or a small custom CNN, exported to ONNX/TFLite and
  int8-quantized — not a server GPU model.
- **Transfer learning** from a general image backbone, fine-tuned per task, is the realistic path
  to decent accuracy on a small field dataset.
- **One narrow task first.** A single well-validated detector (e.g. "blight lesion present:
  yes/no") is worth more than ten shaky multi-class ones.

## Datasets — assessed honestly

- **PlantVillage** — large, popular, but **lab-condition** (single leaves, plain backgrounds).
  Models trained on it alone over-promise in the field. Useful for pre-training, not for the final
  field threshold.
- **PlantDoc** and similar field-image sets — smaller, messier, **closer to reality**; better for
  validation and fine-tuning.
- **Pest ID** — observation platforms (e.g. iNaturalist exports) give varied real images but noisy
  labels; they need cleaning.
- **Varroa** — the hardest. Counting mites on a bee or a sticky board needs **controlled imaging**
  (known distance/lighting) and a purpose-built dataset; general web images will not do.

In every case, the headline accuracy in a dataset's own paper is an **upper bound**, not what a
farmer will see. Field validation is the real test.

## Validation and the trust loop

The accuracy machinery already exists and should gate every model:

1. Run the detector in the field; each confident detection is logged as a sighting.
2. The farmer confirms or corrects it (`--report-sighting`).
3. `--accuracy` reports precision and recall against ground truth.
4. A detector is only promoted from experimental to default once its **field** precision/recall
   clears a stated bar — and the bar for disease "all clear" is high, because false negatives cost
   a crop.

## Phased roadmap

1. **Base camp (done).** Detector interface, `run_scan`, trust-loop wiring, graceful no-model
   default, this document.
2. **First real detector.** One narrow, field-validated model (proposed: late-blight lesion
   presence), shipped as a separately-downloaded `safetensors`/ONNX file with a checksum — never
   bundled until its field numbers are published here.
3. **Expand classes.** Scab lesions, the named pests already modelled by degree-days, so vision and
   phenology corroborate each other.
4. **Varroa counting.** Only with a controlled-imaging protocol and a purpose-built dataset.

## The honest stance

TerraWard would rather say *"no model installed"* than guess. When a model does arrive, it will
carry its measured field accuracy in plain sight, defer to silence below its confidence threshold,
and run entirely on the farmer's own device. The socket is wired and waiting; building the bulb is
the climb — and it will be done grounded, or not at all.
