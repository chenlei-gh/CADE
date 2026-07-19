Add-Type @"
using System;
using System.Runtime.InteropServices;
public class P {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, IntPtr extra);
    public const uint LEFTDOWN = 0x0002;
    public const uint LEFTUP = 0x0004;
}
"@
# Usage: powershell -File cade_probeclick.ps1 <screenX> <screenY>
# Simulates a real left mouse click at absolute screen coordinates. Useful
# for testing toolbar buttons whose hwnd cannot be driven directly via
# SendMessage (CATIA's custom toolbar widgets ignore BM_CLICK/WM_LBUTTONDOWN).
$x = [int]$args[0]
$y = [int]$args[1]
[void][P]::SetCursorPos($x, $y)
Start-Sleep -Milliseconds 200
[P]::mouse_event([P]::LEFTDOWN, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 100
[P]::mouse_event([P]::LEFTUP, 0, 0, 0, [IntPtr]::Zero)
Write-Output ("clicked (" + $x + "," + $y + ")")
