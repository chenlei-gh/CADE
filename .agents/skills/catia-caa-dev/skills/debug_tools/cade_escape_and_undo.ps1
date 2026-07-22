Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WU2 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
Add-Type -AssemblyName System.Windows.Forms

# Usage: powershell -File cade_escape_and_undo.ps1 <hwndDecimal>
$hwnd = [IntPtr]([long]$args[0])
[void][WU2]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

# Cancel any pending inline rename/edit in the tree.
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 300

$r = New-Object WU2+RECT
[void][WU2]::GetWindowRect($hwnd, [ref]$r)
Write-Output ("winRect=(" + $r.L + "," + $r.T + ")-(" + $r.R + "," + $r.B + ")")

[System.Windows.Forms.SendKeys]::SendWait("^z")
Start-Sleep -Milliseconds 1500
Write-Output "escape+undo sent"
