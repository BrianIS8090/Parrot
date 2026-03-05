Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = scriptDir & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonwPath) Then
  MsgBox "Не найден pythonw: " & pythonwPath, vbCritical, "Parrator"
  WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir
command = """" & pythonwPath & """ -m parrator --gui"
shell.Run command, 0, False
