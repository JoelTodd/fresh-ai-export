param(
  [switch] $SkipBuild,
  [switch] $SmokeTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-LaunchedFromExplorer {
  try {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
    if (!$process) { return $false }
    $parent = Get-Process -Id $process.ParentProcessId -ErrorAction SilentlyContinue
    return $parent -and $parent.ProcessName -eq "explorer"
  }
  catch {
    return $false
  }
}

function Pause-ForExplorer($Message = "Press Enter to close this window") {
  if (Test-LaunchedFromExplorer) {
    Write-Host ""
    Read-Host $Message | Out-Null
  }
}

trap {
  Write-Host ""
  Write-Host "Dev test failed."
  Write-Host $_
  Pause-ForExplorer
  exit 1
}

$Root = Split-Path -Parent $PSScriptRoot
$ExePath = Join-Path $Root "frontend\release\Freshdesk Local Exporter-0.1.0-portable.exe"

function Stop-FreshdeskExporter {
  Get-CimInstance Win32_Process |
    Where-Object {
      $_.Name -like "*Freshdesk Local Exporter*" -or
      ($_.CommandLine -and (
        $_.CommandLine -like "*Freshdesk Local Exporter-0.1.0-portable.exe*" -or
        $_.CommandLine -like "*FreshdeskLocalExporter*" -or
        $_.CommandLine -like "*backend_launcher.py*"
      ))
    } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if (!$SkipBuild) {
  & (Join-Path $PSScriptRoot "build.ps1")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (!(Test-Path $ExePath)) {
  throw "WebView2 app was not found at $ExePath. Run scripts\build.ps1 first."
}

Stop-FreshdeskExporter
Write-Host "Opening WebView2 app. Close the app window to return to PowerShell."
$process = $null
try {
  $process = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath) -PassThru
  if ($SmokeTest) {
    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
      $started = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
      if ($started -and $started.MainWindowHandle -ne 0) {
        Write-Host "WebView2 app opened."
        return
      }
      if (!$started) {
        throw "WebView2 app exited before opening a window."
      }
      Start-Sleep -Milliseconds 250
    }
    throw "Timed out waiting for the WebView2 app window."
  }
  Wait-Process -Id $process.Id
}
finally {
  if ($SmokeTest -and $null -ne $process -and !$process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  }
  Stop-FreshdeskExporter
}

Pause-ForExplorer
