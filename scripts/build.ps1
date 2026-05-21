param(
  [switch] $CleanRuntime,
  [switch] $SkipFrontendBuild,
  [switch] $SkipNpmInstall,
  [ValidateSet("Fast", "Small")]
  [string] $Compression = "Fast"
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
  Write-Host "Build failed."
  Write-Host $_
  Pause-ForExplorer
  exit 1
}

# Builds a Windows-only portable executable that uses the installed Microsoft
# Edge WebView2 runtime instead of bundling a browser runtime.
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Runtime = Join-Path $Backend "runtime-fast"
$RuntimePythonDir = Join-Path $Runtime "python"
$RuntimePython = Join-Path $RuntimePythonDir "python.exe"
$RuntimeSitePackages = Join-Path $RuntimePythonDir "Lib\site-packages"
$RuntimeMarker = Join-Path $Runtime ".runtime-spec"
$Release = Join-Path $Frontend "release"
$Stage = Join-Path $Release "single-exe-stage"
$AppStage = Join-Path $Stage "app"
$PayloadZip = Join-Path $Stage "app.zip"
$PythonPayloadZip = Join-Path $Stage "python-runtime.zip"
$LauncherSource = Join-Path $PSScriptRoot "WebViewPortableLauncher.cs"
$PortableExe = Join-Path $Release "Freshdesk Local Exporter-0.1.0-portable.exe"
$SevenZip = Join-Path $Frontend "node_modules\7zip-bin\win\x64\7za.exe"
$WebViewSdk = Join-Path $Stage "webview2-sdk"
$WebViewNupkg = Join-Path $Stage "Microsoft.Web.WebView2.nupkg"
$WebViewZip = Join-Path $Stage "Microsoft.Web.WebView2.zip"
$WebViewCore = Join-Path $WebViewSdk "lib\net462\Microsoft.Web.WebView2.Core.dll"
$WebViewWinForms = Join-Path $WebViewSdk "lib\net462\Microsoft.Web.WebView2.WinForms.dll"
$WebViewLoader = Join-Path $WebViewSdk "runtimes\win-x64\native\WebView2Loader.dll"

function Remove-GeneratedDirectory($Path) {
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
  $resolvedPath = [System.IO.Path]::GetFullPath($Path)
  if (!$resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove generated directory outside workspace: $resolvedPath"
  }
  if (Test-Path $resolvedPath) {
    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
  }
}

