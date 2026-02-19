@echo off
echo Running eidosSpeech v2 Test Suite...
echo ==============================================
echo [1/4] Running Unit Tests...
pytest tests\unit -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/4] Running Integration Tests...
pytest tests\integration -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/4] Running Security Tests...
pytest tests\security -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo [4/4] Running Stress Tests...
pytest tests\stress -v
if %errorlevel% neq 0 exit /b %errorlevel%

echo ==============================================
echo ALL TESTS PASSED!
