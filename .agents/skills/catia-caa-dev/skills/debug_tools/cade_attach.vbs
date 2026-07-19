Option Explicit
Dim fso, ts, app, doc
Set fso = CreateObject("Scripting.FileSystemObject")
Set ts = fso.OpenTextFile("cade_vbs_trace.log", 8, True)
ts.WriteLine "vbs: start"
On Error Resume Next
Set app = GetObject(, "CATIA.Application")
If Err.Number <> 0 Then
    ts.WriteLine "vbs: attach FAILED: " & Err.Number & " " & Err.Description
    ts.Close
    WScript.Quit 1
End If
Err.Clear
ts.WriteLine "vbs: attached: " & app.Caption
Set doc = app.Documents.Add("Part")
If Err.Number <> 0 Then
    ts.WriteLine "vbs: doc add failed: " & Err.Number & " " & Err.Description
    Err.Clear
Else
    ts.WriteLine "vbs: part doc added"
End If
' Change the command identifier below to the workbench/command you want to
' dispatch programmatically for testing (format: "<Module>.<CommandClass>").
app.StartCommand "CADETestModule.CADEDlgTest4Cmd"
If Err.Number <> 0 Then
    ts.WriteLine "vbs: StartCommand ERROR: " & Err.Number & " " & Err.Description
    Err.Clear
Else
    ts.WriteLine "vbs: StartCommand dispatched OK"
End If
ts.WriteLine "vbs: end"
ts.Close
