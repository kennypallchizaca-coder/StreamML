#!/usr/bin/env bash
set -e

echo -e "\033[0;36m=========================================\033[0m"
echo -e "\033[0;36m   Asistente de Configuración StreamML   \033[0m"
echo -e "\033[0;36m=========================================\033[0m"
echo ""

ENV_FILE="deployment/.env"
ENV_TEMPLATE="deployment/.env.example"

if [ ! -f "$ENV_TEMPLATE" ]; then
    echo "El archivo $ENV_TEMPLATE no existe. Ejecuta este script desde la raíz del proyecto."
    exit 1
fi

cp "$ENV_TEMPLATE" "$ENV_FILE"

generate_secret() {
    openssl rand -hex 32
}

echo -e "\033[1;33mConfiguración del Dominio\033[0m"
read -r -p "Ingresa tu dominio público (ej. stream.mi-empresa.com): " DOMAIN
if [ -z "$DOMAIN" ] || ! printf '%s' "$DOMAIN" | grep -Eq '^[A-Za-z0-9.-]+$'; then
    echo "Se requiere un nombre DNS público válido. Para desarrollo local usa docker-compose.local.yml."
    exit 1
fi
PROTOCOL="https"

echo -e "\n\033[1;33mConfiguración de Administrador\033[0m"
read -r -p "Correo del administrador inicial: " EMAIL
read -r -s -p "Contraseña temporal del administrador: " PASSWORD
printf '\n'
if ! printf '%s' "$EMAIL" | grep -Eq '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'; then
    echo "Ingresa un correo electrónico de administrador válido."
    exit 1
fi
if [ "${#PASSWORD}" -lt 12 ] || printf '%s' "$PASSWORD" | grep -q '[\r\n]'; then
    echo "La contraseña debe tener al menos 12 caracteres y no contener saltos de línea."
    exit 1
fi

echo -e "\n\033[1;33mConfiguración de Certificados SSL\033[0m"
read -r -p "Ruta absoluta al certificado SSL (fullchain.pem): " TLS_CERT
read -r -p "Ruta absoluta a la llave SSL (privkey.pem): " TLS_KEY
if [ "${TLS_CERT#/}" = "$TLS_CERT" ] || [ ! -f "$TLS_CERT" ]; then
    echo "TLS_CERT_FILE debe ser una ruta absoluta a un certificado existente."
    exit 1
fi
if [ "${TLS_KEY#/}" = "$TLS_KEY" ] || [ ! -f "$TLS_KEY" ]; then
    echo "TLS_KEY_FILE debe ser una ruta absoluta a una clave privada existente."
    exit 1
fi

TOKEN_SECRET=$(generate_secret)
MEDIA_AUTH_SECRET=$(generate_secret)

set_value() {
    key=$1
    value=$2
    escaped=$(printf '%s' "$value" | sed 's/[\\&|]/\\&/g')
    temporary_file=$(mktemp "${ENV_FILE}.XXXXXX")
    sed "s|^${key}=.*|${key}=\"${escaped}\"|" "$ENV_FILE" > "$temporary_file"
    mv "$temporary_file" "$ENV_FILE"
}

set_value STREAMML_ENVIRONMENT production
set_value STREAMML_TOKEN_SECRET "$TOKEN_SECRET"
set_value STREAMML_MEDIA_AUTH_SECRET "$MEDIA_AUTH_SECRET"
set_value STREAMML_ALLOWED_ORIGINS "$PROTOCOL://$DOMAIN"
set_value STREAMML_MEDIAMTX_PUBLIC_BASE "$PROTOCOL://$DOMAIN/media"
set_value MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS "$DOMAIN"
set_value STREAMML_BOOTSTRAP_EMAIL "$EMAIL"
set_value STREAMML_BOOTSTRAP_PASSWORD "$PASSWORD"
set_value TLS_CERT_FILE "$TLS_CERT"
set_value TLS_KEY_FILE "$TLS_KEY"

echo -e "\n\033[0;32m¡Configuración completada! Se ha generado $ENV_FILE con secretos seguros.\033[0m"
echo -e "\033[0;36mAhora puedes iniciar el sistema con: docker compose --env-file deployment/.env -f infrastructure/docker/docker-compose.yml up -d --build\033[0m"
