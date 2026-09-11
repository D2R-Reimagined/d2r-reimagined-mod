# Reimagined Mod Studio — proposed editor plan

Status: design proposal, not an implemented editor. Cross-platform editing on Windows, Linux and macOS is a first-release requirement. Runtime launch and specialist-tool availability are platform-specific capabilities.

## Recommended technology

Use C#/.NET for the platform-independent document, schema, validation, indexing, calculation and build services. Use Avalonia for the desktop shell. Keep this a separate editor application/repository, consuming a versioned project format; do not turn the mod repository or launcher into the editor application.

The current launcher already uses Avalonia and AvaloniaEdit; the level editor separates C# Core/Assets libraries from its Windows-only WPF application. Reuse suitable services and codecs after checking their dependencies. The WPF viewport is not portable merely because the shell is Avalonia.

Candidate components: AvaloniaEdit for raw text and Dock for movable/split panels. The editable grid requires an early prototype and an explicit dependency decision. Avalonia's original TreeDataGrid is MIT-licensed, but ongoing upstream development is in the commercial Accelerate fork. Do not assume every Avalonia component has the framework's license. Evaluate a maintained open-source grid/fork or the commercial component under its actual redistribution/contributor terms. Avoid designing the entire application around an unproven grid.

Rust is an optional future implementation detail for a measured hot spot, not the default core language. Tauri would add a web UI and an IPC boundary; it would not remove the need for grid virtualization, indexing, incremental validation, or careful document ownership. A web frontend remains an alternative if the Avalonia grid prototype fails; keep the core API independent of either shell.

Current real workloads: 56 table documents containing 47,832 source rows; eight catalogs containing 10,686 translation records; sounds approximately 14.43 MiB and cubemain 8.78 MiB. Skills has 322 columns. These are benchmark inputs, not evidence of .NET performance. Test larger synthetic projects too.

## Workspace and editing experience

- Top: project and branch, runtime configuration, Build/Deploy actions, prominent Play and Stop. Target labels say Standard D2R or D2RLoader, not “vanilla data”; unmodified vanilla content is a separate baseline.
- Left: project tree with a logical Tables/Strings/Assets/Profiles view and a physical Files view. A logical “Unique items” entry represents records.json plus its schema; physical paths remain inspectable. Changes, diagnostics and external modifications decorate entries.
- Center: tabbed and splittable documents. Table mode opens record arrays and recognized TSV files. Source mode shows the backing JSON/TXT. Column presets, pinned identity columns, reference completion, filtering, range selection, paste/fill and undo are core operations. Sorting is a view operation, never a rewrite of runtime row slots.
- Right: persistent selected-record inspector with quick hover previews and a pin action. Context-sensitive tabs expose item previews, calculated results, references and overrides. Keyboard selection exposes the same information as hover.
- Bottom: Problems, Build, Game Output and Changes. Problems identify profile, source document, record, field and rule, and navigate to the corresponding cell. Display running/stale/canceled checks explicitly; do not silently leave a green status from an older edit.

One document session owns the buffer, dirty state, version, undo stack, diagnostics and disk fingerprint. Table and source views edit that same session. Invalid raw text stays recoverable; table edits are paused until it parses. Switching views must not discard unfinished text or replace it with an older model. External modifications trigger reload or three-way reconciliation; a dirty document is never silently overwritten.

Undo stores commands/cell deltas, not complete project snapshots per keystroke. Bulk paste is one undoable transaction. Autosave recovery is local and separate from authored source. Saving uses deterministic serialization and replacement files, preserves unknown supported fields, and detects disk changes since opening.

## Project, source, assets and deployment

Use a versioned shared manifest such as mod-project.json for the mod identity, source layout, schema/compiler versions, runtime profiles and relative asset roots. Keep personal source checkout paths, extracted-game paths, executable locations, tool paths, deployment paths and UI layout in local user settings. Never commit credentials or machine-specific paths.

Distinguish four locations:

1. Source checkout: authored JSON, native assets and compatibility overrides.
2. Read-only game asset roots: user-provided base assets for resolution and previews.
3. Build cache/staging: generated outputs and indexes, never authoritative source.
4. Deployment target: the selected mod installation, separate from source and cache.

