' Poker Guru, no window: double-click this instead of start.bat.
' Runs start.bat hidden (updates, first-time setup, server), waits for the server
' to answer, and shows a message only if something went wrong. Output is in
' trainer.log next to this file. Stop the server with "Stop the trainer" at the
' bottom of any page in the app.
Option Explicit
Dim sh, fso, here, urlFile, url, i, http, ok
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = here
urlFile = fso.BuildPath(here, ".trainer_url")
If fso.FileExists(urlFile) Then fso.DeleteFile urlFile
sh.Run "cmd /c ""start.bat"" --quiet", 0, False

' Wait up to 3 minutes (first run installs packages) for the server to say where it is.
ok = False
For i = 1 To 180
  WScript.Sleep 1000
  If fso.FileExists(urlFile) Then
    url = Trim(fso.OpenTextFile(urlFile, 1).ReadAll)
    On Error Resume Next
    Set http = CreateObject("MSXML2.XMLHTTP")
    http.Open "GET", url & "/api/version", False
    http.Send
    If Err.Number = 0 And http.Status = 200 Then ok = True
    On Error GoTo 0
    If ok Then Exit For
  End If
Next
If Not ok Then
  MsgBox "Poker Guru did not start. Open trainer.log in this folder to see why, or run start.bat to watch it start.", 48, "Poker Guru"
End If
