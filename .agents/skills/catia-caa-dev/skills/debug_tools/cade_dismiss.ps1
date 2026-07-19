Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class D {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
}
"@
Add-Type -AssemblyName System.Windows.Forms
# Usage: powershell -File cade_dismiss.ps1 <targetPid>
# Finds the first visible native #32770 dialog owned by the process and
# sends ENTER to it (e.g. to dismiss a blocking modal such as CATIA's
# "Warm Start" recovery prompt).
$targetPid = [uint32]$args[0]
$script:found = [IntPtr]::Zero
$script:desc = ""
$cb = {
    param($h, $l)
    $p = 0
    [void][D]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid -and [D]::IsWindowVisible($h)) {
        $c = New-Object System.Text.StringBuilder 64
        [void][D]::GetClassName($h, $c, 64)
        if ($c.ToString() -eq "#32770") {
            $script:found = $h
            $t = New-Object System.Text.StringBuilder 256
            [void][D]::GetWindowText($h, $t, 256)
            $script:desc = $t.ToString()
        }
    }
    return $true
}
[void][D]::EnumWindows($cb, [IntPtr]::Zero)
if ($script:found -ne [IntPtr]::Zero) {
    Write-Output ("DISMISS dialog hwnd=" + $script:found + " title=[" + $script:desc + "]")
    [void][D]::ShowWindow($script:found, 1)
    [void][D]::SetForegroundWindow($script:found)
    Start-Sleep -Milliseconds 800
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    Start-Sleep -Milliseconds 1200
    Write-Output "ENTER sent"
} else {
    Write-Output "NO #32770 dialog found"
}
