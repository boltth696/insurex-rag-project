param([switch]$Stop, [switch]$NoBrowser, [switch]$NewInstance)
$ErrorActionPreference = 'Stop'
$chatRoot = $PSScriptRoot
$chatPython = Join-Path $chatRoot '.venv\Scripts\python.exe'
$chatApp = Join-Path $chatRoot 'app.py'
$chatStorage = Join-Path $chatRoot 'storage'
$chatPidFile = Join-Path $chatStorage 'browser-app.pid'
$chatPortFile = Join-Path $chatStorage 'browser-app.port'
$chatPort = 8501
function Get-ChatOwnedProcesses {
    @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine.Contains(('"' + $chatApp + '"')) -and $_.CommandLine.Contains('-m streamlit run')
    })
}
function Get-ChatFreePort {
    foreach ($chatCandidatePort in 8501..8599) {
        $chatProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $chatCandidatePort)
        $chatProbe.Server.ExclusiveAddressUse = $true
        try {
            $chatProbe.Start()
            return $chatCandidatePort
        } catch [System.Net.Sockets.SocketException] {
            # This port belongs to another process; leave it alone.
        } finally { $chatProbe.Stop() }
    }
    throw 'No free local port was found between 8501 and 8599. Stop an unused chatbot instance and try again.'
}
try {
    $chatProcess = $null
    if (Test-Path -LiteralPath $chatPortFile) {
        $chatSavedPort = 0
        if ([int]::TryParse((Get-Content -LiteralPath $chatPortFile -Raw).Trim(), [ref]$chatSavedPort) -and $chatSavedPort -ge 1 -and $chatSavedPort -le 65535) {
            $chatPort = $chatSavedPort
        }
    }
    if (Test-Path -LiteralPath $chatPidFile) {
        $chatSavedPid = 0
        $chatCandidate = $null
        if ([int]::TryParse((Get-Content -LiteralPath $chatPidFile -Raw).Trim(), [ref]$chatSavedPid)) {
            $chatCandidate = Get-CimInstance Win32_Process -Filter "ProcessId = $chatSavedPid"
        }
        # A reused PID must never cause an unrelated process to be stopped.
        if ($chatCandidate -and $chatCandidate.CommandLine -and $chatCandidate.CommandLine.Contains(('"' + $chatApp + '"')) -and $chatCandidate.CommandLine.Contains('-m streamlit run')) {
            $chatProcess = Get-Process -Id $chatSavedPid -ErrorAction SilentlyContinue
        }
        # Recover a still-running interpreter child even if its venv parent ended.
        if (-not $chatProcess) {
            $chatOwnedIds = @(Get-ChatOwnedProcesses | ForEach-Object { $_.ProcessId })
            $chatLiveListener = Get-NetTCPConnection -LocalPort $chatPort -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $chatOwnedIds } | Select-Object -First 1
            if ($chatLiveListener) { $chatProcess = Get-Process -Id $chatLiveListener.OwningProcess -ErrorAction SilentlyContinue }
        }
    }
    if ($Stop) {
        # Windows venv Python can launch a second Python process. Stop every
        # Python process running this exact app, including its interpreter child.
        $chatOwnedProcesses = Get-ChatOwnedProcesses
        foreach ($chatOwnedProcess in $chatOwnedProcesses) {
            Stop-Process -Id $chatOwnedProcess.ProcessId -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $chatPidFile) { Remove-Item -LiteralPath $chatPidFile }
        if (Test-Path -LiteralPath $chatPortFile) { Remove-Item -LiteralPath $chatPortFile }
        exit 0
    }
    if (-not (Test-Path -LiteralPath $chatPython)) { throw 'The project Python environment is missing. Follow the README setup instructions first.' }
    $chatRunStorage = $chatStorage
    if ($NewInstance) {
        $chatProcess = $null
        $chatRunStorage = Join-Path $chatStorage ('browser-instances\' + [guid]::NewGuid().ToString('N'))
        $chatPidFile = Join-Path $chatRunStorage 'browser-app.pid'
        $chatPortFile = Join-Path $chatRunStorage 'browser-app.port'
    }
    if (-not $chatProcess) {
        $chatPort = Get-ChatFreePort
        New-Item -ItemType Directory -Path $chatRunStorage -Force | Out-Null
        $chatArgs = @('-m', 'streamlit', 'run', ('"' + $chatApp + '"'), '--server.address', '127.0.0.1', '--server.port', $chatPort)
        $chatPreviousStorage = [Environment]::GetEnvironmentVariable('INSUREX_UI_STORAGE_DIR', 'Process')
        try {
            if ($NewInstance) { $env:INSUREX_UI_STORAGE_DIR = Join-Path $chatRunStorage 'data' }
            $chatProcess = Start-Process -FilePath $chatPython -ArgumentList $chatArgs -WorkingDirectory $chatRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $chatRunStorage 'browser-app.log') -RedirectStandardError (Join-Path $chatRunStorage 'browser-app-error.log')
        } finally { [Environment]::SetEnvironmentVariable('INSUREX_UI_STORAGE_DIR', $chatPreviousStorage, 'Process') }
        Set-Content -LiteralPath $chatPidFile -Value $chatProcess.Id
        Set-Content -LiteralPath $chatPortFile -Value $chatPort
    }
    $chatUrl = "http://127.0.0.1:$chatPort"
    $chatReady = $false
    for ($chatAttempt = 0; $chatAttempt -lt 30; $chatAttempt++) {
        if ($chatProcess.HasExited) { throw "The chatbot stopped during startup. See $chatRunStorage/browser-app-error.log for details." }
        try {
            $chatResponse = Invoke-WebRequest -Uri "$chatUrl/_stcore/health" -UseBasicParsing -TimeoutSec 1
            if ($chatResponse.StatusCode -eq 200) { $chatReady = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $chatReady) { throw 'The chatbot is taking too long to start. Try Stop Chatbot, then Start Chatbot again.' }
    Write-Output "Chatbot ready: $chatUrl"
    if (-not $NoBrowser) { Start-Process $chatUrl }
} catch {
    Write-Error -Message $_.Exception.Message -ErrorAction Continue
    if (-not $NoBrowser) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'InsureX Chatbot') | Out-Null
    }
    exit 1
}
