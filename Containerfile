FROM fedora:latest

COPY . jirate
RUN cd jirate && dnf -y install python3-pip nano vim-minimal && pip install --user -r requirements.txt .

# TODO: Switch to venv

ENTRYPOINT ["/root/.local/bin/jirate"]
