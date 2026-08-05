# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
ENV NUXT_API_URL=http://api:8000
ENV NUXT_PUBLIC_API_BASE=/api
RUN npm run build

# Runtime stage
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
ENV NUXT_API_URL=http://api:8000
ENV NUXT_PUBLIC_API_BASE=/api

COPY --from=build /app/.output ./.output

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
