FROM node:20-alpine AS base
WORKDIR /app

COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
RUN npm ci --ignore-scripts

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
