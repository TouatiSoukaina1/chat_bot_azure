# Étape 1 : build frontend
FROM node:20-bullseye AS build
WORKDIR /app/frontend

# Copier tout le dossier frontend dans le conteneur
COPY frontend/ ./  

# Installer les dépendances
RUN npm install

# Builder le frontend
RUN npm run build

# Étape 2 : serveur web léger avec nginx
FROM nginx:alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
