# Makefile for Smart Attendance Timetable

.PHONY: help build up down logs stop restart clean build-facial build-timetable shell-facial shell-timetable

help:
	@echo "Smart Attendance Timetable - Docker Management"
	@echo "=============================================="
	@echo ""
	@echo "Available commands:"
	@echo "  make build              - Build all Docker images"
	@echo "  make up                 - Start all services"
	@echo "  make down               - Stop and remove containers"
	@echo "  make stop               - Stop services without removing"
	@echo "  make restart            - Restart all services"
	@echo "  make logs               - View all service logs"
	@echo "  make logs-facial        - View facial recognition logs"
	@echo "  make logs-timetable     - View timetable maker logs"
	@echo "  make shell-facial       - Shell into facial recognition container"
	@echo "  make shell-timetable    - Shell into timetable maker container"
	@echo "  make build-facial       - Build only facial recognition image"
	@echo "  make build-timetable    - Build only timetable maker image"
	@echo "  make clean              - Remove all containers and images"
	@echo "  make ps                 - Show running services"
	@echo "  make stats              - Show container resource usage"
	@echo ""

build:
	@echo "Building all Docker images..."
	docker-compose build

build-facial:
	@echo "Building facial recognition image..."
	docker build -f Dockerfile.facial_recognition -t smart-facial-recognition .

build-timetable:
	@echo "Building timetable maker image..."
	docker build -f Dockerfile.timetable_maker -t smart-timetable-maker .

up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "Services started!"
	@echo ""
	@echo "Access endpoints:"
	@echo "  Facial Recognition: http://localhost:5000"
	@echo "  Timetable Maker:    http://localhost:5001"

down:
	@echo "Stopping and removing containers..."
	docker-compose down

stop:
	@echo "Stopping services..."
	docker-compose stop

restart:
	@echo "Restarting services..."
	docker-compose restart

logs:
	docker-compose logs -f

logs-facial:
	docker-compose logs -f facial_recognition

logs-timetable:
	docker-compose logs -f timetable_maker

ps:
	docker-compose ps

stats:
	docker stats

shell-facial:
	docker exec -it smart-facial-recognition bash

shell-timetable:
	docker exec -it smart-timetable-maker bash

clean:
	@echo "Removing all containers, images, and volumes..."
	docker-compose down -v
	docker rmi smart-facial-recognition smart-timetable-maker

.DEFAULT_GOAL := help
