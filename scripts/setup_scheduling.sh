#!/bin/bash
# setup_scheduling.sh
# Configures and displays Unix crontab guidelines to schedule the daily ingestion pipeline.

# Determine paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( dirname "$SCRIPT_DIR" )"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
SCHEDULER_SCRIPT="$PROJECT_DIR/src/ingestion/scheduler.py"

echo "=========================================================="
echo "      Mutual Fund FAQ Ingestion Pipeline Crontab Setup"
echo "=========================================================="
echo "Project Directory: $PROJECT_DIR"
echo "Python Executable: $VENV_PYTHON"
echo "Scheduler Script:  $SCHEDULER_SCRIPT"
echo "=========================================================="

# Check if python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "WARNING: Virtual environment Python not found at: $VENV_PYTHON"
    echo "Make sure to configure the virtual environment before installing the crontab."
fi

# Define the cron job line: Runs daily at 9:00 AM IST
CRON_JOB="0 9 * * * $VENV_PYTHON $SCHEDULER_SCRIPT --run-now >> $PROJECT_DIR/cron_scheduler.log 2>&1"

echo "To register this daily scheduler, execute:"
echo "(crontab -l 2>/dev/null; echo \"$CRON_JOB\") | crontab -"
echo ""
echo "Or edit your crontab manually using 'crontab -e' and paste the following line:"
echo "$CRON_JOB"
echo "=========================================================="
