.PHONY: install auth run-stdio run-http doctor test docker-up docker-down

install:
	uv sync
	uv run patchright install chromium

auth:
	uv run gemini-web-mcp --setup-auth

run-stdio:
	uv run gemini-web-mcp --transport stdio

run-http:
	uv run gemini-web-mcp --transport streamable-http --host 0.0.0.0 --port 8765

doctor:
	uv run gemini-web-mcp --doctor

test:
	python3 -m unittest discover -s tests -v

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
