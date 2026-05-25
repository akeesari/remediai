FROM node:20-alpine AS build

WORKDIR /app

COPY apps/dashboard/package*.json ./
RUN npm install --legacy-peer-deps

COPY apps/dashboard/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/dashboard/nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
