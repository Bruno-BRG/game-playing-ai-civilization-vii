# Civilization VII detection dataset

This directory defines the first YOLO26 object-detection taxonomy. Images and labels are
intentionally ignored by Git because game screenshots may contain copyrighted assets and
the dataset can become large. Publish an approved dataset separately, for example through
the project's chosen external dataset host, and record its exact revision here.

Expected layout:

```text
images/{train,val,test}/*.jpg
labels/{train,val,test}/*.txt
```

Capture at one fixed game resolution and UI scale for the first model. Do not mix languages,
resolution profiles, or heavily modded UIs until the baseline is measurable. Split by play
session rather than randomly by frame so near-identical consecutive frames do not leak from
training into validation.

See [docs/dataset.md](../../docs/dataset.md) for the annotation contract.
