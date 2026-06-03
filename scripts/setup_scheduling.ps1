# setup_scheduling.ps1
# Registers a daily background scheduled task in Windows Task Scheduler to run the ingestion pipeline.

# Determine script context and paths
$ScriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$ProjectDir = (Get-Item -Path $ScriptDir).Parent.FullName
$VenvPython = Join-Path -Path $ProjectDir -ChildPath ".venv\Scripts\python.exe"
$SchedulerScript = Join-Path -Path $ProjectDir -ChildPath "src\ingestion\scheduler.py"

if (-not (Test-Path -Path $VenvPython)) {
    Write-Error "Virtual environment python executable not found at: $VenvPython"
    exit 1
}

# Configuration
$TaskName = "MutualFundFAQ_IngestionScheduler"
$Description = "Runs the daily mutual fund data scraping, parsing, hashing, and incremental database refresh ingestion pipeline."
$TriggerTime = "09:00AM"  # Executes daily in the morning at 9:00 AM IST

# Build task configurations
$Action = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$SchedulerScript`" --run-now" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register scheduled task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description -Force
    Write-Host "Successfully registered scheduled task '$TaskName' to run daily at $TriggerTime." -ForegroundColor Green
    Write-Host "Task Working Directory: $ProjectDir" -ForegroundColor Cyan
} catch {
    Write-Error "Failed to register scheduled task: $_"
}
