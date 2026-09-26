import { Router } from "express";
import { ZodError } from "zod";
import { prisma } from "../lib/prisma";
import { asyncHandler } from "../middleware/errorHandler";
import { createStorySchema } from "../schemas/story";

export const storiesRouter = Router();

// POST /api/stories - step 2: create a story from the form inputs.
// This just persists the form as a DRAFT story; the actual outline/page/image
// generation (Claude + image API) is wired up in steps 3-5. Keeping "create"
// and "generate" as separate steps means the frontend can show the form
// result immediately without waiting on slow AI calls.
storiesRouter.post(
  "/",
  asyncHandler(async (req, res) => {
    let input;
    try {
      input = createStorySchema.parse(req.body);
    } catch (err) {
      if (err instanceof ZodError) {
        // Flatten Zod's nested error format into a simple field -> message map
        // so the frontend form can show inline errors per field.
        return res.status(400).json({
          error: "Invalid story details",
          fields: err.flatten().fieldErrors,
        });
      }
      throw err;
    }

    const story = await prisma.story.create({
      data: {
        ...input,
        status: "DRAFT",
      },
    });

    res.status(201).json({ story });
  })
);

// GET /api/stories/:id - fetch a single story with its pages, used by the
// viewer (step 6) and to poll generation status after creation.
storiesRouter.get(
  "/:id",
  asyncHandler(async (req, res) => {
    const story = await prisma.story.findUnique({
      where: { id: req.params.id },
      include: { pages: { orderBy: { pageNumber: "asc" }, include: { asset: true } } },
    });

    if (!story) {
      return res.status(404).json({ error: "Story not found" });
    }

    res.json({ story });
  })
);
