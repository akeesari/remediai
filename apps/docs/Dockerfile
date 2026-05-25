FROM node:20-alpine AS build

WORKDIR /app

COPY apps/docs/package*.json ./
RUN npm ci

COPY apps/docs/ ./
RUN npm run build

FROM nginx:1.27-alpine AS production

# Copy build output to /remediai/ so Nginx serves it at the same path
# as GitHub Pages (baseUrl: '/remediai/'), keeping local and deployed URLs consistent.
COPY --from=build /app/build /usr/share/nginx/html/remediai
COPY apps/docs/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
