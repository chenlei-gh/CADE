Option Explicit
Dim app
On Error Resume Next
Set app = GetObject(, "CATIA.Application")
If Err.Number <> 0 Then
    WScript.Quit 1
End If
Err.Clear
app.Quit
WScript.Quit 0
