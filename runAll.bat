@ECHO OFF
pause
FOR /L %%i IN (1, 1, 7) DO (
	ECHO Starting Router %%i with config%%i.txt...
	start cmd.exe /k python rip.py config%%i.txt
)
pause