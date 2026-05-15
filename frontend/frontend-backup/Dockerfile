FROM node:20-alpine

WORKDIR /app

# Copy package files first for better Docker cache
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source code
COPY . .

# Expose Next.js port
EXPOSE 3000

# Start Next.js dev server
CMD ["npm", "run", "dev"]