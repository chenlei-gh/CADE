Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WUM {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@
Add-Type -AssemblyName System.Windows.Forms

$hwnd = [IntPtr]([long]$args[0])
$count = [int]$args[1]
[void][WUM]::ShowWindow($hwnd, 9)
[void][WUM]::ShowWindow($hwnd, 3)
Start-Sleep -Milliseconds 300
[void][WUM]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

for ($i = 0; $i -lt $count; $i++) {
    [System.Windows.Forms.SendKeys]::SendWait("^z")
    Start-Sleep -Milliseconds 800
}
Write-Output ("sent Ctrl+Z x" + $count)
