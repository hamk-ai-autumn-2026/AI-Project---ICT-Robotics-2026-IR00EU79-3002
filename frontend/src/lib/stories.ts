import { apiFetch, ApiError } from "./api";

// Keep this list in sync with backend/src/schemas/story.ts READING_LEVELS.
export const READING_LEVELS = [
  { value: "beginner", label: "Beginner (ages 3-5)" },
  { value: "early-reader", label: "Early reader (ages 6-8)" },
  { value: "confident-reader", label: "Confident reader (ages 9+)" },
] as const;

export type ReadingLevel = (typeof READING_LEVELS)[number]["value"];

export type StoryFormInput = {
  childName: string;
  childAppearance: string;
  favoriteTheme: string;
  readingLevel: ReadingLevel;
  moralLesson: string;
};

export type StoryStatus =
  | "DRAFT"
  | "OUTLINE_READY"
  | "GENERATING"
  | "COMPLETE"
  | "FAILED";

export type Page = {
  id: string;
  pageNumber: number;
  summary: string;
  text: string | null;
  imagePrompt: string | null;
  moderationFlag: boolean;
  asset: { url: string } | null;
};

export type Story = StoryFormInput & {
  id: string;
  title: string | null;
  status: StoryStatus;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  pages?: Page[];
};

// Field-level validation errors returned by the backend's Zod schema, keyed by
// field name (matches StoryFormInput keys).
export type StoryFieldErrors = Partial<Record<keyof StoryFormInput, string[]>>;

export class StoryValidationError extends Error {
  fields: StoryFieldErrors;
  constructor(message: string, fields: StoryFieldErrors) {
    super(message);
    this.fields = fields;
  }
}

export async function createStory(input: StoryFormInput): Promise<Story> {
  try {
    const { story } = await apiFetch<{ story: Story }>("/api/stories", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return story;
  } catch (err) {
    // Turn a 400 validation response into a StoryValidationError so the form
    // can show inline per-field messages instead of a generic banner.
    if (err instanceof ApiError && err.status === 400) {
      const body = err.body as { error?: string; fields?: StoryFieldErrors };
      throw new StoryValidationError(
        body.error ?? "Invalid story details",
        body.fields ?? {}
      );
    }
    throw err;
  }
}

export async function getStory(id: string): Promise<Story> {
  const { story } = await apiFetch<{ story: Story }>(`/api/stories/${id}`);
  return story;
}
