.PHONY: setup test run init-db

setup:
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

test:
PYTHONPATH=. pytest tests -v

init-db:
PYTHONPATH=. python -m src.secop_monitor.main init-db --config ./config.yaml

run:
PYTHONPATH=. python -m src.secop_monitor.main run --config ./config.yaml

show-latest:
PYTHONPATH=. python -m src.secop_monitor.main show-latest --n 5
