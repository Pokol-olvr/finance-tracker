# SSH-kulcs cseréje egy géphez, a régi kulcs eltávolításával. Évente, és azonnal, ha egy gép elveszik
# vagy gazdát cserél. Az SSH-kulcsnak nincs lejárata: addig érvényes, amíg az authorized_keys-ben van.
#
# Futtatás PowerShellből, a saját felhasználóddal:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\rotate-ssh-key.ps1 -HostAlias malna -KeyFile id_ed25519
#   powershell -ExecutionPolicy Bypass -File scripts\windows\rotate-ssh-key.ps1 -HostAlias malna-olvaso -KeyFile id_ed25519_olvaso
#
# A HostAlias a ~/.ssh/config egy bejegyzése, amely a KeyFile kulccsal lép be. A lépések:
#   1. új kulcs (a jelmondatot az ssh-keygen kéri; a korlátozott felhasználónál üresen is hagyható),
#   2. az új kulcs felkerül a távoli authorized_keys-be a régivel belépve,
#   3. belépés csak az új kulccsal, és ugyanebben a kapcsolatban a régi kulcs törlése; ha az új
#      kulccsal nem sikerül belépni, a régi marad, és helyben semmi nem változik,
#   4. helyben a régi fájl átnevezve (.regi-DÁTUM), az új a helyére kerül, az ssh-agent frissül.
# Az új kulcs jelmondatát háromszor kéri: kétszer generáláskor, egyszer a 3. lépésben.

param(
    [Parameter(Mandatory)][string]$HostAlias,
    [Parameter(Mandatory)][string]$KeyFile
)
$ErrorActionPreference = 'Stop'

$ssh = "$env:WINDIR\System32\OpenSSH\ssh.exe"
$keygen = "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe"
$sshAdd = "$env:WINDIR\System32\OpenSSH\ssh-add.exe"
$dir = Join-Path $env:USERPROFILE '.ssh'
$old = Join-Path $dir $KeyFile
$new = "$old.uj"
$stamp = Get-Date -Format 'yyyy-MM-dd'

if (-not (Test-Path $old)) { throw "Nincs ilyen kulcs: $old" }
if (Test-Path $new) { Remove-Item $new, "$new.pub" -ErrorAction SilentlyContinue }
$oldPub = (Get-Content "$old.pub" -Raw).Trim()

# A config régi kulcsát az SSH mindig felajánlaná, ezért az új kulcsos lépések a config nélkül,
# a feloldott felhasználóval és címmel futnak, csak az új kulccsal.
$resolved = & $ssh -G $HostAlias
$target = ($resolved | Where-Object { $_ -like 'user *' }).Split(' ')[1] + '@' + ($resolved | Where-Object { $_ -like 'hostname *' }).Split(' ')[1]
$onlyNew = @('-F', 'NUL', '-i', $new, '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none')

Write-Host "1. Új kulcs: $new"
& $keygen -t ed25519 -f $new -C "$env:USERNAME@$env:COMPUTERNAME $stamp"
if ($LASTEXITCODE -ne 0) { throw 'Az új kulcs nem készült el.' }
$newPub = (Get-Content "$new.pub" -Raw).Trim()

Write-Host '2. Az új kulcs felkerül a távoli gépre (a régi kulccsal)'
$newPub | & $ssh $HostAlias 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
if ($LASTEXITCODE -ne 0) { throw 'Az új kulcs nem került fel; helyben semmi nem változott.' }

Write-Host '3. Belépés csak az új kulccsal, és a régi kulcs törlése a távoli gépről'
# A régi kulcs a bemeneten megy át: a Windows PowerShell a parancssorból kiszedné az idézőjeleket.
$oldPub | & $ssh @onlyNew $target 'grep -vxF -f - ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.uj && mv ~/.ssh/authorized_keys.uj ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
if ($LASTEXITCODE -ne 0) {
    throw 'Az új kulccsal nem sikerült belépni, vagy a régi nem törlődött. A régi kulcs működik; a távoli authorized_keys végén az új sor kézzel törölhető.'
}

Write-Host '4. Csere helyben'
# Az agentet csak akkor érintjük, ha a régi kulcs benne volt; a hibája nem állíthatja meg a cserét.
$ErrorActionPreference = 'Continue'
$oldBody = ($oldPub -split ' ')[1]
$inAgent = ((& $sshAdd -L 2>&1) -join "`n").Contains($oldBody)
if ($inAgent) { & $sshAdd -d "$old.pub" | Out-Null }
$ErrorActionPreference = 'Stop'
Rename-Item $old "$KeyFile.regi-$stamp"
Rename-Item "$old.pub" "$KeyFile.pub.regi-$stamp"
Rename-Item $new $KeyFile
Rename-Item "$new.pub" "$KeyFile.pub"
if ($inAgent) { & $sshAdd $old }

& $ssh $HostAlias 'echo "Belépés az új kulccsal: $(whoami)@$(hostname)"'
Write-Host "Kész. A régi kulcs fájljai: $dir\$KeyFile.regi-$stamp; ha minden működik, törölhetők."
