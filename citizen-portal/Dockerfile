# NEXT_PUBLIC_* values are inlined into the client bundle at build time by
# Next.js itself - there is no way to set them at container-run time, so
# they must be passed as build args here, and re-supplied (with new values)
# any time this image is rebuilt for a different environment.
ARG NEXT_PUBLIC_ORCHESTRATOR_URL=http://localhost:8005
ARG NEXT_PUBLIC_AGENT1_URL=http://localhost:8001
ARG NEXT_PUBLIC_AGENT2_URL=http://localhost:8002
ARG NEXT_PUBLIC_AGENT3_URL=http://localhost:8003
ARG NEXT_PUBLIC_AGENT9_URL=http://localhost:8009

FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_ORCHESTRATOR_URL
ARG NEXT_PUBLIC_AGENT1_URL
ARG NEXT_PUBLIC_AGENT2_URL
ARG NEXT_PUBLIC_AGENT3_URL
ARG NEXT_PUBLIC_AGENT9_URL
ENV NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL \
    NEXT_PUBLIC_AGENT1_URL=$NEXT_PUBLIC_AGENT1_URL \
    NEXT_PUBLIC_AGENT2_URL=$NEXT_PUBLIC_AGENT2_URL \
    NEXT_PUBLIC_AGENT3_URL=$NEXT_PUBLIC_AGENT3_URL \
    NEXT_PUBLIC_AGENT9_URL=$NEXT_PUBLIC_AGENT9_URL

RUN npm run build

# --- Runtime stage: only the standalone server + static assets, no
# node_modules / source / dev toolchain (next.config.js's output:
# "standalone" is what makes this possible).
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# No public/ dir exists in this project yet - add
# "COPY --from=builder /app/public ./public" here if one is added later.

EXPOSE 3000
CMD ["node", "server.js"]
