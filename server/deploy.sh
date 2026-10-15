#!/bin/bash
# Build the padel site (page, slot refresher, stats) inside minikube on the server and deploy it to
# padel.saffist3r.xyz. Uses your SSH key; safe to run again for each update.
set -euo pipefail

HOST=debian@51.254.142.132
DOMAIN=padel.saffist3r.xyz
NS=padel-idl
TAG=$(git -C "$(dirname "$0")" rev-parse --short HEAD 2>/dev/null || date +%s)
REMOTE_DIR=/tmp/padel-idl-deploy

cd "$(dirname "$0")/.."
echo "Copying sources (tag $TAG)..."
ssh "$HOST" "rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR"
COPYFILE_DISABLE=1 tar --exclude __pycache__ -czf - Dockerfile site server/requirements.txt server/app server/k8s \
  | ssh "$HOST" "tar -xzf - -C $REMOTE_DIR"

ssh "$HOST" TAG="$TAG" DOMAIN="$DOMAIN" NS="$NS" REMOTE_DIR="$REMOTE_DIR" bash -s <<'EOF'
set -euo pipefail
cd "$REMOTE_DIR"

echo "Building image padel-idl:$TAG in minikube..."
eval "$(minikube -p minikube docker-env)"
docker build -q -t "padel-idl:$TAG" .

sed "s/IMAGE_TAG/$TAG/g" server/k8s/padel-idl.yaml > /tmp/padel-idl.yaml
kubectl apply -f /tmp/padel-idl.yaml

if ! kubectl get secret stats-auth -n "$NS" >/dev/null 2>&1; then
  echo "Creating the stats password (read it with the command printed at the end)..."
  kubectl create secret generic stats-auth -n "$NS" --from-literal=password="$(openssl rand -base64 18 | tr -d '/+=')"
fi

# TLS: same pattern as the other apps — certbot on the host, copied into a k8s secret
HOOK=/etc/letsencrypt/renewal-hooks/deploy/50-k8s-tls-secrets.sh
if ! sudo grep -q "^  $DOMAIN)" "$HOOK"; then
  echo "Registering $DOMAIN in the certbot renewal hook..."
  sudo cp "$HOOK" "$HOOK.bak.$(date +%Y%m%d%H%M%S)"
  sudo sed -i "s|^  \*) echo|  $DOMAIN)$(printf '%*s' $((31 - ${#DOMAIN} - 1)) '')targets=\"$NS/padel-idl-tls\" ;;\n  *) echo|" "$HOOK"
fi
if ! sudo test -d "/etc/letsencrypt/live/$DOMAIN"; then
  echo "Requesting a Let's Encrypt certificate for $DOMAIN..."
  sudo certbot certonly --non-interactive --standalone --http-01-port 8402 --key-type ecdsa \
    --cert-name "$DOMAIN" -d "$DOMAIN" \
    --pre-hook /etc/letsencrypt/renewal-hooks/pre/10-acme-port-redirect.sh \
    --post-hook /etc/letsencrypt/renewal-hooks/post/10-acme-port-redirect.sh
fi
if ! kubectl get secret padel-idl-tls -n "$NS" >/dev/null 2>&1; then
  sudo RENEWED_LINEAGE="/etc/letsencrypt/live/$DOMAIN" "$HOOK"
fi

kubectl rollout status deploy/padel-idl -n "$NS" --timeout=120s
EOF

echo
echo "Deployed: https://$DOMAIN (stats: https://$DOMAIN/admin)"
echo "Stats password: ssh $HOST \"kubectl get secret stats-auth -n $NS -o jsonpath='{.data.password}' | base64 -d; echo\""
