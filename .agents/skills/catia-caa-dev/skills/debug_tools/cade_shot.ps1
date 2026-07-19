Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class S {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr GetWindowDC(IntPtr h);
    [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
}
"@
Add-Type -AssemblyName System.Drawing
# Usage: powershell -File cade_shot.ps1 <targetPid> <outPngPath>
# Finds the largest visible top-level window of the process (assumed to be
# the main window) plus any CATDlgFloatingFrame windows, then saves a PNG
# screenshot of the main window via PrintWindow (works even if occluded).
$targetPid = [uint32]$args[0]
$outPath = $args[1]

$script:mainHwnd = [IntPtr]::Zero
$script:mainArea = 0
$frames = New-Object System.Collections.ArrayList
$cb = {
    param($h, $l)
    $p = 0
    [void][S]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid -and [S]::IsWindowVisible($h)) {
        $c = New-Object System.Text.StringBuilder 64
        [void][S]::GetClassName($h, $c, 64)
        $t = New-Object System.Text.StringBuilder 256
        [void][S]::GetWindowText($h, $t, 256)
        $r = New-Object S+RECT
        [void][S]::GetWindowRect($h, [ref]$r)
        $w = $r.R - $r.L; $hh = $r.B - $r.T
        if ($c.ToString() -match "CATDlgFloatingFrame") {
            [void]$frames.Add(("{0} rect=({1},{2})-({3},{4}) title=[{5}]" -f $h, $r.L, $r.T, $r.R, $r.B, $t.ToString()))
        }
        if (($w * $hh) -gt $script:mainArea) { $script:mainArea = $w * $hh; $script:mainHwnd = $h }
    }
    return $true
}
[void][S]::EnumWindows($cb, [IntPtr]::Zero)
Write-Output "VISIBLE FLOATING FRAMES:"
$frames | ForEach-Object { Write-Output $_ }
if ($script:mainHwnd -eq [IntPtr]::Zero) { Write-Output "NO main window"; exit 1 }
$r = New-Object S+RECT
[void][S]::GetWindowRect($script:mainHwnd, [ref]$r)
$w = $r.R - $r.L; $hh = $r.B - $r.T
Write-Output ("MAIN hwnd=" + $script:mainHwnd + " size=" + $w + "x" + $hh)
$bmp = New-Object System.Drawing.Bitmap $w, $hh
$g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc()
[void][S]::PrintWindow($script:mainHwnd, $dc, 2)
$g.ReleaseHdc($dc)
$g.Dispose()
$bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output ("SAVED " + $outPath)
