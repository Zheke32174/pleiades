#!/usr/bin/env bash
set -euo pipefail

OUT=${1:-./local-pki}
DAYS_CA=${DAYS_CA:-3650}
DAYS_LEAF=${DAYS_LEAF:-825}

if [[ -e "$OUT" ]]; then
  echo "Refusing to overwrite existing PKI directory: $OUT" >&2
  exit 1
fi

umask 077
mkdir -p "$OUT"

openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$OUT/ca.key.pem"
openssl req -x509 -new -sha256 -days "$DAYS_CA" \
  -key "$OUT/ca.key.pem" \
  -subj "/CN=Pleiades Epoch 2 Local CA/O=Pleiades" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -out "$OUT/ca.cert.pem"

issue_leaf() {
  local stem=$1
  local common_name=$2
  local dns_name=$3
  local uri_san=$4
  local ext="$OUT/${stem}.ext"

  openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 \
    -out "$OUT/${stem}.key.pem"
  openssl req -new -sha256 \
    -key "$OUT/${stem}.key.pem" \
    -subj "/CN=${common_name}/O=Pleiades" \
    -out "$OUT/${stem}.csr.pem"
  cat > "$ext" <<EXT
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth,clientAuth
subjectAltName=DNS:${dns_name},URI:${uri_san}
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EXT
  openssl x509 -req -sha256 -days "$DAYS_LEAF" \
    -in "$OUT/${stem}.csr.pem" \
    -CA "$OUT/ca.cert.pem" \
    -CAkey "$OUT/ca.key.pem" \
    -CAcreateserial \
    -extfile "$ext" \
    -out "$OUT/${stem}.cert.pem"
  cat "$OUT/${stem}.cert.pem" "$OUT/ca.cert.pem" > "$OUT/${stem}.chain.pem"
  rm -f "$OUT/${stem}.csr.pem" "$ext"
}

issue_leaf \
  controller-alienware \
  controller-alienware \
  controller.pdk.local \
  spiffe://pleiades.local/controller/alienware-primary

issue_leaf \
  node-alienware \
  node-alienware \
  alienware-node.pdk.local \
  spiffe://pleiades.local/node/alienware

issue_leaf \
  node-lenovo \
  node-lenovo \
  lenovo-node.pdk.local \
  spiffe://pleiades.local/node/lenovo

chmod 0600 "$OUT"/*.key.pem
chmod 0644 "$OUT"/*.cert.pem "$OUT"/*.chain.pem

: > "$OUT/fingerprints.txt"
for cert in "$OUT"/*.cert.pem; do
  printf '%s ' "$(basename "$cert")" >> "$OUT/fingerprints.txt"
  openssl x509 -in "$cert" -noout -fingerprint -sha256 \
    | sed 's/^sha256 Fingerprint=//;s/^SHA256 Fingerprint=//;s/://g' \
    | tr '[:upper:]' '[:lower:]' >> "$OUT/fingerprints.txt"
done

cat <<MSG
Created a strict local CA and three dual-use mTLS identities in:
  $OUT

Certificate fingerprints:
$(cat "$OUT/fingerprints.txt")

Copy only the required identity and CA files to each host. Keep ca.key.pem
offline after enrollment. The Ed25519 message-signing keys are separate and
must be generated with pdk-keygen.
MSG
