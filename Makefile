.PHONY: install demo test lint serve

install:
	python3 -m pip install -r requirements.txt

demo:
	python3 run_demo.py

test:
	python3 -m pytest -q

lint:
	python3 -m py_compile backend/app/main.py backend/app/services/*.py *.py

serve:
	python3 -m uvicorn backend.app.main:app --reload
