# Локальный GUI

Bothost ищет `package.json` и из‑за него собирает Node-образ без Python. Поэтому манифест npm лежит как `package.gui.json`.

```bash
cd local
cp package.gui.json package.json
cp package-lock.gui.json package-lock.json
npm install
npm run dev
```

Откройте http://127.0.0.1:43122
