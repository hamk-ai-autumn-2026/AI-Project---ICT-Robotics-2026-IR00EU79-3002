import { z } from "zod";

// Allowed reading levels shown in the frontend form's dropdown. Keeping this as
// a fixed set (rather than free text) makes the value easy to drop straight
// into the Claude prompt in step 3 (e.g. "write for a beginner reader").
export const READING_LEVELS = [
  "beginner",
  "early-reader",
  "confident-reader",
] as const;

// Validates the story creation form submitted by the frontend in step 2.
// Kept in its own file (rather than inline in the route) so the same schema
// can be reused by tests or by later steps (e.g. regenerate endpoints).
export const createStorySchema = z.object({
  childName: z.string().trim().min(1, "Child's name is required").max(80),
  childAppearance: z
    .string()
    .trim()
    .min(1, "A short appearance description is required")
    .max(500),
  favoriteTheme: z
    .string()
    .trim()
    .min(1, "Favorite animal/theme is required")
    .max(200),
  readingLevel: z.enum(READING_LEVELS),
  moralLesson: z
    .string()
    .trim()
    .min(1, "A moral or lesson is required")
    .max(300),
});

export type CreateStoryInput = z.infer<typeof createStorySchema>;
