# Windows PowerShell 5.1+ helper. Installs nothing and never cleans existing files.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Check', 'Backend', 'Frontend', 'TestBackend', 'TestFrontend', 'ValidateFrontend')]
    [string]$Command,
    [string]$PythonExecutable,
    [ValidateRange(1, 65535)][int]$Port,
    [string]$BindAddress,
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

function Test-Python {
    param([switch]$Development, [switch]$Models)
    if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
        throw "Python environment not found: $PythonExecutable. See README.md to create a NEW venv, or pass -PythonExecutable."
    }
    $arguments = @('-B', '-W', 'default', (Join-Path $PSScriptRoot 'check_environment.py'))
    if ($Development) { $arguments += '--development' }
    if ($Models) { $arguments += '--models' }
    Invoke-Checked $PythonExecutable $arguments
}

function Test-Node {
    if (-not (Get-Command node.exe -ErrorAction SilentlyContinue) -or
        -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'Node.js/npm not found. Install Node 24.15.0 and npm 11.12.1; see README.md.'
    }
    $nodeVersion = (& node.exe --version).Trim().TrimStart('v')
    $npmVersion = (& npm.cmd --version).Trim()
    if ([version]$nodeVersion -lt [version]'24.15.0' -or ([version]$nodeVersion).Major -ne 24 -or
        ([version]$npmVersion).Major -ne 11) {
        throw "Use Node 24.15.0/npm 11.12.1 (validated baseline). Selected Node $nodeVersion/npm $npmVersion."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\node_modules\vite\package.json'))) {
        throw 'Frontend dependencies missing. Run npm.cmd ci in a NEW frontend checkout/directory; see README.md.'
    }
    Write-Host "Node $nodeVersion; npm $npmVersion."
}

function Assert-FreePort {
    param([string]$Address, [int]$SelectedPort)
    $ip = [System.Net.IPAddress]::Parse($Address)
    $probe = New-Object System.Net.Sockets.TcpListener($ip, $SelectedPort)
    $probe.ExclusiveAddressUse = $true
    try { $probe.Start() }
    catch { throw "Cannot bind ${Address}:$SelectedPort. Choose a free port; existing servers are never reused or stopped." }
    finally { $probe.Stop() }
}

Push-Location -LiteralPath $projectRoot
try {
    switch ($Command) {
        'Check' {
            Test-Python -Development -Models
            Test-Node
            Invoke-Checked $PythonExecutable @('-B', '-m', 'pip', 'check')
        }
        'Backend' {
            Test-Python -Models
            if (-not $BindAddress) {
                $BindAddress = if ($env:UVICORN_HOST) { $env:UVICORN_HOST } else { '127.0.0.1' }
            }
            if (-not $Port) { $Port = if ($env:UVICORN_PORT) { [int]$env:UVICORN_PORT } else { 8765 } }
            Assert-FreePort $BindAddress $Port
            $arguments = @('-B', '-m', 'uvicorn', 'backend.app.main:app', '--host', $BindAddress, '--port', "$Port")
            if ($Reload) { $arguments += '--reload' }
            Write-Host "API at http://${BindAddress}:$Port; storage defaults to data/ unless session overrides are set."
            Invoke-Checked $PythonExecutable $arguments
        }
        'Frontend' {
            Test-Node
            if (-not $BindAddress) { $BindAddress = '127.0.0.1' }
            if (-not $Port) { $Port = 5173 }
            Assert-FreePort $BindAddress $Port
            Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
            try { Invoke-Checked 'npm.cmd' @('run', 'dev', '--', '--host', $BindAddress, '--port', "$Port", '--strictPort') }
            finally { Pop-Location }
        }
        'TestBackend' {
            Test-Python -Development
            $previousUrl = $env:PLACEPRO_API_URL
            try {
                if (-not $env:PLACEPRO_API_URL) {
                    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
                    try {
                        $probe.Start()
                        $env:PLACEPRO_API_URL = "http://127.0.0.1:$($probe.LocalEndpoint.Port)"
                    }
                    finally { $probe.Stop() }
                }
                Write-Host "Pytest owns an isolated server at $env:PLACEPRO_API_URL; temporary stores are fixture-controlled."
                Invoke-Checked $PythonExecutable @('-B', '-m', 'pytest', 'backend/tests/', '-q', '-p', 'no:cacheprovider')
            }
            finally { $env:PLACEPRO_API_URL = $previousUrl }
        }
        'TestFrontend' {
            Test-Node
            Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
            try { Invoke-Checked 'npm.cmd' @('run', 'test') }
            finally { Pop-Location }
        }
        'ValidateFrontend' {
            Test-Node
            # A new output directory ensures Vite never empties previous builds.
            $buildPath = Join-Path $projectRoot ('scratch\frontend-build-' + [guid]::NewGuid().ToString('N'))
            Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
            try {
                Invoke-Checked 'npm.cmd' @('run', 'test')
                Invoke-Checked 'npm.cmd' @('run', 'lint')
                Invoke-Checked 'npm.cmd' @('run', 'build', '--', '--outDir', $buildPath)
                Write-Host "Production assets retained: $buildPath"
            }
            finally { Pop-Location }
        }
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally { Pop-Location }
exit 0
