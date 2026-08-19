.PHONY: docker-build docker-run docker-stop

docker-build:
	docker build -t kredete-agent:latest .

docker-run:
	docker run --rm -p 8000:8000 -p 8001:8001 --name kredete-agent kredete-agent:latest

docker-stop:
	docker rm -f kredete-agent || true
