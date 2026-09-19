# Build stage — `nuxt build` carrega web/.env.production (NODE_ENV=production)
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
ENV NODE_ENV=production
RUN npm run build

# Runtime — aplica .env.production (EasyPanel pode sobrescrever NUXT_* no painel)
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

COPY --from=build /app/.output ./.output
COPY --from=build /app/.env.production ./.env.production

EXPOSE 3000

CMD ["sh", "-c", "set -a && . ./.env.production && set +a && exec node .output/server/index.mjs"]
