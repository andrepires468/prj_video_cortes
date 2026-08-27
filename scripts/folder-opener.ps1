# Watcher local (Windows): abre pastas no Explorer quando a API (Docker) pede.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/folder-opener.ps1

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$targets = @(
    @{ Dir = (Join-Path $root "data\downloads"); Label = "downloads" },
    @{ Dir = (Join-Path $root "data\cortes"); Label = "cortes" }
)

foreach ($t in $targets) {
    if (-not (Test-Path $t.Dir)) {
        New-Item -ItemType Directory -Path $t.Dir -Force | Out-Null
    }
}

Write-Host "Video Cortes — folder opener ativo."
Write-Host "Observando:"
foreach ($t in $targets) {
    Write-Host (" - " + $t.Dir)
}
Write-Host "Deixe esta janela aberta enquanto usa o app. Ctrl+C para sair."

$watchers = @()
$actions = @()

foreach ($t in $targets) {
    $watcher = New-Object System.IO.FileSystemWatcher
    $watcher.Path = $t.Dir
    $watcher.Filter = ".open"
    $watcher.IncludeSubdirectories = $false
    $watcher.EnableRaisingEvents = $true
    $watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor [System.IO.NotifyFilters]::LastWrite

    $dir = $t.Dir
    $action = {
        $path = $Event.SourceEventArgs.FullPath
        Start-Sleep -Milliseconds 150
        try {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
            }
            Invoke-Item -LiteralPath $Event.MessageData
            Write-Host ("[$(Get-Date -Format 'HH:mm:ss')] Abriu: " + $Event.MessageData)
        } catch {
            Write-Host ("Erro ao abrir pasta: " + $_)
        }
    }

    $null = Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action -MessageData $dir
    $null = Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action -MessageData $dir
    $watchers += $watcher
}

try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    foreach ($w in $watchers) {
        $w.EnableRaisingEvents = $false
        $w.Dispose()
    }
    Get-EventSubscriber | Where-Object { $_.SourceObject -is [System.IO.FileSystemWatcher] } | Unregister-Event
}
