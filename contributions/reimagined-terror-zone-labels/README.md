# Reimagined Terror Zone Labels

Shows localized act names on the automap during Reimagined's whole-act Terror Zone rotations. Inside the active rotation, the act name replaces the terror level line. Outside it, an act name replaces the list of areas covered by that rotation. Partial rotations keep their area names. The labels use the active rotation, so Moo Moo Farm shows **Act 4** when it is terrorized with Act 4.

## Build

Use Visual Studio 2022 Build Tools with the C++ x64 workload and CMake 3.29 or newer. Build from this directory.

```powershell
git clone --branch v0.3.0 --single-branch https://github.com/D2RLoader/PluginSDK.git deps/PluginSDK
git -C deps/PluginSDK rev-parse HEAD
cmake -S . -B builds/release -G "Visual Studio 17 2022" -A x64
cmake --build builds/release --config Release
```

The SDK checkout should resolve to `bb0b48e080c51c37fc8296ee415d9daaba7ee33d`. The build produces `builds/release/Release/d2rl-reimagined-terror-zone-labels.dll`. It uses Localization v2 and the Gameplay Lifecycle service.

## Install

Place the DLL in `mods/Reimagined/d2rloader/plugins/` for Reimagined Mod + Loader. The runtime package consists of this DLL. The reported checks used upstream Reimagined 3.1.1 R27 and public D2RLoader 1.3.1-beta.

The level sets in `src/rotations.h` come from Reimagined's scheduled and manual rotations at commit `259768f269baefd01758a8961d785ae10d98879d`. Review those sets when upstream changes rotation membership. [Rotation source](https://github.com/D2R-Reimagined/d2r-reimagined-mod/blob/259768f269baefd01758a8961d785ae10d98879d/data/hd/global/excel/desecratedzones.json)

## Review artifact

The DLL under `tested/` is the exact 0.1.1 binary used for the attended checks.
Its SHA-256 is `c9be307fe71652891ab96f0019e94a45432a176bd84f031e1fa76484a3b98751`.
This contribution directory is for code review. Release packaging is handled
by the separate native plugin project described in the Mod Studio build guide.
