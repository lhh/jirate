all: container-build jirate-c

container-build-darwin:
	if container image ls | grep -q '^localhost/jirate'; then \
		echo "Please remove existing container first"; \
		echo "  container image rm localhost/jirate"; \
	else \
		container build . -t localhost/jirate -f Containerfile.darwin; \
	fi

container-build-linux:
	if podman images | grep -q '^localhost/jirate'; then \
		echo "Please remove existing container first"; \
		echo "  podman image rm -f localhost/jirate"; \
	else \
		podman build . -t jirate; \
	fi

container-build:
	if [ "$$(uname -o)" == "Darwin" ]; then \
		make container-build-darwin; \
	else \
		make container-build-linux; \
	fi

jirate-c: jirate-c.in
	cat $^ > $@
	chmod +x $@

clean:
	# Note: doesn't destroy the container image
	rm -f jirate-c
