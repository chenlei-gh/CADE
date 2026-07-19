Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class F {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
# Usage: powershell -File cade_findbtn.ps1 <targetPid>
# Brute-force EnumChildWindows + title-text matching, because Win32
# TB_BUTTONCOUNT / UI Automation do NOT reliably work on CATIA's custom
# toolbar widgets. Edit the -match pattern below to your command class names.
$targetPid = [uint32]$args[0]
$results = New-Object System.Collections.ArrayList
$allTop = New-Object System.Collections.ArrayList
$cbTop = {
    param($h, $l)
    $p = 0
    [void][F]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid) { [void]$allTop.Add($h) }
    return $true
}
[void][F]::EnumWindows($cbTop, [IntPtr]::Zero)

$cbChild = {
    param($h, $l)
    $t = New-Object System.Text.StringBuilder 256
    [void][F]::GetWindowText($h, $t, 256)
    $title = $t.ToString()
    if ($title -match "CADEDlgTest4Cmd|CADEStateCommand|CADEIconTestCmd|CADETestModule") {
        $c = New-Object System.Text.StringBuilder 64
        [void][F]::GetClassName($h, $c, 64)
        $r = New-Object F+RECT
        [void][F]::GetWindowRect($h, [ref]$r)
        $vis = [F]::IsWindowVisible($h)
        [void]$results.Add(("hwnd={0} vis={1} rect=({2},{3})-({4},{5}) class={6} title=[{7}]" -f $h, $vis, $r.L, $r.T, $r.R, $r.B, $c.ToString(), $title))
    }
    return $true
}
foreach ($top in $allTop) {
    [void][F]::EnumChildWindows($top, $cbChild, [IntPtr]::Zero)
}
Write-Output ("TOTAL_TOP=" + $allTop.Count + "  MATCHES=" + $results.Count)
$results | ForEach-Object { Write-Output $_ }
