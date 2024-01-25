all: container-build jirate-c

container-build:
	if podman images | grep -q '^localhost/jirate'; then \
		echo "Please remove existing container first"; \
		echo "  podman image rm -f localhost/jirate"; \
	else \
		podman build . -t jirate; \
	fi

jirate-c: jirate-c.in
	cat $^ > $@
	chmod +x $@

clean:
	# Note: doesn't destroy the container image
	rm -f jirate-c
