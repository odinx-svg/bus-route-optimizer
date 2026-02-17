param(
    [Parameter(Position = 0)]
    [string]$Version
)

$ErrorActionPreference = "Stop"

function Invoke-GitChecked {
    param(
        [string]$Root,
        [string[]]$GitArgs,
        [switch]$AllowFailure
    )
    & git -C $Root @GitArgs
    $exit = $LASTEXITCODE
    if (-not $AllowFailure -and $exit -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $exit"
    }
    return $exit
}

try {
    $root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
    $versionFile = Join-Path $root "scripts\desktop\desktop_version.py"

    Write-Host ""
    Write-Host " =============================================="
    Write-Host "    TUTTI - One Click Desktop Release"
    Write-Host " =============================================="
    Write-Host ""

    if (-not (Test-Path $versionFile)) {
        throw "Version file not found: $versionFile"
    }

    if ([string]::IsNullOrWhiteSpace($Version)) {
        $Version = Read-Host "Enter release version (x.y.z)"
    }
    if ($null -eq $Version) { $Version = "" }
    $Version = $Version.Trim()
    if ($Version -notmatch "^\d+\.\d+\.\d+$") {
        throw "Invalid version format '$Version'. Use x.y.z"
    }

    Invoke-GitChecked -Root $root -GitArgs @("remote", "get-url", "origin") | Out-Null
    $branchOutput = & git -C $root rev-parse --abbrev-ref HEAD
    $branch = (($branchOutput | Out-String).Trim())
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
        throw "Could not resolve current git branch."
    }

    $tag = "v$Version"
    Write-Host " Target version: $Version"
    Write-Host " Target tag:     $tag"
    Write-Host " Branch:         $branch"
    Write-Host ""

    $localTagOutput = & git -C $root tag --list $tag
    $localTag = (($localTagOutput | Out-String).Trim())
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($localTag)) {
        throw "Tag $tag already exists locally."
    }

    $remoteTagOutput = & git -C $root ls-remote --tags origin "refs/tags/$tag"
    $remoteTag = (($remoteTagOutput | Out-String).Trim())
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($remoteTag)) {
        throw "Tag $tag already exists on origin."
    }

    Write-Host " [1/6] Updating scripts/desktop/desktop_version.py..."
    $content = Get-Content -Path $versionFile -Raw
    if ($content -notmatch 'APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
        throw "APP_VERSION not found in desktop_version.py"
    }
    $currentVersion = $Matches[1]
    if ($currentVersion -ne $Version) {
        $updated = [regex]::Replace(
            $content,
            'APP_VERSION\s*=\s*"[0-9]+\.[0-9]+\.[0-9]+"',
            "APP_VERSION = `"$Version`"",
            1
        )
        Set-Content -Path $versionFile -Value $updated -Encoding UTF8
    } else {
        Write-Host "        APP_VERSION already set to $Version"
    }

    Write-Host " [2/6] Staging changes..."
    Invoke-GitChecked -Root $root -GitArgs @("add", "-A") | Out-Null

    Write-Host " [3/6] Creating commit..."
    & git -C $root diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        Invoke-GitChecked -Root $root -GitArgs @("commit", "-m", "chore(desktop): release $tag") | Out-Null
    } else {
        Write-Host "        Nothing to commit. Continuing with tag."
    }

    Write-Host " [4/6] Creating tag..."
    Invoke-GitChecked -Root $root -GitArgs @("tag", "-a", $tag, "-m", "Tutti desktop release $tag") | Out-Null

    Write-Host " [5/6] Pushing branch..."
    Invoke-GitChecked -Root $root -GitArgs @("push", "origin", $branch) | Out-Null

    Write-Host " [6/6] Pushing tag..."
    Invoke-GitChecked -Root $root -GitArgs @("push", "origin", $tag) | Out-Null

    Write-Host ""
    Write-Host " DONE: Release pipeline started for $tag"
    Write-Host " Track build here:"
    Write-Host " https://github.com/odinx-svg/bus-route-optimizer/actions/workflows/desktop-release.yml"
    Write-Host ""
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