function Clear-ReleaseGeneratedContent {
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
  $resolvedRelease = [System.IO.Path]::GetFullPath($Release)
  if (!$resolvedRelease.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean release directory outside workspace: $resolvedRelease"
  }
  New-Item -ItemType Directory -Force -Path $resolvedRelease | Out-Null
  Get-ChildItem -LiteralPath $resolvedRelease -Force |
    Where-Object { $_.Name -ne "exports" } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

$TotalStopwatch = [System.Diagnostics.Stopwatch]::StartNew()

Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -like "*Freshdesk Local Exporter*" -or
    $_.CommandLine -like "*FreshdeskLocalExporter*" -or
    ($_.Name -like "python*.exe" -and $_.CommandLine -like "*backend_launcher.py*")
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Clear-ReleaseGeneratedContent
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Write-Host "Preparing portable Python runtime..."
Push-Location $Backend
try {
  $EmbedVersion = "3.12.10"
  $RuntimeSpec = @(
    "python=$EmbedVersion"
    "fastapi"
    "httpx"
    "pydantic"
    "python-dotenv"
    "uvicorn[standard]"
  ) -join "`n"
  $CanReuseRuntime =
    !$CleanRuntime -and
    (Test-Path $RuntimePython) -and
    (Test-Path $RuntimeMarker) -and
    ((Get-Content -Path $RuntimeMarker -Raw).Trim() -eq $RuntimeSpec.Trim())

  if ($CanReuseRuntime) {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $RuntimePython -c "import encodings, uvicorn, fastapi, pydantic; assert hasattr(uvicorn, 'run')" 2>$null
    $ErrorActionPreference = $previousErrorActionPreference
    $CanReuseRuntime = $LASTEXITCODE -eq 0
  }

  if ($CanReuseRuntime) {
    Write-Host "Reusing existing portable Python runtime."
  }
  else {
    Remove-GeneratedDirectory $Runtime
    New-Item -ItemType Directory -Force -Path $RuntimePythonDir | Out-Null
    $EmbedZip = Join-Path $Runtime ("python-$EmbedVersion-embed-amd64.zip")
    $EmbedUrl = "https://www.python.org/ftp/python/$EmbedVersion/python-$EmbedVersion-embed-amd64.zip"
    Invoke-WebRequest -Uri $EmbedUrl -OutFile $EmbedZip
    Expand-Archive -Path $EmbedZip -DestinationPath $RuntimePythonDir -Force
    Remove-Item -LiteralPath $EmbedZip -Force

    $PthFile = Get-ChildItem -Path $RuntimePythonDir -Filter "python*._pth" | Select-Object -First 1
    if (!$PthFile) {
      throw "Embedded Python ._pth file was not found."
    }
    $PthContent = Get-Content -Path $PthFile.FullName
    if ($PthContent -notcontains "Lib\site-packages") {
      $PthContent += "Lib\site-packages"
    }
    $PthContent = $PthContent | Where-Object { $_ -ne "#import site" }
    if ($PthContent -notcontains "import site") {
      $PthContent += "import site"
    }
    Set-Content -Path $PthFile.FullName -Value $PthContent -Encoding ASCII

    New-Item -ItemType Directory -Force -Path $RuntimeSitePackages | Out-Null
    & python -m pip install `
      --target $RuntimeSitePackages `
      --platform win_amd64 `
      --python-version 3.12 `
      --implementation cp `
      --abi cp312 `
      --only-binary=:all: `
      fastapi httpx pydantic python-dotenv "uvicorn[standard]"
    if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed" }

    & $RuntimePython -c "import encodings, uvicorn, fastapi, pydantic; assert hasattr(uvicorn, 'run'); print('embedded python ok')"
    if ($LASTEXITCODE -ne 0) { throw "Embedded Python runtime verification failed" }
    Set-Content -Path $RuntimeMarker -Value $RuntimeSpec -Encoding ASCII
  }
}
finally {
  Pop-Location
}

if ($SkipFrontendBuild) {
  $FrontendDist = Join-Path $Frontend "dist"
  if (!(Test-Path $FrontendDist)) {
    throw "Cannot skip the frontend build because frontend\dist does not exist. Run scripts\build.ps1 without -SkipFrontendBuild first."
  }
  Write-Host "Skipping frontend build."
}
else {
  Write-Host "Building frontend..."
  Push-Location $Frontend
  try {
    $NodeModules = Join-Path $Frontend "node_modules"
    $NodeModulesLock = Join-Path $NodeModules ".package-lock.json"
    $PackageLock = Join-Path $Frontend "package-lock.json"
    $ShouldInstall =
      !$SkipNpmInstall -and
      (!(Test-Path $NodeModules) -or
        !(Test-Path $NodeModulesLock) -or
        !(Test-Path $SevenZip) -or
        ((Test-Path $PackageLock) -and ((Get-Item $PackageLock).LastWriteTimeUtc -gt (Get-Item $NodeModulesLock).LastWriteTimeUtc)))

    if ($ShouldInstall) {
      npm install
      if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    else {
      Write-Host "Reusing existing node_modules."
    }

    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
  }
  finally {
    Pop-Location
  }
}

Write-Host "Assembling WebView app payload..."
if (!(Test-Path $SevenZip)) {
  throw "7-Zip was not found at $SevenZip. Run npm install in the frontend folder."
}
if (!(Test-Path $LauncherSource)) {
  throw "WebView launcher source was not found at $LauncherSource."
}

Write-Host "Preparing WebView2 host SDK..."
Invoke-WebRequest -Uri "https://www.nuget.org/api/v2/package/Microsoft.Web.WebView2" -OutFile $WebViewNupkg
Copy-Item -LiteralPath $WebViewNupkg -Destination $WebViewZip -Force
Expand-Archive -Path $WebViewZip -DestinationPath $WebViewSdk -Force
if (!(Test-Path $WebViewCore) -or !(Test-Path $WebViewWinForms) -or !(Test-Path $WebViewLoader)) {
  throw "Required WebView2 SDK files were not found in the NuGet package."
}

New-Item -ItemType Directory -Force -Path (Join-Path $AppStage "resources\app") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $AppStage "resources\backend") | Out-Null
Copy-Item -LiteralPath (Join-Path $Frontend "dist") -Destination (Join-Path $AppStage "resources\app\dist") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Backend "app") -Destination (Join-Path $AppStage "resources\backend\app") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Backend "backend_launcher.py") -Destination (Join-Path $AppStage "resources\backend\backend_launcher.py") -Force

if (Test-Path $PayloadZip) {
  Remove-Item -LiteralPath $PayloadZip -Force
}
if (Test-Path $PythonPayloadZip) {
  Remove-Item -LiteralPath $PythonPayloadZip -Force
}

$AppCompressionLevel = if ($Compression -eq "Small") { "9" } else { "1" }
$PythonCompressionLevel = if ($Compression -eq "Small") { "9" } else { "1" }

Push-Location $AppStage
try {
  & $SevenZip a -tzip "-mx=$AppCompressionLevel" -mmt=on $PayloadZip ".\*"
  if ($LASTEXITCODE -ne 0) { throw "7-Zip app payload compression failed" }
}
finally {
  Pop-Location
}

Push-Location $RuntimePythonDir
try {
  & $SevenZip a -tzip "-mx=$PythonCompressionLevel" -mmt=on $PythonPayloadZip ".\*"
  if ($LASTEXITCODE -ne 0) { throw "7-Zip Python runtime compression failed" }
}
finally {
  Pop-Location
}

Write-Host "Creating WebView2 portable executable..."
$Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$FrameworkDir = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319"
if (!(Test-Path $Csc)) {
  $FrameworkDir = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319"
  $Csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (!(Test-Path $Csc)) {
  throw "C# compiler was not found. Expected csc.exe in the Windows .NET Framework folder."
}
$CompressionRef = Join-Path $FrameworkDir "System.IO.Compression.dll"
$CompressionFsRef = Join-Path $FrameworkDir "System.IO.Compression.FileSystem.dll"

& $Csc `
  /nologo `
  /target:winexe `
  /optimize+ `
  "/out:$PortableExe" `
  "/resource:$PayloadZip,FreshdeskLocalExporter.Payload.app.zip" `
  "/resource:$PythonPayloadZip,FreshdeskLocalExporter.Payload.python-runtime.zip" `
  "/resource:$WebViewCore,FreshdeskLocalExporter.WebView2.Core.dll" `
  "/resource:$WebViewWinForms,FreshdeskLocalExporter.WebView2.WinForms.dll" `
  "/resource:$WebViewLoader,FreshdeskLocalExporter.WebView2.Loader.dll" `
  "/reference:$CompressionRef" `
  "/reference:$CompressionFsRef" `
  "/reference:System.Windows.Forms.dll" `
  "/reference:System.Drawing.dll" `
  "/reference:$WebViewCore" `
  "/reference:$WebViewWinForms" `
  $LauncherSource
if ($LASTEXITCODE -ne 0) { throw "WebView launcher compilation failed" }

Write-Host ""
Write-Host "Done. WebView2 Windows executable:"
Write-Host $PortableExe
Write-Host ("Total build time: {0:n1}s" -f $TotalStopwatch.Elapsed.TotalSeconds)
Pause-ForExplorer
