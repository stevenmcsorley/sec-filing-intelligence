FROM node:20-alpine AS base
WORKDIR /app

COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
# Install basic OS deps that help with network/TLS and git-based packages
RUN apk add --no-cache ca-certificates git openssh && update-ca-certificates || true

# Configure npm to be tolerant of transient network failures and ensure the
# public registry is used in CI builds. These settings increase retries and
# timeouts so builds are less likely to fail due to intermittent network issues.
RUN npm config set registry https://registry.npmjs.org/ \
 && npm config set fetch-retries 5 \
 && npm config set fetch-retry-factor 10 \
 && npm config set fetch-retry-mintimeout 20000 \
 && npm config set fetch-retry-maxtimeout 60000

# Install dependencies (allow transient failures to be retried by Docker rebuilds)
RUN npm ci --ignore-scripts --prefer-offline

WORKDIR /app/frontend
COPY frontend/package.json ./package.json
COPY frontend/tsconfig.json ./tsconfig.json
COPY frontend/next.config.js ./next.config.js
COPY frontend/postcss.config.js ./postcss.config.js
COPY frontend/.eslintrc.json ./.eslintrc.json
COPY frontend/tailwind.config.js ./tailwind.config.js
COPY frontend/app ./app
COPY frontend/public ./public
COPY frontend/styles ./styles
COPY frontend/lib ./lib
COPY frontend/services ./services
COPY frontend/components ./components
COPY frontend/types ./types
COPY frontend/next-env.d.ts ./next-env.d.ts

RUN npm install --ignore-scripts && npm run build

EXPOSE 3000

CMD ["npm", "run", "dev"]