Resolve assets and references against the project's selected game version and runtime profile. Show whether a value came from shared source, a profile override or a baseline resource. Missing inputs produce unresolved results, not copied vanilla constants or zero values. Do not bundle game assets with the community editor.

JSON is the collaboration-oriented authoring format. Native TXT projects remain supported through a format adapter and explicit conversion/import operations. Recognize files by schema, path and content as well as extension: a level preset JSON is not a table merely because it ends in .json. Generated TXT can be inspected read-only and traced back to its source cell. Do not convert binary assets to JSON simply for uniformity.

## Play pipeline

Play runs Save/validate snapshot → Build selected profile → Stage deployment → Commit deployment → Launch selected configuration. Its result names the exact snapshot/build and target used. A build is not a successful launch; a started process is not proof the game loaded the mod.

Save policy is explicit and persistent. If autosave-before-play is disabled and documents are dirty, show a save decision rather than launching silently stale data. Freeze one immutable input snapshot for the build. If edits happen while it runs, finish or cancel that snapshot consistently; do not mix source versions. The UI indicates when the running game uses an older revision.

Build failures and blocking diagnostics stop deployment. Deployment uses an ownership manifest, removes only obsolete owned outputs, preserves settings/saves and unrelated files, handles locked files, and supports rollback. Reject source/deployment overlap and resolve symlinks before writing. Stage on the target volume where possible; use a journal and recovery for multi-file updates rather than promising a fully atomic directory deployment on every platform.

Repeated Play clicks do not race deployments or launch duplicate processes. Cancellation before deployment leaves the installed copy untouched; cancellation during replacement completes recovery before returning. Stop targets the child process/session launched by this editor. Runtime adapters discover and validate supported executables and arguments; Windows, Wine/Proton and other launch environments are separate adapters with tested support declarations.

## Validation and calculations

Run fast syntax/cell checks after edits, affected-table/reference checks in the background, and comprehensive profile validation on Build. Every job is cancelable and tagged with a document/project revision; discard stale results. Maintain a dependency graph so changing one monster or item invalidates relevant previews, not every table after every keystroke.

The existing migration schemas provide lossless serialization and structural guards. Most newly migrated tables deliberately lack runtime identity rules. Add versioned semantic schemas incrementally: field descriptions, numeric ranges, enumerations, references, composite identities, expression fields, dependencies and runtime availability. A structural build must not be presented as complete D2R lint coverage.

The bundled d2rlint.exe can be an optional Windows adapter. Cross-platform core checks must run in the editor's portable engine; release-one Linux/macOS validation cannot depend on a Windows executable. Port or reimplement useful rules with fixtures and retain explicit unsupported-rule reporting.

For superunique health and experience, resolve Class to monster data and all required level/difficulty/player/runtime context. Show ranges, assumptions, missing dependencies and the contributing fields. Experience may require player-level/party context depending on the quantity being displayed; label base monster experience separately from experience actually awarded. Reuse the existing health calculator's logic and tests as reference material after checking data assumptions, rather than assuming its exported website dataset is current editor data.

For unique-item previews, combine base item, properties, strings, selected locale and runtime rules. Show min/max or a selected deterministic roll. Conditional/unknown properties produce explicit incomplete-preview diagnostics. Never invent a plausible-looking complete tooltip when a modifier is unresolved. Initially aim for faithful data and ordering; pixel-identical game rendering is a separate milestone.

## File-type integration

Maintain a handler registry that declares recognition, preview, edit, lint, build and platform capabilities by format/version. “All files handled” means an appropriate, non-destructive route exists; it does not imply every format is natively editable on day one.

- Consolidated table JSON and TSV: native table/source editor.
- Translation catalogs: locale matrix, formatting checks and preview.
- General JSON/text: source editor with matching schemas where available.
- DS1 (the level format, rather than D1S) and associated HD preset JSON: confirm before opening the configured level editor. Pass source paths, paired files and asset roots. Watch the complete save set, detect changes and refresh affected documents without discarding dirty buffers.
- Textures, sprites, tiles and models: read-only preview first, codec-specific editing/import later. Treat file versions and dependencies explicitly.
- Unknown or unsupported binary formats: metadata/hex preview or Open With; no guessed serialization.

