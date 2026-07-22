Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class T2 {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
$targetPid = [uint32]$args[0]
$lines = New-Object System.Collections.ArrayList
$cb = {
    param($h, $l)
    $p = 0
    [void][T2]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid) {
        $t = New-Object System.Text.StringBuilder 256
        [void][T2]::GetWindowText($h, $t, 256)
        $c = New-Object System.Text.StringBuilder 64
        [void][T2]::GetClassName($h, $c, 64)
        $r = New-Object T2+RECT
        [void][T2]::GetWindowRect($h, [ref]$r)
        $vis = [T2]::IsWindowVisible($h)
        [void]$lines.Add(("hwnd={0} vis={1} rect=({2},{3})-({4},{5}) class={6} title=[{7}]" -f $h, $vis, $r.L, $r.T, $r.R, $r.B, $c.ToString(), $t.ToString()))
    }
    return $true
}
[void][T2]::EnumWindows($cb, [IntPtr]::Zero)
$lines | ForEach-Object { Write-Output $_ }
