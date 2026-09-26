import "dotenv/config";
import express from "express";
import cors from "cors";
import helmet from "helmet";
import { errorHandler } from "./middleware/errorHandler";
import { healthRouter } from "./routes/health";
import { storiesRouter } from "./routes/stories";

const app = express();
const port = Number(process.env.PORT) || 4000;

// Allow the frontend dev server / deployed frontend to call this API.
const allowedOrigins = (process.env.CORS_ORIGIN ?? "http://localhost:5173")
  .split(",")
  .map((origin) => origin.trim());

app.use(helmet());
app.use(cors({ origin: allowedOrigins }));
app.use(express.json({ limit: "2mb" }));

app.use("/api/health", healthRouter);
app.use("/api/stories", storiesRouter);

// Keep the error handler mounted last so it catches errors from all routes above.
app.use(errorHandler);

app.listen(port, () => {
  console.log(`Storybook backend listening on http://localhost:${port}`);
});
