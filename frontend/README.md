# Theoria Frontend

This is the modern React frontend for the Theoria service dashboard. It replaces the legacy single-file dashboard found in `../dashboard/index.html`.

## Features

-   **Real-time Monitoring**: Polls service metrics every 5 seconds.
-   **Modern Stack**: Built with Vite, React, and TypeScript.
-   **Type Safety**: Full TypeScript support for metrics data.
-   **Componentized**: Modular architecture for better maintainability.

## Getting Started

### Prerequisites

-   Node.js (v20.19+ or v22.12+ recommended by Vite, though v22.11.0 works with warnings)
-   npm

### Installation

```bash
cd frontend
npm install
```

### Development

To start the development server:

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

### Building for Production

To build the application for production:

```bash
npm run build
```

The artifacts will be in the `dist` directory.

## Configuration

The metrics URL defaults to `http://localhost:9101/metrics`. To change this, set the `VITE_METRICS_URL` environment variable in a `.env` file:

```
VITE_METRICS_URL=http://your-service:9101/metrics
```
