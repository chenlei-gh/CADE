Add-Type -AssemblyName System.Drawing
# Usage: powershell -File cade_crop.ps1 <srcPng> <x> <y> <w> <h> <outPng>
$src = $args[0]
$x = [int]$args[1]
$y = [int]$args[2]
$w = [int]$args[3]
$h = [int]$args[4]
$out = $args[5]
$bmp = New-Object System.Drawing.Bitmap $src
$crop = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($crop)
$g.DrawImage($bmp, (New-Object System.Drawing.Rectangle(0, 0, $w, $h)), (New-Object System.Drawing.Rectangle($x, $y, $w, $h)), [System.Drawing.GraphicsUnit]::Pixel)
$crop.Save($out)
$bmp.Dispose()
$crop.Dispose()
Write-Output "SAVED $out"
