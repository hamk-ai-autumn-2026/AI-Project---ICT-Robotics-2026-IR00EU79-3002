import { NextFunction, Request, Response } from "express";

// Centralized error handler so every route can just `next(err)` instead of
// duplicating try/catch response formatting. Keep this generic for now;
// we can add specific handling for AI-provider errors as those routes are built.
export function errorHandler(
  err: unknown,
  _req: Request,
  res: Response,
  _next: NextFunction
) {
  console.error(err);

  const status =
    typeof err === "object" && err !== null && "status" in err
      ? Number((err as { status: unknown }).status) || 500
      : 500;

  const message =
    err instanceof Error ? err.message : "Unexpected server error";

  res.status(status).json({ error: message });
}

// Wraps an async route handler so thrown errors / rejected promises are
// forwarded to Express's error handler instead of crashing the process.
export function asyncHandler<T extends (...args: any[]) => Promise<any>>(
  fn: T
) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}
