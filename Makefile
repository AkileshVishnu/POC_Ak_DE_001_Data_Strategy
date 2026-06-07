.PHONY: setup generate-data run-healthcare run-finance run-manufacturing run-all test \
        app-healthcare app-finance app-manufacturing clean help

PYTHON := python
PIP := pip

help:
	@echo "AI-Ready Data Strategy POCs — Command Reference"
	@echo "================================================"
	@echo "make setup               Install all Python dependencies"
	@echo "make generate-data       Generate synthetic data for all projects"
	@echo "make run-healthcare      Run full Healthcare pipeline"
	@echo "make run-finance         Run full Finance pipeline"
	@echo "make run-manufacturing   Run full Manufacturing pipeline"
	@echo "make run-all             Run all three project pipelines"
	@echo "make test                Run all pytest tests"
	@echo "make app-healthcare      Launch Healthcare Streamlit dashboard"
	@echo "make app-finance         Launch Finance Streamlit dashboard"
	@echo "make app-manufacturing   Launch Manufacturing Streamlit dashboard"
	@echo "make clean               Remove generated data and model artifacts"

setup:
	$(PIP) install -r requirements.txt
	@echo "Dependencies installed successfully."

generate-data:
	@echo "Generating synthetic data for all projects..."
	$(PYTHON) Healthcare/src/generate_synthetic_data.py
	$(PYTHON) Finance/src/generate_synthetic_data.py
	$(PYTHON) Manufacturing/src/generate_synthetic_data.py
	@echo "Synthetic data generation complete."

run-healthcare:
	@echo "Running Healthcare pipeline..."
	$(PYTHON) Healthcare/src/generate_synthetic_data.py
	$(PYTHON) Healthcare/src/run_pipeline.py
	$(PYTHON) Healthcare/src/data_quality_checks.py
	$(PYTHON) Healthcare/src/train_model.py
	$(PYTHON) Healthcare/src/evaluate_model.py
	@echo "Healthcare pipeline complete."

run-finance:
	@echo "Running Finance pipeline..."
	$(PYTHON) Finance/src/generate_synthetic_data.py
	$(PYTHON) Finance/src/run_pipeline.py
	$(PYTHON) Finance/src/data_quality_checks.py
	$(PYTHON) Finance/src/train_model.py
	$(PYTHON) Finance/src/evaluate_model.py
	@echo "Finance pipeline complete."

run-manufacturing:
	@echo "Running Manufacturing pipeline..."
	$(PYTHON) Manufacturing/src/generate_synthetic_data.py
	$(PYTHON) Manufacturing/src/run_pipeline.py
	$(PYTHON) Manufacturing/src/data_quality_checks.py
	$(PYTHON) Manufacturing/src/train_model.py
	$(PYTHON) Manufacturing/src/evaluate_model.py
	@echo "Manufacturing pipeline complete."

run-all: run-healthcare run-finance run-manufacturing
	@echo "All pipelines completed successfully."

test:
	$(PYTHON) -m pytest Healthcare/tests/ Finance/tests/ Manufacturing/tests/ -v --tb=short
	@echo "All tests completed."

app-healthcare:
	@echo "Launching Healthcare dashboard at http://localhost:8501"
	streamlit run Healthcare/app/streamlit_app.py --server.port 8501

app-finance:
	@echo "Launching Finance dashboard at http://localhost:8502"
	streamlit run Finance/app/streamlit_app.py --server.port 8502

app-manufacturing:
	@echo "Launching Manufacturing dashboard at http://localhost:8503"
	streamlit run Manufacturing/app/streamlit_app.py --server.port 8503

clean:
	@echo "Cleaning generated files..."
	find . -path "*/data/raw/*.csv" -delete
	find . -path "*/data/bronze/*.parquet" -delete
	find . -path "*/data/silver/*.parquet" -delete
	find . -path "*/data/gold/*.parquet" -delete
	find . -path "*/models/*.pkl" -delete
	find . -path "*/models/*.joblib" -delete
	find . -name "*.duckdb" -delete
	@echo "Clean complete."
