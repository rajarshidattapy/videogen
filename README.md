# AI Viral Video Generator

Generate a consent-based talking-head video from a script and a reference image.
The video pipeline is self-hosted: Sarvam creates the speech, LivePortrait adds
natural head motion, MuseTalk lip-syncs the mouth, and local post-processing
produces the final MP4.

```text
script -> Sarvam TTS -> audio preparation ------------------+
                                                          |
reference image + idle driving clip -> LivePortrait ------+-> MuseTalk -> restore + mux -> MP4
                                                          |
                                   (LivePortrait is optional for the first version)
```

## Architecture

| Component | Input | Output | Responsibility |
| --- | --- | --- | --- |
| Sarvam TTS | Script text | Speech audio | Voice generation |
| LivePortrait | Reference image + driving video | Moving base video | Head pose, blinks, and subtle expression |
| MuseTalk 1.5 | Image or video + audio | Lip-synced video | Repaints the mouth region to match speech |
| Post-processing | Lip-synced frames + master audio | `talking_head.mp4` | Facial restoration, temporal smoothing, encoding, and audio muxing |

MuseTalk can use a single still image directly, which makes **image + audio ->
MuseTalk** the fastest proof of concept. That produces a mostly static head with
a moving mouth. Add LivePortrait for natural head movement and blinking once the
lip-sync path is working.

### Model choices

| Model | Use it for | Notes |
| --- | --- | --- |
| **MuseTalk 1.5** | Default lip-sync model | Best initial choice; supports a fast avatar-precompute path. |
| **LatentSync 1.6** | Higher-detail lip-sync evaluation | Consider it when MuseTalk's mouth detail is the quality limit; it needs more GPU. |
| **LivePortrait** | Motion transfer | Drives idle head movement from a reusable clip or motion template. |
| **SadTalker** | First-day smoke test | Simple image-to-audio path, but not the preferred production quality. |
| **InfiniteTalk** | Body motion experiments | Heavy option for torso/body movement rather than a focused talking head. |

Keep the lip-sync engine behind an interface so MuseTalk and LatentSync can be
compared without changing the rest of the pipeline.

## Requirements

- An NVIDIA CUDA GPU. A 4 GB card can run short fp16 experiments, but 16 GB VRAM
  (for example L4, A10, or 4090) is the practical target.
- Linux or a Linux-compatible CUDA environment such as WSL2.
- Python **3.11.9** for both model environments.
- FFmpeg available on `PATH` (`FFMPEG_PATH=/usr/bin` for MuseTalk when needed).
- Git LFS for LivePortrait weights.
- A Sarvam API key in `.env`:

  ```dotenv
  SARVAM_API_KEY=...
  ```

Use separate environments for MuseTalk and LivePortrait. MuseTalk has tightly
pinned Torch/MMCV dependencies, while LivePortrait has its own dependency tree;
combining them makes version conflicts much more likely.

## Install the model environments

