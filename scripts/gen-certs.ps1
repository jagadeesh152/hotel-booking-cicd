# Generates a self-signed TLS certificate for localhost (uses Docker, nothing to install).
New-Item -ItemType Directory -Force nginx/certs | Out-Null
docker run --rm -v "${PWD}/nginx/certs:/certs" alpine/openssl req -x509 -nodes -newkey rsa:2048 `
  -days 365 -keyout /certs/server.key -out /certs/server.crt `
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
Write-Host "Certificate written to nginx/certs/"
