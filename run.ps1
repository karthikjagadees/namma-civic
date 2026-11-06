$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$backendPort = 8000
$frontendPort = 5173
$aiMode = if ($env:NAMMA_CIVIC_AI_MODE) { $env:NAMMA_CIVIC_AI_MODE.Trim().ToLowerInvariant() } else { 'mock' }
if ($aiMode -notin @('mock', 'groq', 'openai', 'gemini')) {
  throw 'NAMMA_CIVIC_AI_MODE must be mock, groq, openai, or gemini.'
}

function Test-HttpEndpoint([int]$Port) {
  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $connection = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    if (-not $connection.AsyncWaitHandle.WaitOne(2000)) { return $false }
    $client.EndConnect($connection)

    $stream = $client.GetStream()
    $stream.ReadTimeout = 2000
    $request = [System.Text.Encoding]::ASCII.GetBytes("GET / HTTP/1.1`r`nHost: localhost`r`nConnection: close`r`n`r`n")
    $stream.Write($request, 0, $request.Length)
    $reader = [System.IO.StreamReader]::new($stream)
    $statusLine = $reader.ReadLine()
    return $statusLine -match '^HTTP/\d(?:\.\d)? \d{3}'
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Test-PortInUse([int]$Port) {
  return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$frontendVite = Join-Path $frontendPath 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $frontendVite)) {
  throw 'Frontend dependencies are missing. From the frontend folder, run: npm ci'
}

$pythonCandidates = @(
  (Join-Path $backendPath '.venv\Scripts\python.exe'),
  (Join-Path $projectRoot '.venv\Scripts\python.exe'),
  (Join-Path $env:TEMP 'civicfix-phase0-venv\Scripts\python.exe')
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonPath) {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCommand) { $pythonPath = $pythonCommand.Source }
}
if (-not $pythonPath) { throw 'Python was not found. Install Python or create backend\.venv first.' }

$backendReady = Test-HttpEndpoint $backendPort
$frontendReady = Test-HttpEndpoint $frontendPort

if ($aiMode -ne 'mock' -and (Test-PortInUse $backendPort)) {
  throw "Port 8000 already has a backend. Stop the current app with Ctrl+C before starting live AI mode '$aiMode'."
}

if (-not $backendReady -and (Test-PortInUse $backendPort)) {
  Write-Warning 'Port 8000 already has a listener. Reusing it and skipping a second backend; this should be the Namma Civic API.'
  $backendReady = $true
}
if (-not $frontendReady -and (Test-PortInUse $frontendPort)) {
  Write-Warning 'Port 5173 already has a listener. Reusing it and skipping a second frontend; this should be the Namma Civic web app.'
  $frontendReady = $true
}

$runDirectory = Join-Path $env:TEMP 'namma-civic-live-demo'
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

# These settings keep the local demo deterministic, offline, and isolated from project data.
$env:NAMMA_CIVIC_BACKEND_ROOT = $backendPath
$env:NAMMA_CIVIC_RUN_DIR = $runDirectory
$env:NAMMA_CIVIC_PYTHON = $pythonPath
$env:PYTHONPATH = $backendPath
$env:DATABASE_URL = 'sqlite+aiosqlite:///./namma-civic-demo.db'
$env:DATABASE_MODE = 'sqlite'
$env:APP_ENV = 'development'
$env:DEBUG = 'false'
$env:AI_MODE = $aiMode
$env:AI_PROVIDER = $aiMode
$env:MCP_MODE = 'mock'
$env:SMS_PROVIDER = 'mock'
$env:GEOCODING_PROVIDER = 'mock'
$env:VITE_API_BASE_URL = 'http://localhost:8000'

$servicesToWaitFor = [System.Collections.Generic.List[int]]::new()
$backendProcess = $null
$frontendProcess = $null

try {
  if (-not $backendReady) {
    $backendArguments = "-m uvicorn app.main:app --app-dir `"$backendPath`" --host 127.0.0.1 --port 8000"
    if ($aiMode -ne 'mock') {
      $envFile = Join-Path $projectRoot '.env'
      if (-not (Test-Path -LiteralPath $envFile)) {
        throw "Live AI mode '$aiMode' requires the project .env file."
      }
      $backendArguments += " --env-file `"$envFile`""
    }
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList $backendArguments -WorkingDirectory $runDirectory -NoNewWindow -PassThru
    $servicesToWaitFor.Add($backendProcess.Id)
    Write-Host 'Starting backend at http://localhost:8000 ...'
  } else {
    Write-Host 'Backend already responds at http://localhost:8000.'
  }

  if (-not $frontendReady) {
    $frontendArguments = "`"$frontendVite`" --host 127.0.0.1"
    $frontendProcess = Start-Process -FilePath (Get-Command node).Source -ArgumentList $frontendArguments -WorkingDirectory $frontendPath -NoNewWindow -PassThru
    $servicesToWaitFor.Add($frontendProcess.Id)
    Write-Host 'Starting frontend at http://localhost:5173 ...'
  } else {
    Write-Host 'Frontend already responds at http://localhost:5173.'
  }

  if ($servicesToWaitFor.Count -gt 0) {
    Write-Host 'Both services run in this PowerShell window. Press Ctrl+C to stop them.'
    $deadline = (Get-Date).AddSeconds(90)
    do {
      Start-Sleep -Seconds 2
      $backendReady = $backendReady -or (Test-HttpEndpoint $backendPort)
      $frontendReady = $frontendReady -or (Test-HttpEndpoint $frontendPort)
      if (-not $backendReady -and $backendProcess -and $backendProcess.HasExited) {
        throw 'Backend stopped before becoming ready. Check the startup error above.'
      }
      if (-not $frontendReady -and $frontendProcess -and $frontendProcess.HasExited) {
        throw 'Frontend stopped before becoming ready. Check the startup error above.'
      }
    } while ((-not $backendReady -or -not $frontendReady) -and (Get-Date) -lt $deadline)

    if (-not $backendReady -or -not $frontendReady) {
      throw 'Timed out waiting for both services to start.'
    }
  }

  Write-Host 'Namma Civic is ready at http://localhost:5173.'
  Start-Process 'http://localhost:5173'

  if ($servicesToWaitFor.Count -gt 0) {
    Wait-Process -Id $servicesToWaitFor.ToArray()
  }
} finally {
  foreach ($serviceProcess in @($backendProcess, $frontendProcess)) {
    if ($serviceProcess -and -not $serviceProcess.HasExited) {
      Stop-Process -Id $serviceProcess.Id -Force -ErrorAction SilentlyContinue
    }
  }
}
