import { Router } from "express";
import { prisma } from "../lib/prisma";

export const healthRouter = Router();

// Simple liveness check for step 1: confirms the API is up and (optionally) that
// the database connection works. Useful for Render/Railway health checks too.
healthRouter.get("/", async (_req, res) => {
  let dbStatus: "ok" | "error" = "ok";
  try {
    await prisma.$queryRaw`SELECT 1`;
  } catch {
    dbStatus = "error";
  }

  res.json({
    status: "ok",
    db: dbStatus,
    timestamp: new Date().toISOString(),
  });
});
