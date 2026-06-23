.PHONY: install dev test test-all lint format db-push demo

install:
	pip install -r requirements.txt

dev:
	uvicorn backend.main:app --reload --port 8000

test:
	pytest tests/ -v --ignore=tests/test_e2e.py

test-all:
	INTEGRATION=true pytest tests/ -v

lint:
	ruff check backend/

format:
	ruff format backend/

db-push:
	@echo "Apply schema to Supabase:"
	@echo "  1. Open Supabase Dashboard → SQL Editor"
	@echo "  2. Paste contents of infrastructure/supabase/schema.sql"
	@echo "  3. Run the query"
	@echo ""
	@echo "Or use the Supabase CLI:"
	@echo "  supabase db push --db-url \"\$$DATABASE_URL\""

demo:
	@bash scripts/demo.sh
