# Build Stage
FROM node:18-slim as build

WORKDIR /app

# Early copy removed to prevent overwrite issues
# Dependencies installed after full copy


COPY cityreport/ .
RUN rm -rf node_modules
RUN npm install --legacy-peer-deps
RUN npm rebuild esbuild
RUN npm run build

# Serve Stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy custom nginx config if needed (we will use the root nginx for reverse proxy, 
# but this nginx serves static files)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
