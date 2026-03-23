#!/usr/bin/env bash
# ===========================================================================
# Setup monitoring cron jobs for Halal Check API
# ===========================================================================
# Usage: bash scripts/setup_monitoring_cron.sh
#
# This script installs two cron jobs:
#   1. Health check every 5 minutes (alternative to daemon mode)
#   2. Weekly report every Monday at 00:00 UTC
#
# Environment variables can be set in /etc/halal-check-monitor.env
# ===========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CRON_ENV_FILE="/etc/halal-check-monitor.env"
LOG_FILE="/var/log/halal-check-monitor.log"
PYTHON="$(which python3)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Prerequisites ---
if ! command -v python3 &>/dev/null; then
    log_error "python3 not found. Install Python 3.12+ first."
    exit 1
fi

# Check required Python packages
if ! python3 -c "import httpx" 2>/dev/null; then
    log_error "Required Python packages not installed. Run: pip install -r requirements.txt"
    exit 1
fi

# --- Configuration ---
log_info "Project directory: $PROJECT_DIR"
log_info "Python: $PYTHON"
log_info "Log file: $LOG_FILE"

# Create env file template if it doesn't exist
if [ ! -f "$CRON_ENV_FILE" ]; then
    log_info "Creating environment file template at $CRON_ENV_FILE"
    sudo tee "$CRON_ENV_FILE" > /dev/null << 'ENVEOF'
# Halal Check API Monitoring Configuration
# Edit these values to configure monitoring behavior

# API base URL to monitor
API_BASE_URL=http://localhost:8000

# Webhook URL for alerts (Slack, Discord, etc.)
# WEBHOOK_URL=https://hooks.slack.com/services/xxx

# Email alerting (SMTP)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
# SMTP_FROM=your-email@gmail.com
# SMTP_TO=oncall@example.com

# Health check interval in seconds (for daemon mode only)
CHECK_INTERVAL=60
ENVEOF
    sudo chmod 600 "$CRON_ENV_FILE"
    log_warn "Edit $CRON_ENV_FILE to configure webhook/email alerts"
fi

# Ensure log file is writable
sudo touch "$LOG_FILE" 2>/dev/null && sudo chmod 644 "$LOG_FILE" 2>/dev/null || {
    LOG_FILE="$PROJECT_DIR/logs/monitor.log"
    mkdir -p "$(dirname "$LOG_FILE")"
    log_warn "Cannot write to /var/log/, using $LOG_FILE instead"
}

# --- Install cron jobs ---
log_info "Setting up cron jobs..."

CRON_MARKER="# HALAL-CHECK-MONITOR"

# Remove old cron entries with our marker
(crontab -l 2>/dev/null | grep -v "$CRON_MARKER") | crontab - 2>/dev/null || true

# Build cron entries
# Health check every 5 minutes
HEALTH_CRON="*/5 * * * * cd $PROJECT_DIR && $PYTHON -m monitoring.run --once >> $LOG_FILE 2>&1 $CRON_MARKER"

# Weekly report every Monday at 00:00 UTC
REPORT_CRON="0 0 * * 1 cd $PROJECT_DIR && $PYTHON -m monitoring.run --report >> $LOG_FILE 2>&1 $CRON_MARKER"

# Add new cron entries
(crontab -l 2>/dev/null; echo "$HEALTH_CRON"; echo "$REPORT_CRON") | crontab -

log_info "Cron jobs installed:"
echo ""
echo "  Health check:  */5 * * * * (every 5 minutes)"
echo "  Weekly report: 0 0 * * 1   (every Monday at 00:00 UTC)"
echo "  Log file:      $LOG_FILE"
echo ""

# --- Verify ---
log_info "Current crontab for this service:"
crontab -l 2>/dev/null | grep "$CRON_MARKER" || echo "  (none found)"

echo ""
log_info "Setup complete!"
echo ""
echo "To use daemon mode instead of cron (continuous monitoring):"
echo "  cd $PROJECT_DIR && python -m monitoring.run"
echo ""
echo "To test a single health check:"
echo "  cd $PROJECT_DIR && python -m monitoring.run --once"
echo ""
echo "To generate a report now:"
echo "  cd $PROJECT_DIR && python -m monitoring.run --report"
