Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Projeler\CineNode"
WshShell.Run "python bot\main.py", 0, False
