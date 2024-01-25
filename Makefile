all: container-build jirate-c

container-build:
	podman images | grep '^localhost/jirate' && echo "Please remove existing image: podman image rm localhost/jirate" && false
	podman build . -t jirate

jirate-c: jirate-c.in
	cat $^ > $@
	chmod +x $@

clean:
	# Note: doesn't destroy the container image
	rm -f jirate-c
