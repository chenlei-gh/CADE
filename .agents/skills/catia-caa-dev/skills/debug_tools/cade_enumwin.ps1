Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
"@
# Usage: powershell -File cade_enumwin.ps1 <targetPid>
# Lists all top-level windows owned by the target process, plus any child
# windows that look like dialogs (class "#32770" or title containing "CADEDlg").
$targetPid = [uint32]$args[0]
$lines = New-Object System.Collections.ArrayList
$topHwnds = New-Object System.Collections.ArrayList
function Describe($h) {
    $t = New-Object System.Text.StringBuilder 256
    $c = New-Object System.Text.StringBuilder 64
    [void][W]::GetWindowText($h, $t, 256)
    [void][W]::GetClassName($h, $c, 64)
    $r = New-Object W+RECT
    [void][W]::GetWindowRect($h, [ref]$r)
    $vis = [W]::IsWindowVisible($h)
    return ("{0}  vis={1}  rect=({2},{3})-({4},{5})  class={6}  title=[{7}]" -f $h, $vis, $r.L, $r.T, $r.R, $r.B, $c.ToString(), $t.ToString())
}
$cbTop = {
    param($h, $l)
    $p = 0
    [void][W]::GetWindowThreadProcessId($h, [ref]$p)
    if ($p -eq $targetPid) {
        [void]$lines.Add(("TOP " + (Describe $h)))
        [void]$topHwnds.Add($h)
    }
    return $true
}
[void][W]::EnumWindows($cbTop, [IntPtr]::Zero)
# pass 2: children that look like dialogs (class contains #32770, or title contains CADEDlg), any depth
$cbChild = {
    param($h, $l)
    $c = New-Object System.Text.StringBuilder 64
    [void][W]::GetClassName($h, $c, 64)
    $cls = $c.ToString()
    $t = New-Object System.Text.StringBuilder 256
    [void][W]::GetWindowText($h, $t, 256)
    if ($cls -match "#32770" -or $t.ToString() -match "CADEDlg") {
        [void]$lines.Add(("CHILD parent=" + [W]::GetParent($h) + " hwnd=" + (Describe $h)))
    }
    return $true
}
foreach ($hw in $topHwnds) { [void][W]::EnumChildWindows($hw, $cbChild, [IntPtr]::Zero) }
Write-Output ("TOTAL_TOP=" + $topHwnds.Count)
$lines | ForEach-Object { Write-Output $_ }
