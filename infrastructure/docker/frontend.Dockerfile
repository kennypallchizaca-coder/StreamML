FROM node:22-alpine AS build

WORKDIR /app
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci
COPY apps/frontend/ ./
ARG VITE_API_BASE_URL=/api/v1
ARG VITE_WS_BASE_URL=/ws
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL}
RUN npm run build

FROM nginx:1.30.3-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/frontend.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
