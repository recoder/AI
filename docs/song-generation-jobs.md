# Song-generation jobs and runners

Status: initial version 1 contract; runners and installers are not implemented yet. Establish this interface before installing music tools. Tool-specific translations must be verified against the selected upstream revisions.

## Layout and invocation

Each tool gets a Python runner under `<workspace>/bin/`: `yue.py`, `ace-step.py`, `levo.py`, and `heartmula.py`. With the current workspace root, this means `D:\AI\bin`. Paths derive from workspace configuration when bootstrap is implemented.

The intended invocation is:

```powershell
python D:\AI\bin\ace-step.py .\songs\night-drive.md
python D:\AI\bin\ace-step.py .\songs\night-drive.md --validate
python D:\AI\bin\ace-step.py .\songs\night-drive.md --dry-run
```

Bootstrap will provide a runner environment through `uv`; each adapter launches the tool's own configured runtime. Shared parsing/configuration behavior lives in reusable Python helpers. Runners translate jobs into upstream CLI/API calls rather than embedding installation logic.

`--validate` checks syntax, flavor, settings, and configured paths. `--dry-run` additionally displays the translated request or argument list. Neither loads models, downloads files, starts a service, or generates audio. Generation runs must fail clearly when dependencies/models are missing and name the relevant repair command once available.

## Markdown job structure

A job is a UTF-8 `.md` file with optional YAML frontmatter at the beginning, exactly one top-level H1 song title, a prose generation prompt after that title, and optional named fenced blocks carrying separate generation data. The title is metadata and an output label; it is not automatically added to lyrics or the prompt.

````markdown
---
version: 1
tool: ace-step
seed: 42
duration_seconds: 90
steps: 50
---
# Night Drive

A reflective synth-pop song with warm analog textures, a steady groove,
and an intimate lead vocal. Build toward a wide, hopeful chorus.

```song-positive-style
synth-pop, warm analog synths, intimate vocals, steady groove
```

```song-lyrics
[Verse]
Streetlights trace the road ahead
All the words we never said

[Chorus]
We keep moving through the night
Till the morning turns to light
```

```song-negative-prompt
harsh distortion, crowd noise
```
````

This is a syntax illustration, not a promise that every ACE-Step revision accepts all shown controls. A runnable example must use only fields and blocks supported by its finalized flavor.

Frontmatter holds small scalar tuning values and optional short lists; long lyrics, styles, and other generation data belong in fences. `version` defaults to `1`. `tool`, when supplied, must match the invoked runner; when omitted, the runner selects its own flavor. There is no separate frontmatter title.

The shared parameter names reserve `seed`, `duration_seconds`, `steps`, `guidance_scale`, `temperature`, `top_p`, and `top_k`. These names have common meanings, but support and numeric ranges are flavor-specific. A tool is not required to implement every parameter. Additional tuning keys belong in a small `tool_options` mapping and must be explicitly allowlisted by that adapter. Machine paths, executable choices, and model locations belong in runner configuration.

The prompt is the ordered Markdown content after the H1 with named data fences removed, trimmed only at its outer edges. Paragraph breaks and other Markdown remain intact; no HTML rendering or automatic rewriting occurs. Require a nonempty prompt, even when a flavor primarily consumes lyrics or tags. Any other H1 outside a fence is an error. Title-like lines inside lyrics remain literal data.

Use these fence identifiers exactly:

| Fence | Content |
| --- | --- |
| `song-positive-style` | Dedicated positive style text or tags; interpretation belongs to the flavor. |
| `song-negative-prompt` | Undesired attributes for tools that support a negative input. |
| `song-lyrics` | Literal lyrics, preserving line breaks and section markers. |
| `song-reference-audio` | One file path per nonempty line, resolved relative to the job file. |

Use ordinary Markdown fenced-code syntax, with no extra attributes on these identifiers. Block contents are literal data and are never executed. Reject duplicate named blocks, unknown `song-*` identifiers, and unclosed fences. Unrecognized ordinary code fences are errors in version 1 to prevent accidentally sending code as prompt text. Extensions must be documented by their flavor before use. Use a Markdown parser that understands fences rather than extracting titles with a global regular expression.

Parse frontmatter/configuration as safe YAML mappings; reject duplicate keys and executable YAML tags. Reject unknown keys, unsupported controls/blocks, invalid types/ranges, and incompatible combinations before inference. Error messages identify the file and offending field/block. Missing optional settings stay unspecified unless the flavor defines a default; an explicit null is invalid unless documented by that flavor.

## Per-tool flavors

All flavors share document structure and runner behavior. They differ in accepted tuning keys, required blocks, and translation. The following are proposed adapter contracts, not confirmed upstream CLI flags:

| Flavor / runner | Proposed translation | Work to finalize |
| --- | --- | --- |
| `yue` / `yue.py` | Lyrics from `song-lyrics`; style from `song-positive-style`, or the body prompt when absent. | Select YuE generation; validate lyrics/section format, sampling controls, and reference support. |
| `ace-step` / `ace-step.py` | Body becomes the caption; optional style block appends with a paragraph break; lyrics remain separate. | Confirm selected version's duration, steps, guidance, negative input, and instrumental behavior. |
| `levo` / `levo.py` | Body becomes the description; optional style appends with a paragraph break; lyrics and reference paths become separate structured inputs. | Confirm request schema, required lyric structure, controls, and reference modes. |
| `heartmula` / `heartmula.py` | Lyrics remain separate; explicit style block becomes tags, otherwise the body supplies the style text. | Confirm tag normalization, duration/sampling controls, and required model/codec inputs. |

