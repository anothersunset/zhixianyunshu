@echo off
setlocal

set "MAVEN_VERSION=3.9.9"
set "MAVEN_HOME=%USERPROFILE%\.m2\wrapper\dists\apache-maven-%MAVEN_VERSION%"
set "MAVEN_DIR=%MAVEN_HOME%\apache-maven-%MAVEN_VERSION%"
set "MAVEN_CMD=%MAVEN_DIR%\bin\mvn.cmd"
set "MAVEN_URL=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven-%MAVEN_VERSION%/apache-maven-%MAVEN_VERSION%-bin.zip"

if not exist "%MAVEN_CMD%" (
  echo Downloading Maven %MAVEN_VERSION%...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='Stop';" ^
    "New-Item -ItemType Directory -Force -Path '%MAVEN_HOME%' | Out-Null;" ^
    "$zip=Join-Path '%MAVEN_HOME%' 'maven.zip';" ^
    "Invoke-WebRequest -Uri '%MAVEN_URL%' -OutFile $zip;" ^
    "Expand-Archive -LiteralPath $zip -DestinationPath '%MAVEN_HOME%' -Force;" ^
    "Remove-Item -LiteralPath $zip -Force"
)

if not exist "%MAVEN_CMD%" (
  echo Maven wrapper download failed: %MAVEN_CMD% not found
  exit /b 1
)

call "%MAVEN_CMD%" %*
