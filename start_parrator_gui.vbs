Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = scriptDir & "\.venv\Scripts\pythonw.exe"

If Not fso.FileExists(pythonwPath) Then
  MsgBox "Не найден pythonw: " & pythonwPath, vbCritical, "Parrator"
  WScript.Quit 1
End If

shell.CurrentDirectory = scriptDir

' Закрываем уже запущенные процессы Parrator из этого проекта,
' чтобы не оставались старые оверлей-окна.
shell.Run "taskkill /IM Parrator.exe /F >nul 2>&1", 0, True

Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set processes = wmi.ExecQuery("SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name='pythonw.exe'")
For Each proc In processes
  cmdLine = ""
  On Error Resume Next
  cmdLine = proc.CommandLine
  On Error GoTo 0

  If Len(cmdLine) > 0 Then
    hasPython = InStr(1, LCase(cmdLine), LCase(pythonwPath), vbTextCompare) > 0
    hasParrator = InStr(1, LCase(cmdLine), "-m parrator", vbTextCompare) > 0
    hasOverlay = InStr(1, LCase(cmdLine), "parrator\wave_overlay.py", vbTextCompare) > 0
    If hasPython And (hasParrator Or hasOverlay) Then
      shell.Run "taskkill /PID " & proc.ProcessId & " /F >nul 2>&1", 0, True
    End If
  End If
Next
WScript.Sleep 700

command = """" & pythonwPath & """ -m parrator --gui"
shell.Run command, 0, False
