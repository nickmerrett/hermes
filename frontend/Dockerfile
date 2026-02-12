# Build stage
FROM docker.io/library/node:24-alpine as build

WORKDIR /app

# Copy package files first (layer cached unless these change)
COPY package.json package-lock.json ./

# Install dependencies using ci for faster, reproducible installs from lockfile
RUN npm ci

# Copy source code (only this layer invalidates on code changes)
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM docker.io/library/nginx:alpine

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
