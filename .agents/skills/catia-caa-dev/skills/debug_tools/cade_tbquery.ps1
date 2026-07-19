Add-Type @"
using System;
using System.Runtime.InteropServices;
public class T {
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr wp, IntPtr lp);
    public const uint TB_BUTTONCOUNT = 0x0418; // WM_USER+24
}
"@
# Usage: powershell -File cade_tbquery.ps1 <hwnd>
# NOTE: standard Win32 TB_BUTTONCOUNT does NOT reliably work on CATIA's
# custom toolbar widgets (they are not real ToolbarWindow32 controls) —
# kept for reference/completeness, but prefer cade_findbtn.ps1 or
# cade_enumwin.ps1 for actually inspecting CATIA toolbar contents.
$hwnd = New-Object IntPtr ([int64]$args[0])
$count = [T]::SendMessage($hwnd, [T]::TB_BUTTONCOUNT, [IntPtr]::Zero, [IntPtr]::Zero)
Write-Output ("TB_BUTTONCOUNT for hwnd=" + $hwnd + " => " + $count)
