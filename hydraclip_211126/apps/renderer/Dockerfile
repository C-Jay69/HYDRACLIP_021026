FROM node:22-bookworm-slim

WORKDIR /app

# Shared libraries required by Chrome Headless Shell (Remotion's bundled browser)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libdbus-1-3 \
    libatk1.0-0 \
    libgbm-dev \
    libasound2 \
    libxrandr2 \
    libxkbcommon-dev \
    libxfixes3 \
    libxcomposite1 \
    libxdamage1 \
    libatk-bridge2.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libcups2 \
    fonts-dejavu-core \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so this layer is cached when only source changes
COPY package.json ./
RUN npm install --no-audit --no-fund

# Download Remotion's headless browser at build time
RUN npx remotion browser ensure

# Application source
COPY tsconfig.json remotion.config.ts ./
COPY src ./src
COPY public ./public
COPY server.mjs ./

# Pre-bundle the Remotion project so requests do not pay bundling cost
RUN npx remotion bundle src/index.ts --out-dir=build

ENV NODE_ENV=production
ENV PORT=3001
ENV REMOTION_BUNDLE_DIR=/app/build
ENV REMOTION_COMPOSITION_ID=HydraClipShort

EXPOSE 3001

CMD ["node", "server.mjs"]
