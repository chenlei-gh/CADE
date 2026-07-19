Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class R {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
}
"@
# Usage: powershell -File cade_resize.ps1 <targetPid>
# Finds the toolbar window by its title ("CADETestModuleTlb" below — edit
# to match your workspace's toolbar identifier) and repositions/resizes it
# to a fixed, on-screen location. Useful for recovering a toolbar that was
# pushed off-screen (e.g. after a corrupted DialogPosition.CATSettings).
$targetPid = [uint32]$args[0]
$script:hwnd = [IntPtr]::Zero
$cb = {
    param($h, $l)
    $p = 0
    [void][R]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid) {
        $t = New-Object System.Text.StringBuilder 256
        [void][R]::GetWindowText($h, $t, 256)
        if ($t.ToString() -eq "CADETestModuleTlb") { $script:hwnd = $h }
    }
    return $true
}
[void][R]::EnumWindows($cb, [IntPtr]::Zero)
if ($script:hwnd -eq [IntPtr]::Zero) { Write-Output "NOT FOUND"; exit 1 }
$r = New-Object R+RECT
[void][R]::GetWindowRect($script:hwnd, [ref]$r)
Write-Output ("BEFORE rect=(" + $r.L + "," + $r.T + ")-(" + $r.R + "," + $r.B + ")")
# make it wide enough for 3x 22px buttons horizontally: move to a fixed screen spot, size 140 x 40
[void][R]::SetWindowPos($script:hwnd, [IntPtr]::Zero, 200, 200, 140, 40, 0x0004)
Start-Sleep -Milliseconds 500
[R+RECT]$r2 = New-Object R+RECT
[void][R]::GetWindowRect($script:hwnd, [ref]$r2)
Write-Output ("AFTER  rect=(" + $r2.L + "," + $r2.T + ")-(" + $r2.R + "," + $r2.B + ")")
