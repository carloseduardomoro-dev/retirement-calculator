
# Retirement Calculator (Python)

A simple, realistic retirement savings longevity calculator implemented in pure Python. It can:

- Simulate month-by-month how long savings last given expected returns, inflation, expenses, income, and annual extras.
- Estimate the **required initial savings** to make funds last a target number of years using a closed-form real-rate approach.
- Optionally solve the required initial savings using a simulation-based bisection for more complex assumptions.

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **pip** (comes with most Python installs)

## Quick start (virtual environment + install)

> The project has **no required third‑party packages**. We still recommend a virtual environment to keep things clean.

### macOS / Linux

```bash
# From the project folder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run your script (replace with your filename)
python main.py
