# ── Speegile ATS — frontend (React + Vite) ──────────────────────────────────
# Multi-stage: build the static SPA with Node, then serve it with nginx, which
# also proxies /api to the backend service (see nginx.conf).

# 1) Build  (Node 22 LTS — required by Vite 8 / React 19 / TS 6 in package.json)
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Baked in at build time. In compose this is "/api" so the SPA calls nginx,
# which proxies to the backend (no CORS, no hardcoded host).
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# 2) Serve
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
