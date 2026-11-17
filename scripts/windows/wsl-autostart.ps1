# A feldolgozó Windowsos gépen: a WSL bejelentkezéskor ablak nélkül elindul és futva marad, így a
# worker, a timerek és a riportok nyitott terminál nélkül is dolgoznak. A tükrözött hálózattal a WSL
# portjai a Windows Tailscale-címén is látszanak (FIN-301).
#
# Futtatás PowerShellből, a saját felhasználóddal (rendszergazda nem kell):
#   powershell -ExecutionPolicy Bypass -File scripts\windows\wsl-autostart.ps1
# Visszavonás:
#   Unregister-ScheduledTask -TaskName 'finance-tracker WSL' -Confirm:$false

param(
    [string]$Distro = 'Ubuntu-24.04'
)
$ErrorActionPreference = 'Stop'

# 1. Bejelentkezéskor induló, rejtett feladat: a sleep tartja életben a WSL-t, a systemd indítja a Dockert.
$command = "Start-Process -WindowStyle Hidden -FilePath wsl.exe -ArgumentList '-d','$Distro','--exec','/bin/sleep','infinity'"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -Command `"$command`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Hidden
Register-ScheduledTask -TaskName 'finance-tracker WSL' -Action $action -Trigger $trigger -Settings $settings `
    -Description 'A pénzügyi nyomkövető otthoni stackje: a WSL futva tartása ablak nélkül.' -Force | Out-Null
Write-Host "Kész: a 'finance-tracker WSL' feladat bejelentkezéskor elindítja a(z) $Distro disztribúciót."

# 2. Tükrözött hálózat: csak hozzáad, a meglévő .wslconfig többi beállításához nem nyúl.
$config = Join-Path $env:USERPROFILE '.wslconfig'
$current = if (Test-Path $config) { Get-Content $config -Raw } else { '' }
if ($current -match '(?m)^\s*networkingMode\s*=') {
    Write-Host "A $config már megadja a networkingMode-ot, nem módosítom."
} else {
    if ($current -notmatch '(?m)^\[wsl2\]') { $current = $current.TrimEnd() + "`r`n[wsl2]`r`n" }
    $current = $current -replace '(?m)^\[wsl2\]\s*$', "[wsl2]`r`nnetworkingMode=mirrored"
    Set-Content -Path $config -Value $current.TrimStart() -Encoding utf8
    Write-Host "A $config tükrözött hálózatot kapott; érvényes a következő 'wsl --shutdown' után."
}
