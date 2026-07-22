Add-Type @"
using System;
using System.Runtime.InteropServices;
public class R {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
}
"@
Add-Type -AssemblyName System.Drawing
# Usage: powershell -File cade_restore_and_shot.ps1 <hwndDecimal> <outPng>
$hwnd = New-Object IntPtr ([int64]$args[0])
$outPng = $args[1]

# Restore window if minimized
if ([R]::IsIconic($hwnd)) { 
    Write-Output "Window is minimized, restoring..."
    [void][R]::ShowWindow($hwnd, 9)  # SW_RESTORE
    Start-Sleep -Milliseconds 500
}
[void][R]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 500

$r = New-Object R+RECT
[void][R]::GetWindowRect($hwnd, [ref]$r)
$w = $r.R - $r.L; $hh = $r.B - $r.T
Write-Output "Window rect: ($($r.L),$($r.T))-($($r.R),$($r.B)) size=$w x $hh"

if ($w -le 0 -or $hh -le 0) { Write-Output "BAD RECT"; exit 1 }
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[void][R]::PrintWindow($hwnd, $dc, 2)
$g.ReleaseHdc($dc)
$g.Dispose()
$bmp.Save($outPng, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output ("SAVED " + $outPng)
