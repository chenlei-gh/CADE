Add-Type @"
using System;
using System.Runtime.InteropServices;
public class CH {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, IntPtr extra);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
# Usage: powershell -File cade_click_on_hwnd.ps1 <hwndDecimal> <relX> <relY>
# Brings the window to the foreground first, then clicks at (relX, relY)
# relative to the window's top-left corner (as reported by GetWindowRect).
$hwnd = New-Object IntPtr ([int64]$args[0])
$relX = [int]$args[1]
$relY = [int]$args[2]
[void][CH]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300
$r = New-Object CH+RECT
[void][CH]::GetWindowRect($hwnd, [ref]$r)
$x = $r.L + $relX
$y = $r.T + $relY
[void][CH]::SetCursorPos($x, $y)
Start-Sleep -Milliseconds 150
[CH]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 100
[CH]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)
Write-Output ("clicked screen(" + $x + "," + $y + ") rel(" + $relX + "," + $relY + ") winRect=(" + $r.L + "," + $r.T + ")-(" + $r.R + "," + $r.B + ")")