The existing WPF level editor is Windows-only. Cross-platform table/text editing can ship first, while Linux/macOS specialist-file workflows clearly report unavailable tools and offer preview/Open With. Providing the same integrated level-authoring experience on every platform requires porting that UI/renderer or choosing a separately supported external tool; it is a distinct project milestone.

Start with built-in handlers and external-process tools. Define stable handler interfaces now, but defer arbitrary third-party in-process plugins and a plugin marketplace. External tool execution requires the configured confirmation policy; opening an unfamiliar project must not automatically execute repository scripts or plugins.

## Architecture and migration from the current compiler

Suggested boundaries:

- Editor.App: Avalonia shell, commands, docking, grid and text views.
- Editor.Workspace: project configuration, documents, undo, filesystem changes, Git and recovery.
- D2R.Data: table/catalog models, lossless readers/writers, versioned schemas and reference indexes.
- D2R.Analysis: diagnostics, dependency graph, calculations and preview models.
- D2R.Build: deterministic profile compiler, manifests and validation CLI.
- D2R.Runtime: staged deployment and platform-specific launch adapters.
- D2R.Tools: external tools and format handler capabilities.

These are dependency boundaries, not a requirement for separate processes or dozens of packages immediately. Keep pure domain logic callable from tests and a headless CLI. UI controls never own game formulas or deployment decisions.

Initially run the existing tested Node compiler through a build adapter, using a pinned/bundled runtime rather than requiring community users to install Node manually. Do not duplicate its behavior hastily. Move compilation into shared .NET libraries once golden-output parity covers every current table, catalog and override/failure case; then the UI and CLI use that one implementation. Keep differential checks during the transition.

Use Git for commits and branches. Add record/field-aware diffs and three-way merges inside the editor: independent cells can reconcile; competing cell edits require a choice; deletion-versus-edit and simultaneous ID allocation are explicit conflicts. Keep stable runtime identities and never silently renumber records to make a merge pass. Optional SQLite indexes are disposable caches outside Git, not the canonical source.

## Performance and first milestone

Load table data on demand, perform parsing/indexing off the UI thread, virtualize both rows and columns, and avoid one control or observable object per cell. Cache only useful projections. Avoid retaining simultaneous raw strings, several DOMs, grids and whole-document undo snapshots. Consider streaming parsing and paged backing only when measurements justify them.

The first implementation milestone is a cross-platform shell/grid prototype with real sounds, cubemain and skills data, not the full editor. Test Windows, Linux and macOS; include wide tables, Unicode/IME, keyboard-only editing, clipboard ranges, invalid text, external changes, cancellation and file-write recovery. Define baseline hardware and measure cold open, time to first usable rows, scrolling, paste/undo, validation delay, memory and save diff size. Provisional targets such as responsive input under 100 ms are goals, not measured guarantees.

Then deliver in order:

1. Real table/source documents, schemas, undo, save, recovery and existing compiler integration.
2. Source/deployment configuration, full build diagnostics and reliable Standard/D2RL Play on tested platforms.
3. Semantic references and linting, profile editing, changes/diffs and cell-level conflict resolution.
4. Item and monster inspectors with provenance and invalidation tests.
5. Specialist-format previews, confirmed external tools, then portable integrated level editing and additional native format editors.

The first usable release should cover the complete open → edit → diagnose → build → deploy → play path where launch is supported, while remaining useful for editing/building on every supported desktop OS.

## Technical references checked

- [Microsoft: Utf8JsonReader and streaming](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/use-utf8jsonreader)
- [Avalonia: control performance and virtualization](https://docs.avaloniaui.net/troubleshooting/app-performance-issues)
- [Avalonia: framework and TreeDataGrid licensing/development distinction](https://avaloniaui.net/blog/building-a-sustainable-future-for-avalonia)
- [AvaloniaEdit](https://github.com/AvaloniaUI/AvaloniaEdit)
- [Dock](https://github.com/wieslawsoltes/Dock/)
- [Tauri architecture](https://v2.tauri.app/concept/architecture/)

Local references: reimagined-launcher/ReimaginedLauncher/ReimaginedLauncher.csproj; d2r-level-editor/README.md and src/D2RLevel.App/D2RLevel.App.csproj; d2r-reimagined-mod/docs/source-workflow.md; d2r-reimagined-website/src/lib/health-calculator.ts and its tests. Existing-tool availability is source inspection, not new runtime verification.
