Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WU3 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
Add-Type -AssemblyName System.Windows.Forms

# Usage: powershell -File cade_escape_and_redo.ps1 <hwndDecimal>
$hwnd = [IntPtr]([long]$args[0])
[void][WU3]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 300

$r = New-Object WU3+RECT
[void][WU3]::GetWindowRect($hwnd, [ref]$r)
Write-Output ("winRect=(" + $r.L + "," + $r.T + ")-(" + $r.R + "," + $r.B + ")")

[System.Windows.Forms.SendKeys]::SendWait("^y")
Start-Sleep -Milliseconds 1500
Write-Output "escape+redo sent"
