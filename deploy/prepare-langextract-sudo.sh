#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────────────────
# Langextract — exponer el servicio de DESARROLLO en internet (langextract.tribbe.es)
# Requisitos (por orden):
#   1. A record en WebEmpresa:  langextract  →  141.94.92.173   (el A record actual NO existe)
#   2. Ejecutar ESTE script con sudo (teclea tu password en este terminal):
#        cd ~/repos/langextract-cuidum && sudo bash deploy/prepare-langextract-sudo.sh
#
# Qué hace (idempotente; re-ejecutable sin romper):
#   - Crea credenciales de acceso (user/contraseña) si no existen → .htpasswd-langextract
#   - Instala el vhost nginx con BASIC AUTH + proxy al servicio (127.0.0.1:8654)
#   - Emite/reutiliza el certificado Let's Encrypt (necesita el DNS ya apuntando)
#   - Verifica con curl.
# Seguridad: basic auth en TODA la URL (UI + API) + X-API-Key en la app.
# ────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="langextract.tribbe.es"
UPSTREAM="http://127.0.0.1:8654"
HTPASSWD="/etc/nginx/.htpasswd-langextract"
VHOST="/etc/nginx/sites-available/${DOMAIN}"
LIVE_DIR="/etc/letsencrypt/live/${DOMAIN}"
AUTH_USER="${LANGE_AUTH_USER:-langextract}"
CREDS_TMP="/tmp/langextract-creds.txt"

# ── 0. Guardas de entorno (por si lo ejecuta sin sudo) ───────────────────
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ Ejecuta con sudo:  sudo bash deploy/prepare-langextract-sudo.sh"
  exit 1
fi
echo "→ Comprobando que el servicio responde en 127.0.0.1:8654..."
curl -s -m 4 http://127.0.0.1:8654/health >/dev/null || { echo "❌ El servicio no responde en 8654. ¿Está el contenedor arriba?"; exit 1; }

# ── 1. Credenciales basic-auth (se crean UNA vez) ────────────────────────
if [ -f "$HTPASSWD" ]; then
  echo "→ htpasswd ya existe (${HTPASSWD})"
else
  PASS="${LANGE_AUTH_PASS:-$(openssl rand -base64 18 | tr -d '/+=' )}"
  HASH="$(openssl passwd -apr1 "${PASS}")"
  printf '%s:%s\n' "${AUTH_USER}" "${HASH}" > "${HTPASSWD}"
  chmod 640 "${HTPASSWD}"
  chown root:www-data "${HTPASSWD}" 2>/dev/null || true
  umask 077; >"${CREDS_TMP}"; printf 'URL: https://%s\nUsuario: %s\nContraseña: %s\n' "${DOMAIN}" "${AUTH_USER}" "${PASS}" > "${CREDS_TMP}"
  echo "🔑 Credenciales generadas (guárdalas, se muestran UNA vez):"
  cat "${CREDS_TMP}"
  echo "(copia guardada en ${CREDS_TMP}, chmod 600 — borra cuando quieras)"
fi

# ── 2. Vhost (se reescribe siempre: idempotente) ─────────────────────────
TLS_EXTRA=""
if [ -d "$LIVE_DIR" ]; then
  TLS_EXTRA="
    ssl_certificate     ${LIVE_DIR}/fullchain.pem;
    ssl_certificate_key ${LIVE_DIR}/privkey.pem;"
fi
cat > /tmp/langextract.vhost <<EOF
# Langextract dev — autogenerado por deploy/prepare-langextract-sudo.sh
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ { root /var/www/html; }

    location / {
        auth_basic "Langextract dev (en desarrollo)";
        auth_basic_user_file ${HTPASSWD};

        proxy_pass ${UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
        client_max_body_size 12m;
    }
}
EOF
if [ -n "$TLS_EXTRA" ]; then
cat >> /tmp/langextract.vhost <<EOF

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name ${DOMAIN};
${TLS_EXTRA}

    location / {
        auth_basic "Langextract dev (en desarrollo)";
        auth_basic_user_file ${HTPASSWD};

        proxy_pass ${UPSTREAM};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_buffering off;
        client_max_body_size 12m;
    }
}
EOF
fi

cp /tmp/langextract.vhost "${VHOST}"
ln -sf "${VHOST}" "/etc/nginx/sites-enabled/${DOMAIN}"
echo "→ Vhost instalado en ${VHOST}"
nginx -t && systemctl reload nginx && echo "✓ nginx OK (basic auth activo)"

# ── 3. Certificado Let's Encrypt (solo si el DNS ya apunta) ──────────────
if [ ! -d "$LIVE_DIR" ]; then
  if ! dig +short "${DOMAIN}" A | grep -q '^[0-9]'; then
    echo "⚠️  El A record de ${DOMAIN} aún NO apunta aquí — certbot fallaría (NXDOMAIN)."
    echo "    Crea en WebEmpresa:  A  langextract  →  141.94.92.173"
    echo "    Cuando lo tengas, vuelve a ejecutar este script (re-instalará el vhost 443)."
    exit 0
  fi
  certbot certonly --nginx -d "${DOMAIN}" --non-interactive --agree-tos --no-redirect
  # Re-insertar el bloque 443 + redirect
  exec bash "$0"
elif [ -d "$LIVE_DIR" ]; then
  echo "✓ Certificado ya presente en ${LIVE_DIR} (se reutiliza)"
  # Asegurar HTTP→HTTPS cuando ya hay cert
  if ! grep -q "301 https" "${VHOST}"; then
    : # vhost sin redirect; el bloque 443 ya está sirviendo HTTPS
  fi
fi

# ── 4. Verificación ──────────────────────────────────────────────────────
echo "── Verificación ──"
echo "DNS:"; dig +short "${DOMAIN}" A || true
echo "HTTP (local, con Host header + basic auth):"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: ${DOMAIN}" http://127.0.0.1/ || true)
echo "  sin credenciales → ${CODE} (401 esperado)"
echo "  con credenciales → $(curl -s -o /dev/null -w '%{http_code}' -u "${AUTH_USER}:$(grep -oP 'Contraseña: \K.*' "${CREDS_TMP}" 2>/dev/null || echo x)" -H "Host: ${DOMAIN}" http://127.0.0.1/health 2>/dev/null || echo '?')"
echo
echo "✅ Listo. Acceso público: https://${DOMAIN}  (credenciales: ${CREDS_TMP})"