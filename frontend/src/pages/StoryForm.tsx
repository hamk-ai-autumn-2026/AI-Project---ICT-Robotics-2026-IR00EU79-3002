import { FormEvent, ReactNode, useState } from "react";
import {
  createStory,
  READING_LEVELS,
  Story,
  StoryFieldErrors,
  StoryFormInput,
  StoryValidationError,
} from "../lib/stories";

const EMPTY_FORM: StoryFormInput = {
  childName: "",
  childAppearance: "",
  favoriteTheme: "",
  readingLevel: "early-reader",
  moralLesson: "",
};

type Props = {
  // Called after the story is successfully saved as a DRAFT. The actual
  // outline/page/image generation happens in steps 3-5, so for now this just
  // hands the created story back up to App so we can show a confirmation.
  onCreated: (story: Story) => void;
};

// Step 2: the story creation form. Collects the child's details and posts
// them to POST /api/stories. Field-level errors from the backend's Zod
// validation are shown inline next to each input.
export function StoryForm({ onCreated }: Props) {
  const [form, setForm] = useState<StoryFormInput>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<StoryFieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function updateField<K extends keyof StoryFormInput>(
    key: K,
    value: StoryFormInput[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setSubmitting(true);
    try {
      const story = await createStory(form);
      onCreated(story);
    } catch (err) {
      if (err instanceof StoryValidationError) {
        setFieldErrors(err.fields);
        setFormError(err.message);
      } else {
        setFormError(
          err instanceof Error ? err.message : "Could not create story"
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-lg w-full bg-white rounded-2xl shadow p-8 space-y-5"
    >
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Create a Storybook</h1>
        <p className="text-slate-500 text-sm mt-1">
          Tell us about the child and we'll write a personalized story just
          for them.
        </p>
      </div>

      {formError && (
        <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3">
          {formError}
        </p>
      )}

      <Field
        label="Child's name"
        error={fieldErrors.childName}
      >
        <input
          type="text"
          value={form.childName}
          onChange={(e) => updateField("childName", e.target.value)}
          placeholder="e.g. Amara"
          className="input"
        />
      </Field>

      <Field
        label="Appearance"
        hint="A short description used to keep illustrations consistent."
        error={fieldErrors.childAppearance}
      >
        <textarea
          value={form.childAppearance}
          onChange={(e) => updateField("childAppearance", e.target.value)}
          placeholder="e.g. curly black hair, brown eyes, wears glasses"
          rows={2}
          className="input"
        />
      </Field>

      <Field
        label="Favorite animal or theme"
        error={fieldErrors.favoriteTheme}
      >
        <input
          type="text"
          value={form.favoriteTheme}
          onChange={(e) => updateField("favoriteTheme", e.target.value)}
          placeholder="e.g. dinosaurs, foxes, outer space"
          className="input"
        />
      </Field>

      <Field label="Reading level" error={fieldErrors.readingLevel}>
        <select
          value={form.readingLevel}
          onChange={(e) =>
            updateField(
              "readingLevel",
              e.target.value as StoryFormInput["readingLevel"]
            )
          }
          className="input"
        >
          {READING_LEVELS.map((level) => (
            <option key={level.value} value={level.value}>
              {level.label}
            </option>
          ))}
        </select>
      </Field>

      <Field
        label="Moral or lesson to teach"
        error={fieldErrors.moralLesson}
      >
        <input
          type="text"
          value={form.moralLesson}
          onChange={(e) => updateField("moralLesson", e.target.value)}
          placeholder="e.g. sharing is caring"
          className="input"
        />
      </Field>

      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold rounded-lg py-2.5 transition-colors"
      >
        {submitting ? "Saving..." : "Create Storybook"}
      </button>
    </form>
  );
}

// Small helper to render a labeled field with an optional hint and backend
// validation error, keeping the form markup above readable.
function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string[];
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {hint && <span className="block text-xs text-slate-400">{hint}</span>}
      <div className="mt-1">{children}</div>
      {error?.map((msg) => (
        <span key={msg} className="block text-xs text-red-600 mt-1">
          {msg}
        </span>
      ))}
    </label>
  );
}
