.PHONY: help setup start stop restart logs clean build

help:
	@echo "Customer Intelligence Tool - Available Commands"
	@echo ""
	@echo "  make setup      - Initial setup (create .env and directories)"
	@echo "  make build      - Build Docker containers"
	@echo "  make start      - Start the application"
	@echo "  make stop       - Stop the application"
	@echo "  make restart    - Restart the application"
	@echo "  make logs       - View application logs"
	@echo "  make collect    - Trigger manual collection"
	@echo "  make clean      - Remove data and containers"
	@echo "  make dev        - Run backend in development mode"
	@echo ""

setup:
	@./setup.sh

build:
	podman-compose build

start:
	podman-compose up -d
	@echo ""
	@echo "Application started!"
	@echo "API: http://localhost:8000/docs"
	@echo "Dashboard: http://localhost:3000"
	@echo ""
	@echo "View logs: make logs"

stop:
	podman-compose down

restart: stop start

logs:
	podman-compose logs -f

collect:
	@echo "Triggering manual collection..."
	@curl -X POST http://localhost:8000/api/collect/trigger
	@echo ""

clean:
	podman-compose down -v
	rm -rf data/db/* data/chroma/*
	@echo "Cleaned data and containers"

dev:
	@echo "Starting backend in development mode..."
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