For YuE and HeartMuLa, an explicit style block supplies the positive conditioning; the body remains recorded creative context if the selected upstream interface has no additional prompt field. The runner must report this translation in dry-run output and run metadata. It must not secretly use another model to turn prose into tags or lyrics.

Do not silently discard an unsupported negative prompt, reference, tuning value, or extension. Fail with an explanation of what the selected flavor accepts. Preserve lyrics and reference order; any required normalization must be documented and visible in dry-run output.

Each finalized flavor gets a `docs/tools/<tool>.md` reference, a runnable example job, accepted parameter types/ranges/defaults, required block rules, and exact upstream mappings tied to a declared revision.

Official sources to consult when finalizing adapters:

- [YuE repository](https://github.com/multimodal-art-projection/YuE). This workstation selects YuE2 through Wan2GP's native Windows pipeline; see the implemented [YuE2 flavor](tools/yue.md).
- [ACE-Step repository](https://github.com/ace-step/ACE-Step) and [ACE-Step 1.5 inference API](https://ace-step.github.io/ACE-Step-1.5/en/INFERENCE). Choose a version before settling parameter mappings.
- [LeVo / SongGeneration repository](https://github.com/tencent-ailab/SongGeneration).
- [HeartMuLa heartlib repository](https://github.com/HeartMuLa/heartlib). Use `heartmula` as the canonical identifier for the requested Heart Moola tool.

## Runner configuration

For a runner named `ace-step.py`, look for exactly `ace-step.yaml`:

1. In the invocation's current working directory.
2. Beside the runner, under `<workspace>/bin/`, if the first file is absent.

Select the first existing file; do not merge the two files. An invalid/unreadable current-directory config fails immediately, rather than falling back. If neither exists, fail with both searched paths and instructions to create a config from its example template. Do not search the job directory or parent directories. Capture the invocation directory before launching the upstream tool, so child-process working directories cannot change lookup behavior.

Track portable templates as `bin/<runner>.example.yaml`. Concrete configs beside runners are ignored by Git; configs kept inside user work are local to that work. Configs must contain no secrets; document environment/credential-manager sources when authentication is needed.

Example proposed schema:

```yaml
version: 1
tool: ace-step
paths:
  application: ../apps/ace-step
  python: ../apps/ace-step/.venv/Scripts/python.exe
  entrypoint: ../apps/ace-step/adapter-entrypoint.py
  models:
    generation: ../models/music/ace-step/generation
    # Add other named model components only when the adapter requires them.
runtime:
  device: cuda
  precision: bf16
  timeout_seconds: 1800
defaults:
  seed: 42
  duration_seconds: 90
  steps: 50
  tool_options: {}
output:
  directory: ../work/music/generated
```

The entrypoint is a placeholder, not an existing upstream file. Runtime precision and generation defaults shown here also require validation against the chosen tool. An adapter may replace `python`/`entrypoint` with a documented `binary` path, or define a documented API connection schema. Model component names are flavor-specific.

Resolve relative application, interpreter/binary, entrypoint, model, and output paths against the selected config's directory. Resolve a relative CLI job path against the invocation directory and reference paths against the job's directory. Absolute paths remain absolute. Do not infer workspace locations from the invocation directory. Any native Windows/WSL path translation belongs to the tool adapter and must be explicit.

Effective generation settings use this precedence: documented adapter defaults → config `defaults` → job frontmatter. Overlay `tool_options` by individual key. Validate the resulting settings against the selected flavor and model. Config `paths`, `runtime`, and `output` are deployment settings and cannot be replaced by job tuning keys. Version/tool identity fields are validation metadata, not generation defaults. CLI overrides are limited to `--output-dir` for output location; its relative path resolves against the invocation directory. No arbitrary upstream argument passthrough in version 1.

## Execution and output

Translate validated inputs into a structured API request or an argument array passed without a shell. Launch Python tools with their configured interpreter and application working directory; pass lyric/style files via a unique run directory when upstream requires files. Do not build commands by concatenating prompt text. Runners require installed tools/models and must avoid interactive prompts or implicit downloads during generation.

Every invocation creates a unique output subdirectory under the configured output location (or `--output-dir`), labeled with a filename-safe title and unique run identifier. Never overwrite existing outputs. Preserve the original job, translated text/request, effective nonsecret settings, selected config path, available code/model revision identities, stdout/stderr logs, and generated audio. Record the resolved seed when upstream supports one; a fixed seed does not guarantee identical audio across hardware or software revisions.

Set a configured generation timeout, report tool exit failures clearly, and retain partial artifacts/logs. Generation is a new run on each invocation; retrying does not delete or reuse earlier output automatically. Model download resumability belongs to installation/model reconciliation; generation resume is supported only when a flavor explicitly documents it. Return zero only after expected audio exists and passes basic readability/nonempty checks. Validation and dry-run success also return zero. Other outcomes return a nonzero status with a concise error and log location when a run directory exists.
