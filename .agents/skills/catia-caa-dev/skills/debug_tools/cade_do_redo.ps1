Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WR {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, IntPtr extra);
}
"@
Add-Type -AssemblyName System.Windows.Forms

$hwnd = [IntPtr]([long]$args[0])
[void][WR]::ShowWindow($hwnd, 9)
[void][WR]::ShowWindow($hwnd, 3)
Start-Sleep -Milliseconds 300
[void][WR]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

[void][WR]::SetCursorPos(1280, 700)
Start-Sleep -Milliseconds 150
[WR]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 100
[WR]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 300

[System.Windows.Forms.SendKeys]::SendWait("^y")
Start-Sleep -Milliseconds 1500
Write-Output "redo sent"
