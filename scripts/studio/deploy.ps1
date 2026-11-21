<#
    Builds one Mod Studio profile of the mod and installs it into the game folder.
    Replaces scripts/copy-files.bat.

      -Profile d2rl       the D2RLoader build -> mods\Reimagined (default)
      -Profile standard   the soft mod for plain D2R -> mods\ReimaginedSoft

    What it does:
      1. ModStudio.Cli build <repo> <profile>  (tables + strings from source/, assets from data/,
         plus the profile's rules and files under compatibility/<profile>/)
      2. Mirrors the built <Mod>.mpq into mods\<Mod>\<Mod>.mpq: copies new and changed files,
         removes files the build no longer has. Like copy-files.bat it leaves
         global\.DISABLE_DEBUG and the launcher's *_launcher_clean snapshots out of the
         mirror, then deletes the snapshots so the launcher re-snapshots fresh data.
      It never touches d2rloader\: plugins, memory patches, configs and logs there come from
      other projects, the launcher and the players.

    The archive is named after the deploy folder (-Mod), so the soft mod installs as
    mods\ReimaginedSoft\ReimaginedSoft.mpq; its profile also gives it its own savepath.

    For the standard profile it first runs string_budget.py on the built strings: plain D2R
    crashes once its strings' combined size passes a limit (Russian first). It stops when
    string_budget.json sets a limit and the build is over it (-SkipStringCheck goes ahead).

    Run:  powershell -ExecutionPolicy Bypass -File scripts\studio\deploy.ps1 [-Profile standard]
#>
param(
    [Alias('Profile')]
    [ValidateSet('d2rl', 'standard')]
    [string]$BuildProfile = 'd2rl',
    [string]$GameDir = 'C:\Program Files (x86)\Diablo II Resurrected',
    [string]$Mod = '',
    [string]$Cli = $env:MOD_STUDIO_CLI,
    [switch]$SkipBuild,
    [switch]$SkipStringCheck,
    [switch]$WhatIf
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Mod) { $Mod = if ($BuildProfile -eq 'standard') { 'ReimaginedSoft' } else { 'Reimagined' } }
if ($Mod -notmatch '^[A-Za-z0-9_-]{1,80}$') { throw "Invalid mod folder name: $Mod" }
$project = (Get-Content (Join-Path $repo 'mod-project.json') -Raw | ConvertFrom-Json).name

if (-not $SkipBuild) {
    if (-not $Cli) { $Cli = Join-Path $repo '..\d2r-mod-studio\src\ModStudio.Cli\bin\Release\net10.0\ModStudio.Cli.exe' }
    if (-not (Test-Path -LiteralPath $Cli)) { throw "Mod Studio CLI not found at $Cli. Build it (dotnet build src\ModStudio.Cli -c Release) or pass -Cli / set MOD_STUDIO_CLI." }
    Write-Host "Building profile '$BuildProfile' with $Cli"
    & $Cli build $repo $BuildProfile
    if ($LASTEXITCODE -ne 0) { throw "Mod Studio build failed ($LASTEXITCODE)." }
}
$build = Get-Content (Join-Path $repo '.studio\builds\current\build.json') -Raw | ConvertFrom-Json
if ($build.Profile -ne $BuildProfile) { throw "The current build is profile '$($build.Profile)', not '$BuildProfile'. Run without -SkipBuild." }
$output = $build.Output

if ($BuildProfile -eq 'standard' -and -not $SkipStringCheck) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { Write-Warning 'python not found: string size check skipped.' }
    else {
        & $python.Source (Join-Path $PSScriptRoot 'string_budget.py') --output (Join-Path $output "$project.mpq\data\local\lng\strings")
        if ($LASTEXITCODE -eq 1) { throw 'The build is over plain D2R''s string limit (see above). Pass -SkipStringCheck to deploy it anyway.' }
        if ($LASTEXITCODE -ne 0) { Write-Warning 'String size check could not run (see above).' }
    }
}

$dest = Join-Path $GameDir "mods\$Mod"
$archive = "$Mod.mpq"
function Test-Kept([string]$relative) {
    # Install files the mirror must neither overwrite nor delete.
    return ($relative -match '(^|/)[^/]*_launcher_clean(/|$)' -or $relative -match '_launcher_clean\.json$' -or
            $relative -ieq "$archive/data/global/.DISABLE_DEBUG")
}

$copied = 0; $same = 0; $removed = 0
$wanted = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
foreach ($file in $build.Files) {
    $source = Join-Path $output $file.Path
    $relative = $file.Path
    if (-not $relative.StartsWith("$project.mpq/", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected build output path: $($file.Path)"
    }
    $relative = $archive + $relative.Substring($project.Length + 4)
    if (Test-Kept $relative) { continue }
    [void]$wanted.Add($relative)
    $target = Join-Path $dest ($relative -replace '/', '\')
    if ((Test-Path -LiteralPath $target) -and (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ieq $file.Sha256) { $same++; continue }
    if ($WhatIf) { Write-Host "  would copy $relative"; $copied++; continue }
    New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Force
    Write-Host "  copied $relative"
    $copied++
}

# Mirror deletions inside the archive folder only.
$archiveDir = Join-Path $dest $archive
if (Test-Path -LiteralPath $archiveDir) {
    foreach ($existing in Get-ChildItem -LiteralPath $archiveDir -Recurse -File) {
        $relative = $archive + '/' + $existing.FullName.Substring($archiveDir.Length + 1).Replace('\', '/')
        if ((Test-Kept $relative) -or $wanted.Contains($relative)) { continue }
        if ($WhatIf) { Write-Host "  would remove $relative"; $removed++; continue }
        Remove-Item -LiteralPath $existing.FullName -Force
        Write-Host "  removed $relative"
        $removed++
    }
    if (-not $WhatIf) {
        Get-ChildItem -LiteralPath $archiveDir -Recurse -Directory | Sort-Object { $_.FullName.Length } -Descending |
            Where-Object { -not (Get-ChildItem -LiteralPath $_.FullName -Force) } | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
        # The launcher copies its <name>_launcher_clean snapshot back over the data on every launch;
        # a stale one silently reverts this deploy (see copy-files.bat history).
        $snapshots = @(Get-ChildItem -LiteralPath $archiveDir -Recurse -Directory -Filter '*_launcher_clean') +
                     @(Get-ChildItem -LiteralPath $archiveDir -Recurse -File -Filter '*_launcher_clean.json')
        foreach ($s in $snapshots) { Remove-Item -LiteralPath $s.FullName -Recurse -Force }
        if ($snapshots.Count) { Write-Host "Removed the launcher's clean-copy snapshots; it rebuilds them on the next launch." }
    }
}
Write-Host ("{0}: {1} copied, {2} unchanged, {3} removed -> {4}" -f $BuildProfile, $copied, $same, $removed, $dest)
if ($BuildProfile -eq 'standard') { Write-Host "Launch plain D2R with: -mod $Mod -txt" }
