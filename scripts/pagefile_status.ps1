# Read-only pagefile / commit status for Wan14B gate. Never reboots.
$ErrorActionPreference = "Continue"
Write-Host "=== PageFileSetting (configured; may need reboot to apply) ==="
Get-CimInstance Win32_PageFileSetting | Format-Table Name, InitialSize, MaximumSize -AutoSize
Write-Host "=== PageFileUsage (active now) ==="
Get-CimInstance Win32_PageFileUsage | Format-Table Name, AllocatedBaseSize, CurrentUsage -AutoSize

$c = Get-CimInstance Win32_PageFileUsage | Where-Object { $_.Name -match '(?i)^C:\\' } | Select-Object -First 1
$cAlloc = if ($c) { [int]$c.AllocatedBaseSize } else { 0 }
$secondary = Get-CimInstance Win32_PageFileUsage | Where-Object {
    $_.Name -notmatch '(?i)^C:\\' -and [int]$_.AllocatedBaseSize -ge 7000
} | Select-Object -First 1

Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class PagefileStatusMem {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Auto)]
  public class MEMORYSTATUSEX {
    public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
    public uint dwMemoryLoad; public ulong ullTotalPhys; public ulong ullAvailPhys;
    public ulong ullTotalPageFile; public ulong ullAvailPageFile;
    public ulong ullTotalVirtual; public ulong ullAvailVirtual; public ulong ullAvailExtendedVirtual;
  }
  [DllImport("kernel32.dll", CharSet=CharSet.Auto, SetLastError=true)]
  public static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX b);
}
"@ -ErrorAction SilentlyContinue
$m = New-Object PagefileStatusMem+MEMORYSTATUSEX
[void][PagefileStatusMem]::GlobalMemoryStatusEx($m)
$commit = [math]::Round($m.ullTotalPageFile / 1GB, 2)
Write-Host ("CommitLimitGiB={0}" -f $commit)

$cfg = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -match '(?i)^C:\\' } | Select-Object -First 1
$cfgMb = if ($cfg) { [int]$cfg.InitialSize } else { 0 }
if ($cfgMb -ge 8000 -and $cAlloc -lt 8000) {
    Write-Host "CONFIGURED: C pagefile ${cfgMb} MB is set but NOT active yet (still ${cAlloc} MB)."
    Write-Host "ACTION: reboot Windows yourself when convenient, then: .\scripts\local_studio.ps1 after-reboot-wan"
    Write-Host "This script will not reboot."
    exit 2
}
if ($secondary -or $cAlloc -ge 8000) {
    Write-Host "RESULT: PASS — ready for Wan14B gate"
    exit 0
}
Write-Host "RESULT: FAIL — active pagefile too small for Wan14B"
exit 1
