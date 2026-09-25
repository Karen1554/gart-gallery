# Imagen ligera de Node.js
FROM node:18-alpine

WORKDIR /app

# Crear el archivo server.js
RUN echo 'const http = require("http"); const server = http.createServer((req, res) => { res.writeHead(200, { "Content-Type": "application/json" }); res.end(JSON.stringify({ status: "ok", message: "Backend API running in Azure Container Apps" })); }); server.listen(5000, () => console.log("Server running on port 5000"));' > server.js

EXPOSE 5000

CMD ["node", "server.js"]
