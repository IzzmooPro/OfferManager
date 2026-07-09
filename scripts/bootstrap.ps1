$ErrorActionPreference = "Stop"
$MinimumPython = [Version]"3.12"
$Python = $null

function Install-PythonFromOfficialSite {
    Write-Host "[BILGI] Python resmi sitesinden indiriliyor..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $index = Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/"
    $versions = [regex]::Matches($index.Content, 'href="(3\.13\.\d+)/"') |
        ForEach-Object { [Version]$_.Groups[1].Value } |
        Sort-Object -Descending -Unique
    $latest = $versions | Select-Object -First 1
    if ($null -eq $latest) {
        throw "Python 3.13 indirme surumu resmi sitede belirlenemedi."
    }

    $versionText = $latest.ToString()
    $installer = Join-Path $env:TEMP "python-$versionText-amd64.exe"
    $downloadUrl = "https://www.python.org/ftp/python/$versionText/python-$versionText-amd64.exe"

    try {
        Invoke-WebRequest -UseBasicParsing -Uri $downloadUrl -OutFile $installer
        $process = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList @(
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=1",
            "Include_launcher=1",
            "Include_pip=1"
        )
        if ($process.ExitCode -ne 0) {
            throw "Python resmi kurucusu hata verdi (cikis kodu: $($process.ExitCode))."
        }
    }
    finally {
        Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    }
}

function Test-PythonCommand {
    param(
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    try {
        $versionText = & $Executable @PrefixArgs -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        if ([Version]$versionText -lt $MinimumPython) { return $null }
        return [PSCustomObject]@{
            Executable = $Executable
            PrefixArgs = $PrefixArgs
            Version = $versionText
        }
    }
    catch {
        return $null
    }
}

$Candidates = @(
    [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.13") }
    [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.12") }
    [PSCustomObject]@{ Executable = "python"; PrefixArgs = @() }
    [PSCustomObject]@{ Executable = "python3"; PrefixArgs = @() }
)

foreach ($candidate in $Candidates) {
    $Python = Test-PythonCommand -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs
    if ($null -ne $Python) { break }
}

if ($null -eq $Python) {
    Write-Host "[BILGI] Python 3.12+ bulunamadi. Python 3.13 kuruluyor..."
    $installedWithWinget = $false
    if ($null -ne (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        & winget.exe install --id Python.Python.3.13 --exact --scope user --accept-package-agreements --accept-source-agreements
        $installedWithWinget = ($LASTEXITCODE -eq 0)
    }
    if (-not $installedWithWinget) {
        Install-PythonFromOfficialSite
    }

    $PostInstallCandidates = @(
        [PSCustomObject]@{ Executable = "py"; PrefixArgs = @("-3.13") }
        [PSCustomObject]@{ Executable = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"; PrefixArgs = @() }
        [PSCustomObject]@{ Executable = "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe"; PrefixArgs = @() }
    )
    foreach ($candidate in $PostInstallCandidates) {
        $Python = Test-PythonCommand -Executable $candidate.Executable -PrefixArgs $candidate.PrefixArgs
        if ($null -ne $Python) { break }
    }
}

if ($null -eq $Python) {
    throw "Python kuruldu ancak bu oturumda bulunamadi. Bilgisayari yeniden baslatip Baslat.bat dosyasini tekrar calistirin."
}

Write-Host "[OK] Python $($Python.Version) hazir."
Write-Host "[BILGI] Paketler kontrol ediliyor ve program baslatiliyor..."

$MainFile = Join-Path $PSScriptRoot "..\main.py"
& $Python.Executable @($Python.PrefixArgs) $MainFile
exit $LASTEXITCODE