[`uv`](https://docs.astral.sh/uv/) is the quickest way to obtain the exact Python
version and create environments. Plain `venv` is fine when Python 3.11.9 is
already installed.

```bash
# MuseTalk
git clone https://github.com/TMElyralab/MuseTalk vendor/MuseTalk
uv venv vendor/MuseTalk/.venv --python 3.11.9
source vendor/MuseTalk/.venv/bin/activate
uv pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
  --index-url https://download.pytorch.org/whl/cu118
uv pip install -r vendor/MuseTalk/requirements.txt
uv pip install mmengine mmcv==2.0.1 \
  -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.0/index.html
uv pip install mmdet==3.1.0 mmpose==1.1.0 numpy==1.23.5
(cd vendor/MuseTalk && sh ./download_weights.sh)
deactivate

# LivePortrait
git clone https://github.com/KwaiVGI/LivePortrait vendor/LivePortrait
uv venv vendor/LivePortrait/.venv --python 3.11.9
source vendor/LivePortrait/.venv/bin/activate
uv pip install -r vendor/LivePortrait/requirements.txt
git lfs install
git clone https://huggingface.co/KwaiVGI/LivePortrait vendor/LivePortrait/pretrained_weights
deactivate
```

Before integrating either model, verify that the weights were downloaded and run
each upstream project's example inference command. A partial weight download is a
more common failure than a model bug.

> **Dependency note:** MuseTalk's `numpy==1.23.5` pin is important. Its pinned
> MMCV version predates the NumPy 2 ABI, and TensorFlow 2.12 also requires
> `numpy<1.24`. Run `pip check` after changing the environment.

## Pipeline stages

### 0. Generate and prepare audio

Use Sarvam Bulbul v3 to create speech. For lip-sync, a slightly slower delivery
(`pace` around `0.90` to `0.95`) gives the model more frames per phoneme.

- Split scripts exceeding 2,500 characters on sentence boundaries, never in the
  middle of a word.
- Create two normalized copies: a **16 kHz mono** file for Whisper features and a
  **24 kHz** master file for the final mux.
- Add 200 ms of lead and trail padding; without it, the first and final phonemes
  can be visibly clipped.

```bash
# Lip-sync input
ffmpeg -y -i tts_raw.wav -ac 1 -ar 16000 \
  -af "apad=pad_dur=0.2,adelay=200|200" audio_16k.wav

# Final-output master
ffmpeg -y -i tts_raw.wav -ac 1 -ar 24000 \
  -af "apad=pad_dur=0.2,adelay=200|200" audio_master.wav
```

### 1. Create the base motion (optional for v0)

Give LivePortrait a reference image and a short idle driving clip. Record drivers
with subtle head turns, natural blinks, and a closed or barely parted mouth. A
driver with obvious mouth movement conflicts with the later lip-sync pass.

Make the driving video at least as long as the audio. Looping it forward and then
in reverse avoids a visible seam; output must be constant-frame-rate 25 fps.

```bash
ffmpeg -y -i driver.mp4 -filter_complex "[0]reverse[r];[0][r]concat=n=2:v=1[v]" \
  -map "[v]" ping_pong.mp4
ffmpeg -y -stream_loop -1 -i ping_pong.mp4 -t "$DURATION" \
  -r 25 -vsync cfr driver_fit.mp4
```

LivePortrait writes a motion-template `.pkl` alongside a driver. Cache and reuse
that template: subsequent renders can apply it to another reference image without
extracting the motion again.

### 2. Lip-sync with MuseTalk

MuseTalk accepts either the reference image (v0) or the LivePortrait base video
(full pipeline), together with `audio_16k.wav`. It expects a fixed **25 fps**
input. Variable-frame-rate video causes lip-sync drift that looks like an
inference failure.

For a product path, use MuseTalk's real-time inference mode. It separates a slow,
one-time avatar preparation step (face detection, crop, and VAE latent caching)
from fast audio renders. Re-run preparation whenever the base video or
`bbox_shift` changes; key that cache by the reference image, driver, and
`bbox_shift`.

`bbox_shift` is the most important mouth-tuning control in MuseTalk v1.0. Start
at the default, read the valid range printed for that face, and tune within it:
positive values open the mask more; negative values constrain it. Check the
current v1.5 command help rather than assuming the same flag names.

### 3. Restore and encode

MuseTalk's mouth region is low resolution and frames are generated independently.
Post-process only the face/mouth crop:

- Restore the face crop with GFPGAN or CodeFormer. Keep CodeFormer fidelity around
  `0.7` to `0.8`; more aggressive restoration can change the subject's identity.
- Reduce mouth jitter with a three-frame EMA within the mouth mask only:

  ```text
  smoothed = 0.25 * previous + 0.50 * current + 0.25 * next
  ```

- Encode at 25 fps and mux in `audio_master.wav`:

  ```bash
  ffmpeg -y -framerate 25 -i frames/%08d.png -i audio_master.wav \
    -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -shortest out/talking_head.mp4
  ```

## Reference-image requirements

Validate the source on upload. Most output-quality problems begin with a weak
reference image.

**Accept:** one front-facing person (within roughly 15 degrees of frontal), both
eyes visible, mouth closed or barely open, even lighting, a sharp face at least
512 px wide, and no obstruction.

**Reject:** profiles, wide-open mouths or visible teeth, hands or microphones on
the face, heavy glasses glare, motion blur, hats covering the forehead, multiple
faces, and watermarks across the face.

MuseTalk is optimized for real human faces. Route illustrations and animal images
to a LivePortrait-only path, or reject them rather than silently producing poor
lip-sync.

## Recommended service design

The prepare/render split mirrors the model workflow and avoids repeated work:

```text
POST /avatars  { image }                    -> { avatar_id }
  Validate image, create base motion, prepare and cache MuseTalk avatar data.

POST /render   { avatar_id, text|audio, lang, speaker } -> { job_id }
  Create/prep audio, run lip-sync, post-process, and save the video.

GET /jobs/{job_id}                          -> { status, video_url }
```

Use a single GPU worker with models kept in memory and serialize jobs per GPU.
Cache prepared avatar data on disk, cap base-video length (about 30 seconds is a
useful starting point), and evict old caches with an LRU policy.

## Quality evaluation

Build the evaluation harness early. For five fixed sentences per language, record
results by `(avatar_id, model, bbox_shift, restoration_fidelity)`:

- **LSE-D / LSE-C:** SyncNet lip-sync error and confidence; lower LSE-D and higher
  LSE-C are better.
- **Identity:** ArcFace cosine similarity between the reference and sampled output
  frames. Investigate scores below `0.7`.
- **Temporal stability:** mean pixel change inside the mouth mask between frames.
- **Human A/B review:** two raters scoring visual quality on a five-point scale.

Indic speech is workable but deserves dedicated evaluation. Slow the Sarvam pace
slightly first, then compare against LatentSync when rapid retroflex or aspirated
phonemes look weak.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Mouth barely opens | Inpaint mask is too tight | Increase `bbox_shift` within the valid range. |
| Mouth does not close on p/b/m sounds | Inpaint mask is too broad | Reduce `bbox_shift`, typically into the negative range. |
| Sync drifts through the clip | Base video is variable-frame-rate | Re-encode with `-r 25 -vsync cfr`. |
| A jump appears when motion repeats | Driver was simply looped | Use a ping-pong loop. |
| Mouth region shimmers | Per-frame inference jitter | Apply EMA smoothing inside the mouth mask. |
| Face identity drifts | Restoration is too aggressive | Lower restoration fidelity; restore the face crop only. |
| Lower face is blurry | MuseTalk's mouth resolution limit | Test face-crop restoration or evaluate LatentSync. |
| Speech plays but the mouth is static | Audio path or sample rate is wrong | Confirm a 16 kHz mono audio input reaches MuseTalk. |
| Imports fail after setup | MuseTalk dependency drift | Recreate the pinned environment and run `pip check`. |

## Delivery milestones

1. **M0:** MuseTalk from a still reference image plus Sarvam audio.
2. **M1:** Evaluation harness and a `bbox_shift` sweep.
3. **M2:** LivePortrait motion, ping-pong driving clips, and cached templates.
4. **M3:** Restoration, jitter smoothing, and final encoding.
5. **M4:** Prepared-avatar service, queue, and cache eviction.
6. **M5:** LatentSync behind the same lip-sync interface and an evidence-based
   comparison.

Do not build the service layer before the still-image and motion paths produce
good, repeatable output.

## Consent, safety, and licensing

This workflow can make a photo appear to say arbitrary words. Before making it
available to users:

- Obtain explicit, recorded consent from the person depicted—not merely from the
  uploader.
- Clearly disclose that output is AI-generated; add provenance metadata and
  consider a visible watermark by default.
- Retain the reference image and generation log for every output.
- Review the licences for all model weights and bundled assets before commercial
  use; upstream code licences alone are not sufficient.

## Upstream resources

- [MuseTalk](https://github.com/TMElyralab/MuseTalk)
- [LivePortrait](https://github.com/KwaiVGI/LivePortrait)
- [Sarvam AI documentation](https://docs.sarvam.ai)
