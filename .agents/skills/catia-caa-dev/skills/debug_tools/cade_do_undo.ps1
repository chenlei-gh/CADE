Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WU {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, IntPtr extra);
}
"@
Add-Type -AssemblyName System.Windows.Forms

$hwnd = [IntPtr]([long]$args[0])
[void][WU]::ShowWindow($hwnd, 9)   # SW_RESTORE
[void][WU]::ShowWindow($hwnd, 3)   # SW_MAXIMIZE
Start-Sleep -Milliseconds 300
[void][WU]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

# Click inside the 3D view client area to make sure keyboard focus is
# actually on the document window, not just the top-level frame.
[void][WU]::SetCursorPos(1280, 700)
Start-Sleep -Milliseconds 150
[WU]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)  # LEFTDOWN
Start-Sleep -Milliseconds 100
[WU]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)  # LEFTUP
Start-Sleep -Milliseconds 300

[System.Windows.Forms.SendKeys]::SendWait("^z")
Start-Sleep -Milliseconds 1500
Write-Output "undo sent"
