# Optional manual installations

These tools are available for individual use but are outside the managed workstation bootstrap. They are not installed, updated, or checked by `just bootstrap`, `just status`, or `just doctor`. Install them manually only when their interface or workflow is useful.

| Tool | Purpose | Why optional |
| --- | --- | --- |
| [WavePrompt](https://www.discodsp.com/waveprompt/) | Desktop music generation with loops, vocal phrases, songs, a piano roll, and a render library. | Uses YuE2, already supported by the workstation's existing YuE integration. Its desktop workflow does not warrant another managed backend. |

## WavePrompt

Decision: skip managed integration; keep it as an optional manual installation. See the [official download and requirements](https://www.discodsp.com/waveprompt/) and [version history](https://www.discodsp.net/news/waveprompt.html). Review the vendor's current software/model licensing terms before use.

### Manual setup

1. Download the Windows installer from the official site and check that its digital signature identifies DiscoDSP LLC.
2. Run the installer manually, granting administrator access if requested. For a workspace installation, choose `<workspace>/apps/waveprompt` as the application destination.
3. Complete the vendor's GPU-runtime and model setup. Allow substantial disk space: the tested application/runtime used about 6 GiB and the required models about 8.85 GiB, with additional space needed for installer downloads and generated audio.
4. Use the app's File menu to select `<workspace>/models/music/waveprompt` for models and `<workspace>/work/music/waveprompt` for generated work. Preserve any existing folders; use the app's migration controls when changing locations.
5. Launch from the Windows Start menu or `WavePrompt.exe`, render a short loop, and check playback/export. Manage updates through the vendor's application/installer.

WavePrompt's model packaging differs from the Wan2GP YuE2 backend used by this repository. Do not substitute the existing Wan2GP weights by renaming them or linking them into WavePrompt's model slots.

### Local trial record

WavePrompt **1.2.3** was installed and tested on **2026-10-20** with an RTX 5070 Ti (16 GB). Its bundled Python 3.12.15 engine and PyTorch 2.10/CUDA 12.8 produced a non-silent, two-second instrumental loop at 120 BPM, stereo 48 kHz PCM 24-bit, in approximately 85 seconds offline. The GUI reached `Ready (CUDA:0)`. Full-song quality and lyric fidelity were not assessed.

The existing local application, model files, settings, installer cache, and generated work have been retained. Application/model/output locations follow the workspace-relative paths above; settings and the GUI engine log live under the user's Documents `discoDSP/WavePrompt` folder, possibly redirected through OneDrive. Removing managed integration does not uninstall the app or delete its data.

There are no repository `just` commands or automatic reconstruction steps for WavePrompt. The local trial's request, vendor recipe, audio, and generation log remain under `work/music/waveprompt/` for reference.
