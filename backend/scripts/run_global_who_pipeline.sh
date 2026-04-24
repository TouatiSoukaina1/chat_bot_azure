#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/soukainatouati/devs/chat_bot_azure/backend"
CONDA_SH="/opt/miniconda3/etc/profile.d/conda.sh"
ENV_NAME="chatbot_azure"

cd "$PROJECT_DIR"

export APP_ENV=prod
export LOG_LEVEL=INFO
export PYTHONUNBUFFERED=1

source "$CONDA_SH"
conda activate "$ENV_NAME"

python -m scripts.run_global_who_pipeline