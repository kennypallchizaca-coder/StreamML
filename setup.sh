#!/usr/bin/env bash
set -e

echo -e "\033[0;36m=========================================\033[0m"
echo -e "\033[0;36m   Asistente de Configuración StreamML   \033[0m"
echo -e "\033[0;36m=========================================\033[0m"
echo ""

ENV_FILE=".env"
ENV_TEMPLATE=".env.example"

if [ ! -f "$ENV_TEMPLATE" ]; then
    echo "El archivo $ENV_TEMPLATE no existe. Ejecuta este script desde la raíz del proyecto."
    exit 1
fi

cp "$ENV_TEMPLATE" "$ENV_FILE"

generate_secret() {
    openssl rand -hex 32
}

echo -e "\033[1;33mConfiguración del Dominio\033[0m"
read -p "Ingresa tu dominio principal (ej. stream.mi-empresa.com) [Dejar vacío para localhost]: " DOMAIN
if [ -z "$DOMAIN" ]; then
    DOMAIN="localhost"
    PROTOCOL="http"
else
    PROTOCOL="https"
fi

echo -e "\n\033[1;33mConfiguración de Administrador\033[0m"
read -p "Correo del administrador inicial: " EMAIL
read -p "Contraseña temporal del administrador: " PASSWORD

if [ "$DOMAIN" != "localhost" ]; then
    echo -e "\n\033[1;33mConfiguración de Certificados SSL (Opcional si usas localhost)\033[0m"
    read -p "Ruta al certificado SSL (ej. ./certs/fullchain.pem) [Presiona Enter para ignorar]: " TLS_CERT
    read -p "Ruta a la llave SSL (ej. ./certs/privkey.pem) [Presiona Enter para ignorar]: " TLS_KEY
else
    TLS_CERT=""
    TLS_KEY=""
fi

TOKEN_SECRET=$(generate_secret)
MEDIA_AUTH_SECRET=$(generate_secret)

# Sed replacements
sed -i "s|^STREAMML_ENVIRONMENT=.*|STREAMML_ENVIRONMENT=production|" "$ENV_FILE"
sed -i "s|^STREAMML_TOKEN_SECRET=.*|STREAMML_TOKEN_SECRET=$TOKEN_SECRET|" "$ENV_FILE"
sed -i "s|^STREAMML_MEDIA_AUTH_SECRET=.*|STREAMML_MEDIA_AUTH_SECRET=$MEDIA_AUTH_SECRET|" "$ENV_FILE"
sed -i "s|^STREAMML_ALLOWED_ORIGINS=.*|STREAMML_ALLOWED_ORIGINS=$PROTOCOL://$DOMAIN|" "$ENV_FILE"
sed -i "s|^STREAMML_MEDIAMTX_PUBLIC_BASE=.*|STREAMML_MEDIAMTX_PUBLIC_BASE=$PROTOCOL://$DOMAIN/media|" "$ENV_FILE"
sed -i "s|^STREAMML_BOOTSTRAP_EMAIL=.*|STREAMML_BOOTSTRAP_EMAIL=$EMAIL|" "$ENV_FILE"
sed -i "s|^STREAMML_BOOTSTRAP_PASSWORD=.*|STREAMML_BOOTSTRAP_PASSWORD=$PASSWORD|" "$ENV_FILE"

if [ -n "$TLS_CERT" ] && [ -n "$TLS_KEY" ]; then
    echo "TLS_CERT_FILE=$TLS_CERT" >> "$ENV_FILE"
    echo "TLS_KEY_FILE=$TLS_KEY" >> "$ENV_FILE"
else
    sed -i "/^TLS_CERT_FILE=/d" "$ENV_FILE"
    sed -i "/^TLS_KEY_FILE=/d" "$ENV_FILE"
fi

echo -e "\n\033[0;32m¡Configuración completada! Se ha generado tu archivo .env con secretos seguros.\033[0m"
echo -e "\033[0;36mAhora puedes iniciar el sistema con: docker-compose -f infrastructure/docker/docker-compose.yml up -d\033[0m"
