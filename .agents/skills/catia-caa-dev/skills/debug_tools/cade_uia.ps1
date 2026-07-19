Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class U {
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
}
"@
# Usage: powershell -File cade_uia.ps1 <hwnd>
# NOTE: UI Automation does NOT reliably enumerate CATIA's custom toolbar
# button controls either (kept for reference) — prefer cade_findbtn.ps1 /
# cade_enumwin.ps1 (brute-force EnumChildWindows + title matching) for
# actually inspecting CATIA window/toolbar contents from outside the process.
$hwnd = New-Object IntPtr ([int64]$args[0])
$elem = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
if ($null -eq $elem) { Write-Output "Could not get AutomationElement"; exit 1 }
Write-Output ("Root: " + $elem.Current.Name + " / " + $elem.Current.ControlType.ProgrammaticName)
$cond = [System.Windows.Automation.Condition]::TrueCondition
$children = $elem.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
Write-Output ("Descendant count: " + $children.Count)
foreach ($c in $children) {
    $r = $c.Current.BoundingRectangle
    Write-Output ("  name=[" + $c.Current.Name + "] type=" + $c.Current.ControlType.ProgrammaticName + " rect=(" + $r.X + "," + $r.Y + "," + $r.Width + "," + $r.Height + ")")
}
