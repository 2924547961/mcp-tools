[CmdletBinding()]
param(
  [ValidateSet('Install', 'Uninstall')]
  [string]$Mode = 'Install',
  [Parameter(Mandatory = $true)]
  [string]$ProjectRoot,
  [string]$InstallRoot = (Join-Path $env:USERPROFILE '.codex\tools\github-auto-sync')
)

$ErrorActionPreference = 'Stop'
$SourceRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$NodePath = (Get-Command node).Source
$CodexPath = (Get-Command codex).Source
$HooksPath = Join-Path $env:USERPROFILE '.codex\hooks.json'
$SkillTarget = Join-Path $env:USERPROFILE '.agents\skills\github-auto-sync'
$InstalledHookPath = Join-Path $InstallRoot 'dist\src\hook.js'

function Read-Hooks {
  if (Test-Path -LiteralPath $HooksPath) {
    return Get-Content -Raw -LiteralPath $HooksPath | ConvertFrom-Json -AsHashtable
  }
  return @{ description = 'User lifecycle hooks.'; hooks = @{} }
}

function Write-Hooks([hashtable]$Document) {
  $parent = Split-Path -Parent $HooksPath
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $Document | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $HooksPath -Encoding utf8NoBOM
}

function Add-Hook([hashtable]$Document, [string]$Event, [string]$ModeName, [string]$HookPath) {
  if (-not $Document.ContainsKey('hooks')) { $Document.hooks = @{} }
  if (-not $Document.hooks.ContainsKey($Event)) { $Document.hooks[$Event] = @() }
  $command = '"{0}" "{1}" {2}' -f $NodePath, $HookPath, $ModeName
  $nodeLiteral = "'" + $NodePath.Replace("'", "''") + "'"
  $hookLiteral = "'" + $HookPath.Replace("'", "''") + "'"
  $commandWindows = "& $nodeLiteral $hookLiteral $ModeName"
  $exists = @($Document.hooks[$Event]) | Where-Object {
    @($_.hooks) | Where-Object { $_.commandWindows -like "*$InstalledHookPath*" -or $_.command -like "*$InstalledHookPath*" }
  }
  if (-not $exists) {
    $Document.hooks[$Event] = @($Document.hooks[$Event]) + @{
      hooks = @(@{ type = 'command'; command = $command; commandWindows = $commandWindows; timeout = 600; statusMessage = "GitHub auto-sync: $Event" })
    }
  }
}

function Remove-ManagedHooks([hashtable]$Document) {
  if (-not $Document.ContainsKey('hooks')) { return }
  foreach ($event in @('UserPromptSubmit', 'Stop')) {
    if (-not $Document.hooks.ContainsKey($event)) { continue }
    $remaining = @()
    foreach ($group in @($Document.hooks[$event])) {
      $handlers = @($group.hooks) | Where-Object {
        -not (($_.commandWindows -like "*$InstalledHookPath*") -or ($_.command -like "*$InstalledHookPath*"))
      }
      if ($handlers.Count -gt 0) {
        $group.hooks = $handlers
        $remaining += $group
      }
    }
    if ($remaining.Count -gt 0) { $Document.hooks[$event] = $remaining }
    else { $Document.hooks.Remove($event) }
  }
}

if ($Mode -eq 'Uninstall') {
  $hooks = Read-Hooks
  Remove-ManagedHooks $hooks
  Write-Hooks $hooks
  $existingText = (& $CodexPath mcp get github-repository --json 2>$null | Out-String)
  if ($LASTEXITCODE -eq 0) {
    $existingConfig = $existingText | ConvertFrom-Json
    if (@($existingConfig.transport.args) -contains (Join-Path $InstallRoot 'dist\src\index.js')) {
      & $CodexPath mcp remove github-repository
    }
  }
  if (Test-Path -LiteralPath $SkillTarget) { Remove-Item -Recurse -Force -LiteralPath $SkillTarget }
  if (Test-Path -LiteralPath $InstallRoot) { Remove-Item -Recurse -Force -LiteralPath $InstallRoot }
  [pscustomobject]@{ status = 'success'; mode = 'uninstall'; hooks = $HooksPath; installRoot = $InstallRoot } | ConvertTo-Json
  exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot 'dist\src\index.js'))) {
  throw 'Build output is missing. Run npm run check before installation.'
}

New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
$DistTarget = Join-Path $InstallRoot 'dist'
if (Test-Path -LiteralPath $DistTarget) { Remove-Item -Recurse -Force -LiteralPath $DistTarget }
Copy-Item -Recurse -Force -LiteralPath (Join-Path $SourceRoot 'dist') -Destination $DistTarget
Copy-Item -Force -LiteralPath (Join-Path $SourceRoot 'package.json') -Destination $InstallRoot
Copy-Item -Force -LiteralPath (Join-Path $SourceRoot 'package-lock.json') -Destination $InstallRoot
$ScriptsTarget = Join-Path $InstallRoot 'scripts'
New-Item -ItemType Directory -Force -Path $ScriptsTarget | Out-Null
Copy-Item -Force -LiteralPath $PSCommandPath -Destination (Join-Path $ScriptsTarget 'install.ps1')
& npm ci --omit=dev --prefix $InstallRoot
if ($LASTEXITCODE -ne 0) { throw 'Production dependency installation failed.' }

New-Item -ItemType Directory -Force -Path $SkillTarget | Out-Null
Copy-Item -Force -LiteralPath (Join-Path (Split-Path -Parent $SourceRoot) '.agents\skills\github-auto-sync\SKILL.md') -Destination $SkillTarget

$HookPath = $InstalledHookPath
$hooks = Read-Hooks
Remove-ManagedHooks $hooks
Add-Hook $hooks 'UserPromptSubmit' 'prompt' $HookPath
Add-Hook $hooks 'Stop' 'stop' $HookPath
Write-Hooks $hooks

$existingText = (& $CodexPath mcp get github-repository --json 2>$null | Out-String)
if ($LASTEXITCODE -eq 0) {
  $existingConfig = $existingText | ConvertFrom-Json
  $expectedEntry = Join-Path $InstallRoot 'dist\src\index.js'
  if (@($existingConfig.transport.args) -notcontains $expectedEntry) { throw 'An unrelated MCP server named github-repository already exists; refusing to overwrite it.' }
} else {
  & $CodexPath mcp add github-repository --env "GITHUB_MCP_ALLOWED_ROOTS=$ProjectRoot" -- $NodePath (Join-Path $InstallRoot 'dist\src\index.js')
  if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed.' }
}

& $NodePath (Join-Path $InstallRoot 'dist\src\cli.js') setup --path $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw 'Repository auto-sync setup failed.' }

[pscustomobject]@{
  status = 'success'
  mode = 'install'
  installRoot = $InstallRoot
  skill = Join-Path $SkillTarget 'SKILL.md'
  hooks = $HooksPath
  mcp = 'github-repository'
  allowedRoot = $ProjectRoot
  trustRequired = $true
} | ConvertTo-Json
